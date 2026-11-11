from datetime import datetime, timedelta
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from viesett.db.models import (
    Account,
    DocumentRequestDraft,
    EvidenceItem,
    Finding,
    FindingEvidence,
    ObjectDeletionTask,
    PropertyDocument,
    PropertyWorkspace,
    utcnow,
)
from viesett.domain.types import WorkspaceStatus
from viesett.services.ownership import owned_document, owned_workspace
from viesett.storage.private import PrivateObjectStorage


async def queue_objects(db: AsyncSession, documents: list[PropertyDocument]) -> None:
    for document in documents:
        await db.execute(
            insert(ObjectDeletionTask)
            .values(
                storage_key=document.storage_key,
            )
            .on_conflict_do_nothing(index_elements=["storage_key"])
        )


async def purge_objects(db: AsyncSession, storage: PrivateObjectStorage) -> int:
    tasks = (
        await db.scalars(
            select(ObjectDeletionTask)
            .where(
                ObjectDeletionTask.not_before <= utcnow(),
            )
            .with_for_update(skip_locked=True)
        )
    ).all()
    count = 0
    for task in tasks:
        try:
            storage.delete(task.storage_key)
        except OSError:
            continue
        await db.delete(task)
        count += 1
    await db.commit()
    return count


async def finish_deletion(
    db: AsyncSession,
    storage: PrivateObjectStorage,
    keys: set[str],
) -> None:
    # Commit logical removal and cleanup tasks atomically before touching storage.
    await db.commit()
    await purge_objects(db, storage)
    pending = await db.scalar(
        select(ObjectDeletionTask.id)
        .where(
            ObjectDeletionTask.storage_key.in_(keys),
        )
        .limit(1)
    )
    if pending is not None:
        raise HTTPException(503, "Data is inaccessible; private object deletion pending retry")


async def delete_document(
    db: AsyncSession,
    user_id: UUID,
    workspace_id: UUID,
    document_id: UUID,
    storage: PrivateObjectStorage,
) -> None:
    await owned_workspace(db, user_id, workspace_id, lock=True)
    document = await owned_document(db, user_id, workspace_id, document_id)
    await queue_objects(db, [document])
    evidence_ids = select(EvidenceItem.id).where(EvidenceItem.document_id == document_id)
    finding_ids = select(FindingEvidence.finding_id).where(
        FindingEvidence.evidence_id.in_(evidence_ids),
    )
    await db.execute(delete(Finding).where(Finding.id.in_(finding_ids)))
    await db.execute(delete(EvidenceItem).where(EvidenceItem.document_id == document_id))
    # Drafts could have been based on the removed evidence: regenerate explicitly.
    await db.execute(
        delete(DocumentRequestDraft).where(
            DocumentRequestDraft.workspace_id == workspace_id,
        )
    )
    await db.execute(
        update(PropertyDocument)
        .where(
            PropertyDocument.workspace_id == workspace_id,
            PropertyDocument.supersedes_document_id == document_id,
        )
        .values(supersedes_document_id=None)
    )
    await db.execute(delete(PropertyDocument).where(PropertyDocument.id == document_id))
    await finish_deletion(db, storage, {document.storage_key})


async def delete_workspace(
    db: AsyncSession,
    user_id: UUID,
    workspace_id: UUID,
    storage: PrivateObjectStorage,
    *,
    archived_before: datetime | None = None,
) -> bool:
    workspace = await owned_workspace(db, user_id, workspace_id, lock=True)
    if archived_before is not None and (
        workspace.status != WorkspaceStatus.ARCHIVED
        or workspace.archived_at is None
        or workspace.archived_at >= archived_before
    ):
        # Revalidate scheduler candidates under the same lock used for deletion.
        await db.commit()
        return False
    documents = list(
        (
            await db.scalars(
                select(PropertyDocument).where(
                    PropertyDocument.workspace_id == workspace_id,
                )
            )
        ).all()
    )
    await queue_objects(db, documents)
    await db.delete(workspace)
    await finish_deletion(db, storage, {d.storage_key for d in documents})
    return True


async def delete_account(
    db: AsyncSession,
    user_id: UUID,
    storage: PrivateObjectStorage,
) -> None:
    account = await db.scalar(select(Account).where(Account.id == user_id).with_for_update())
    if account is None:
        raise HTTPException(404, "Not found")
    documents = list(
        (
            await db.scalars(
                select(PropertyDocument)
                .join(PropertyWorkspace)
                .where(
                    PropertyWorkspace.owner_user_id == user_id,
                )
            )
        ).all()
    )
    await queue_objects(db, documents)
    await db.delete(account)
    await finish_deletion(db, storage, {d.storage_key for d in documents})


async def purge_archived(
    db: AsyncSession,
    storage: PrivateObjectStorage,
    retention_days: int | None,
) -> int:
    if retention_days is None:
        return 0
    cutoff = utcnow() - timedelta(days=retention_days)
    workspaces = (
        await db.scalars(
            select(PropertyWorkspace).where(
                PropertyWorkspace.status == WorkspaceStatus.ARCHIVED,
                PropertyWorkspace.archived_at < cutoff,
            )
        )
    ).all()
    count = 0
    for workspace in workspaces:
        try:
            if await delete_workspace(
                db,
                workspace.owner_user_id,
                workspace.id,
                storage,
                archived_before=cutoff,
            ):
                count += 1
        except HTTPException as error:
            if error.status_code != 404:
                raise
            await db.rollback()
    return count
