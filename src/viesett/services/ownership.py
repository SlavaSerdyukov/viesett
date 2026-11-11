from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from viesett.db.models import Account, PropertyDocument, PropertyWorkspace
from viesett.domain.types import DocumentStatus


async def owned_workspace(
    db: AsyncSession,
    user_id: UUID,
    workspace_id: UUID,
    *,
    lock: bool = False,
) -> PropertyWorkspace:
    query = (
        select(PropertyWorkspace)
        .join(Account)
        .where(
            PropertyWorkspace.id == workspace_id,
            PropertyWorkspace.owner_user_id == user_id,
        )
    )
    if lock:
        # A prior commit may have released the lock while expire_on_commit=False
        # retained stale status in the identity map. Refresh from the locked row.
        query = query.with_for_update().execution_options(populate_existing=True)
    workspace = await db.scalar(query)
    if workspace is None:
        raise HTTPException(404, "Not found")
    return workspace


async def owned_document(
    db: AsyncSession,
    user_id: UUID,
    workspace_id: UUID,
    document_id: UUID,
) -> PropertyDocument:
    await owned_workspace(db, user_id, workspace_id)
    document = await db.scalar(
        select(PropertyDocument).where(
            PropertyDocument.id == document_id,
            PropertyDocument.workspace_id == workspace_id,
            PropertyDocument.status != DocumentStatus.DELETED,
        )
    )
    if document is None:
        raise HTTPException(404, "Not found")
    return document
