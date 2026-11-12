from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from viesett.db.models import EvidenceItem, Finding, FindingEvidence, PropertyDocument
from viesett.domain.schemas import EvidenceCreate, FindingCreate, FindingOut
from viesett.domain.types import DocumentStatus
from viesett.services.ownership import owned_workspace


async def record_evidence(
    db: AsyncSession,
    user_id: UUID,
    workspace_id: UUID,
    data: EvidenceCreate,
) -> EvidenceItem:
    """Append-only evidence: there is deliberately no update/overwrite operation."""
    await owned_workspace(db, user_id, workspace_id, lock=True)
    if data.document_id is not None:
        document = await db.scalar(
            select(PropertyDocument).where(
                PropertyDocument.id == data.document_id,
                PropertyDocument.workspace_id == workspace_id,
                PropertyDocument.status == DocumentStatus.READY,
            )
        )
        if document is None:
            raise HTTPException(409, "Evidence requires a ready document in this workspace")
    item = EvidenceItem(workspace_id=workspace_id, **data.model_dump(mode="json"))
    # JSON serialization is used only for structured values, not UUID/datetime columns.
    item.document_id = data.document_id
    item.observed_at = data.observed_at
    db.add(item)
    await db.flush()
    return item


async def record_finding(
    db: AsyncSession,
    user_id: UUID,
    workspace_id: UUID,
    data: FindingCreate,
) -> Finding:
    await owned_workspace(db, user_id, workspace_id, lock=True)
    ids = set(data.evidence_ids)
    available = set(
        (
            await db.scalars(
                select(EvidenceItem.id).where(
                    EvidenceItem.workspace_id == workspace_id,
                    EvidenceItem.id.in_(ids),
                )
            )
        ).all()
    )
    if ids != available:
        raise HTTPException(409, "Finding evidence must belong to this workspace")
    finding = Finding(
        workspace_id=workspace_id, **data.model_dump(mode="json", exclude={"evidence_ids"})
    )
    db.add(finding)
    await db.flush()
    db.add_all(
        [
            FindingEvidence(finding_id=finding.id, evidence_id=item_id, workspace_id=workspace_id)
            for item_id in ids
        ]
    )
    await db.flush()
    return finding


async def list_findings(
    db: AsyncSession,
    workspace_ids: list[UUID],
    *,
    current_only: bool = False,
    limit: int | None = None,
) -> list[FindingOut]:
    query = select(Finding).where(Finding.workspace_id.in_(workspace_ids))
    if current_only:
        query = query.where(Finding.resolved_at.is_(None))
    query = query.order_by(Finding.created_at, Finding.id)
    if limit is not None:
        query = query.limit(limit)
    findings = (await db.scalars(query)).all()
    links = (
        await db.execute(
            select(FindingEvidence.finding_id, FindingEvidence.evidence_id).where(
                FindingEvidence.workspace_id.in_(workspace_ids),
                FindingEvidence.finding_id.in_([f.id for f in findings]),
            )
        )
    ).all()
    return [
        FindingOut(
            id=f.id,
            workspace_id=f.workspace_id,
            code=f.code,
            severity=f.severity,
            summary=f.summary,
            details=f.details,
            provenance=f.provenance,
            evidence_ids=[evidence_id for finding_id, evidence_id in links if finding_id == f.id],
            created_at=f.created_at,
            resolved_at=f.resolved_at,
        )
        for f in findings
    ]
