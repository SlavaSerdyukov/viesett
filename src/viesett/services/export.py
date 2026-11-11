from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from viesett.db.models import (
    Account,
    DocumentRequestDraft,
    EvidenceItem,
    PropertyDocument,
    PropertyWorkspace,
)
from viesett.domain.schemas import (
    AccountOut,
    DocumentOut,
    DraftOut,
    EvidenceOut,
    ExportOut,
    WorkspaceOut,
)
from viesett.domain.types import DocumentStatus
from viesett.services.evidence import list_findings
from viesett.services.policies import acknowledgements


async def export_user(db: AsyncSession, user_id: UUID) -> ExportOut:
    account = await db.get(Account, user_id)
    if account is None:
        raise HTTPException(404, "Not found")
    workspaces = (
        await db.scalars(
            select(PropertyWorkspace)
            .where(
                PropertyWorkspace.owner_user_id == user_id,
            )
            .order_by(PropertyWorkspace.created_at)
        )
    ).all()
    ids = [workspace.id for workspace in workspaces]
    documents = (
        await db.scalars(
            select(PropertyDocument).where(
                PropertyDocument.workspace_id.in_(ids),
                PropertyDocument.status != DocumentStatus.DELETED,
            )
        )
    ).all()
    evidence = (
        await db.scalars(
            select(EvidenceItem).where(
                EvidenceItem.workspace_id.in_(ids),
            )
        )
    ).all()
    drafts = (
        await db.scalars(
            select(DocumentRequestDraft).where(
                DocumentRequestDraft.workspace_id.in_(ids),
            )
        )
    ).all()
    return ExportOut(
        account=AccountOut.model_validate(account),
        policy_acknowledgements=await acknowledgements(db, user_id),
        workspaces=[WorkspaceOut.model_validate(w) for w in workspaces],
        documents=[DocumentOut.model_validate(d) for d in documents],
        evidence=[EvidenceOut.model_validate(e) for e in evidence],
        findings=await list_findings(db, ids),
        document_request_drafts=[DraftOut.model_validate(d) for d in drafts],
    )
