import hashlib
import json
from datetime import date
from uuid import UUID

from pydantic import JsonValue
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from viesett.coownership.catalog import CATALOG
from viesett.coownership.context import CrossDocumentContext, Document, Fact
from viesett.coownership.engine import evaluate
from viesett.db.coownership_models import (
    CoOwnershipEvaluation,
    CoOwnershipIdentityRecord,
    PlannedWorkRecord,
)
from viesett.db.intelligence_models import DocumentAnalysis
from viesett.db.models import EvidenceItem, Finding, PropertyDocument, utcnow
from viesett.domain.coownership import (
    CO_EVALUATION_VERSION,
    CO_KINDS,
    EXPOSURE_VERSION,
    QUESTIONS_VERSION,
    CoSnapshot,
)
from viesett.domain.intelligence import ExtractedField, ExtractionStatus
from viesett.domain.schemas import FindingCreate, FindingProvenance
from viesett.domain.types import Authority, DocumentStatus
from viesett.services.due_diligence import current_evaluation_date
from viesett.services.evidence import record_finding
from viesett.services.ownership import owned_workspace
from viesett.services.property_snapshot import snapshot


async def refresh_coownership(
    db: AsyncSession, user: UUID, workspace_id: UUID, evaluation_date: date | None = None
) -> CoSnapshot:
    await owned_workspace(db, user, workspace_id, lock=True)
    when = evaluation_date or current_evaluation_date()
    property = await snapshot(db, workspace_id, user)
    sources = list(
        (
            await db.scalars(
                select(PropertyDocument)
                .where(
                    PropertyDocument.workspace_id == workspace_id,
                    PropertyDocument.status == DocumentStatus.READY,
                )
                .order_by(PropertyDocument.id)
            )
        ).all()
    )
    superseded = {d.supersedes_document_id for d in sources if d.supersedes_document_id}
    runs = list(
        (
            await db.scalars(
                select(DocumentAnalysis)
                .where(DocumentAnalysis.workspace_id == workspace_id)
                .order_by(DocumentAnalysis.generation.desc())
            )
        ).all()
    )
    current_evidence = {
        str(e.id): e
        for e in (
            await db.scalars(
                select(EvidenceItem).where(
                    EvidenceItem.workspace_id == workspace_id,
                    EvidenceItem.superseded_at.is_(None),
                    EvidenceItem.authority == Authority.DOCUMENTED,
                )
            )
        ).all()
    }
    documents = []
    for source in sources:
        if source.id in superseded:
            continue
        run = next((r for r in runs if r.document_id == source.id), None)
        if run is None or run.status != ExtractionStatus.READY:
            continue
        fields = []
        for raw, eid in zip(run.fields, run.evidence_ids, strict=True):
            evidence = current_evidence.get(eid)
            if evidence is None or evidence.document_id != source.id:
                continue
            field = ExtractedField.model_validate(raw)
            # Only persisted normalized observations from this analysis, not hints.
            if evidence.typed_value.get("value") != field.value:
                continue
            fields.append(Fact(field, evidence.id))
        documents.append(
            Document(
                source.id,
                run.effective_classification,
                tuple(fields),
                str(run.co_metadata.get("parse_status", "PARTIALLY_PARSED"))
                if run.co_metadata
                else "PARSED",
                source.sha256,
            )
        )
    payload: dict[str, JsonValue] = {
        "evaluation_version": CO_EVALUATION_VERSION,
        "exposure_version": EXPOSURE_VERSION,
        "question_generator_version": QUESTIONS_VERSION,
        "evaluation_date": when.isoformat(),
        "property": {
            "identity_revision": property.identity_revision,
            "stale": property.stale,
            "resolution_status": property.resolution_status,
            "address": property.address.model_dump(
                mode="json", exclude={"retrieved_at", "native_geometry"}
            )
            if property.address
            else None,
            "parcels": [
                {"official_id": p.official_id, "capakey": p.capakey} for p in property.parcels
            ],
        },
        "documents": [
            {
                "id": str(d.id),
                "kind": d.kind.value,
                "parse_status": d.parse_status,
                "sha256": d.source_sha256,
                "fields": [
                    {"field": f.field.model_dump(mode="json"), "evidence_id": str(f.evidence_id)}
                    for f in d.fields
                ],
            }
            for d in documents
        ],
        "checks": [c.model_dump(mode="json") for c in CATALOG.values()],
    }
    fingerprint = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    previous = await db.scalar(
        select(CoOwnershipEvaluation)
        .where(CoOwnershipEvaluation.workspace_id == workspace_id)
        .order_by(CoOwnershipEvaluation.created_at.desc(), CoOwnershipEvaluation.id.desc())
        .limit(1)
    )
    if previous and previous.input_hash == fingerprint:
        await db.commit()
        return CoSnapshot.model_validate(previous.result)
    result = evaluate(
        CrossDocumentContext(workspace_id, when, property, tuple(documents)), fingerprint
    )
    row = CoOwnershipEvaluation(
        workspace_id=workspace_id,
        evaluation_date=when,
        input_hash=fingerprint,
        identity_revision=property.identity_revision,
        result={},
        inputs=payload,
    )
    db.add(row)
    await db.flush()
    result.evaluation_id = row.id
    await db.execute(
        delete(CoOwnershipIdentityRecord).where(
            CoOwnershipIdentityRecord.workspace_id == workspace_id
        )
    )
    if result.identity:
        db.add(
            CoOwnershipIdentityRecord(
                workspace_id=workspace_id,
                evaluation_id=row.id,
                **result.identity.model_dump(mode="json"),
            )
        )
    for current in (
        await db.scalars(
            select(PlannedWorkRecord).where(
                PlannedWorkRecord.workspace_id == workspace_id,
                PlannedWorkRecord.superseded_at.is_(None),
            )
        )
    ).all():
        current.superseded_at = utcnow()
    for work in result.planned_works:
        db.add(
            PlannedWorkRecord(
                workspace_id=workspace_id,
                evaluation_id=row.id,
                work_key=work.key,
                decision_status=work.decision_status.value,
                result=work.model_dump(mode="json"),
            )
        )
    for finding in (
        await db.scalars(
            select(Finding).where(
                Finding.workspace_id == workspace_id,
                Finding.resolved_at.is_(None),
            )
        )
    ).all():
        if finding.provenance.get("source") == "viesett.coownership":
            finding.resolved_at = utcnow()
    for conclusion in result.cross_document_findings:
        await record_finding(
            db,
            user,
            workspace_id,
            FindingCreate(
                code=conclusion.code,
                severity=conclusion.severity,
                summary=conclusion.summary,
                details=conclusion.reason,
                evidence_ids=conclusion.evidence_ids[:100],
                provenance=FindingProvenance(
                    method="deterministic",
                    source="viesett.coownership",
                    version=conclusion.check.version,
                    rule_code=conclusion.check.code,
                    evaluation_id=row.id,
                    evaluation_date=when,
                    input_hash=fingerprint,
                    category=conclusion.check.category,
                    check_description=conclusion.check.description,
                    severity_policy=conclusion.check.severity_policy,
                    reviewed_at=conclusion.check.reviewed_at,
                    effective_from=conclusion.check.effective_from,
                    effective_to=conclusion.check.effective_to,
                    jurisdiction="BE",
                    official_source_reference=conclusion.check.official_source,
                    official_source_name="Belgian Civil Code Book 3"
                    if conclusion.check.official_source
                    else None,
                ),
            ),
        )
    row.result = result.model_dump(mode="json")
    await db.commit()
    return result


async def refresh_if_present(
    db: AsyncSession, user: UUID, workspace_id: UUID, evaluation_date: date | None = None
) -> CoSnapshot | None:
    exists = await db.scalar(
        select(DocumentAnalysis.id)
        .where(
            DocumentAnalysis.workspace_id == workspace_id,
            DocumentAnalysis.effective_classification.in_(CO_KINDS),
        )
        .limit(1)
    )
    if exists is None:
        exists = await db.scalar(
            select(CoOwnershipEvaluation.id)
            .where(CoOwnershipEvaluation.workspace_id == workspace_id)
            .limit(1)
        )
    if exists is not None:
        return await refresh_coownership(db, user, workspace_id, evaluation_date)
    return None
