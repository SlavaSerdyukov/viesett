import hashlib
from datetime import timedelta
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from viesett.db.models import ObjectDeletionTask, PropertyDocument, utcnow
from viesett.document_safety.pipeline import SafetyPipeline, sanitize_filename, validate_pdf
from viesett.domain.types import DocumentKind, DocumentStatus, WorkspaceStatus
from viesett.services.ownership import owned_workspace
from viesett.services.policies import require_upload_attestation
from viesett.storage.private import PrivateObjectStorage

TRANSITIONS: dict[DocumentStatus, set[DocumentStatus]] = {
    DocumentStatus.UPLOADED: {DocumentStatus.SCANNING, DocumentStatus.DELETED},
    DocumentStatus.SCANNING: {
        DocumentStatus.READY,
        DocumentStatus.QUARANTINED,
        DocumentStatus.REJECTED,
        DocumentStatus.DELETED,
    },
    DocumentStatus.READY: {DocumentStatus.DELETED},
    DocumentStatus.QUARANTINED: {DocumentStatus.DELETED},
    DocumentStatus.REJECTED: {DocumentStatus.DELETED},
    DocumentStatus.DELETED: set(),
}


def transition(document: PropertyDocument, status: DocumentStatus) -> None:
    if status not in TRANSITIONS[document.status]:
        raise ValueError("Invalid document lifecycle transition")
    document.status = status


async def upload_document(
    db: AsyncSession,
    user_id: UUID,
    workspace_id: UUID,
    content: bytes,
    filename: str,
    media_type: str,
    kind: DocumentKind,
    max_size: int,
    storage: PrivateObjectStorage,
    pipeline: SafetyPipeline,
) -> tuple[PropertyDocument, bool]:
    workspace = await owned_workspace(db, user_id, workspace_id, lock=True)
    await require_upload_attestation(db, user_id)
    if workspace.status != WorkspaceStatus.ACTIVE:
        raise HTTPException(409, "Workspace is archived")
    if not content or len(content) > max_size:
        raise HTTPException(413, "Upload size is outside permitted limits")
    validate_pdf(content, media_type)
    digest = hashlib.sha256(content).hexdigest()
    duplicate = await db.scalar(
        select(PropertyDocument).where(
            PropertyDocument.workspace_id == workspace_id,
            PropertyDocument.sha256 == digest,
            PropertyDocument.status != DocumentStatus.DELETED,
        )
    )
    if duplicate is not None:
        return duplicate, False
    # Reserve cleanup durably before writing bytes. The lease exceeds the bounded
    # request duration. A crash at any later step leaves an idempotent purge task.
    key = storage.new_key()
    reservation = ObjectDeletionTask(storage_key=key, not_before=utcnow() + timedelta(minutes=10))
    db.add(reservation)
    await db.commit()
    workspace = await owned_workspace(db, user_id, workspace_id, lock=True)
    if workspace.status != WorkspaceStatus.ACTIVE:
        raise HTTPException(409, "Workspace is archived")
    await require_upload_attestation(db, user_id)
    # The reservation commit released the workspace lock: recheck a racing upload.
    duplicate = await db.scalar(
        select(PropertyDocument).where(
            PropertyDocument.workspace_id == workspace_id,
            PropertyDocument.sha256 == digest,
            PropertyDocument.status != DocumentStatus.DELETED,
        )
    )
    if duplicate is not None:
        await db.delete(reservation)
        await db.commit()
        return duplicate, False
    name = sanitize_filename(filename)
    document = PropertyDocument(
        workspace_id=workspace_id,
        original_filename=name,
        media_type="application/pdf",
        size_bytes=len(content),
        sha256=digest,
        document_kind=kind,
        status=DocumentStatus.UPLOADED,
        safety_reason="pending",
        storage_key=key,
    )
    try:
        storage.put(key, content)
        db.add(document)
        transition(document, DocumentStatus.SCANNING)
        outcome = await pipeline.inspect(name, content)
        transition(document, outcome.status)
        document.safety_reason = outcome.reason
        if document.status == DocumentStatus.REJECTED:
            # Rejected content is never retained; keep only its private metadata.
            storage.delete(key)
        await db.execute(delete(ObjectDeletionTask).where(ObjectDeletionTask.storage_key == key))
        await db.commit()
    except BaseException:
        await db.rollback()
        # The durable reservation survives failure of this best-effort cleanup.
        try:
            storage.delete(key)
        except OSError:
            pass
        raise
    return document, True
