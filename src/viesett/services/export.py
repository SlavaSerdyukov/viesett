from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from viesett.db.intelligence_models import DocumentAnalysis, DueDiligenceEvaluation
from viesett.db.models import (
    Account,
    DocumentRequestDraft,
    EvidenceItem,
    PropertyDocument,
    PropertyWorkspace,
)
from viesett.db.property_models import PropertyResolution, PublicEnrichmentRun
from viesett.domain.intelligence import AnalysisOut, EvaluationOut
from viesett.domain.property import SourceRunOut
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
from viesett.services.property_snapshot import resolution_out, snapshot


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
        document_analyses=[
            AnalysisOut.model_validate(row)
            for row in (
                await db.scalars(
                    select(DocumentAnalysis)
                    .where(DocumentAnalysis.workspace_id.in_(ids))
                    .order_by(DocumentAnalysis.created_at)
                )
            ).all()
        ],
        due_diligence_evaluations=[
            EvaluationOut.model_validate(row)
            for row in (
                await db.scalars(
                    select(DueDiligenceEvaluation)
                    .where(DueDiligenceEvaluation.workspace_id.in_(ids))
                    .order_by(DueDiligenceEvaluation.created_at)
                )
            ).all()
        ],
        account=AccountOut.model_validate(account),
        policy_acknowledgements=await acknowledgements(db, user_id),
        workspaces=[WorkspaceOut.model_validate(w) for w in workspaces],
        documents=[DocumentOut.model_validate(d) for d in documents],
        evidence=[EvidenceOut.model_validate(e) for e in evidence],
        findings=await list_findings(db, ids),
        document_request_drafts=[DraftOut.model_validate(d) for d in drafts],
        property_resolutions=[
            resolution_out(row)
            for row in (
                await db.scalars(
                    select(PropertyResolution)
                    .where(PropertyResolution.workspace_id.in_(ids))
                    .order_by(
                        PropertyResolution.workspace_id,
                        PropertyResolution.generation,
                    )
                )
            ).all()
        ],
        property_snapshots=[await snapshot(db, workspace_id, user_id) for workspace_id in ids],
        public_enrichment_runs=[
            SourceRunOut.model_validate(row)
            for row in (
                await db.scalars(
                    select(PublicEnrichmentRun)
                    .where(PublicEnrichmentRun.workspace_id.in_(ids))
                    .order_by(
                        PublicEnrichmentRun.attempted_at,
                    )
                )
            ).all()
        ],
    )
