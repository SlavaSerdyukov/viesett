import hashlib
import json
from datetime import date, datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from pydantic import JsonValue
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from viesett.db.intelligence_models import DocumentAnalysis, DueDiligenceEvaluation
from viesett.db.models import EvidenceItem, Finding, PropertyDocument, utcnow
from viesett.document_intelligence.association import associate
from viesett.domain.intelligence import (
    AnalysisKind,
    AssociationStatus,
    EvaluationOut,
    ExtractedField,
    ExtractionStatus,
)
from viesett.domain.schemas import FindingCreate, FindingProvenance
from viesett.domain.types import Authority, DocumentStatus
from viesett.rules.catalog import CATALOG
from viesett.rules.engine import DocumentInput, Fact, RuleContext, evaluate
from viesett.services.evidence import record_finding
from viesett.services.ownership import owned_workspace
from viesett.services.property_snapshot import snapshot


def current_evaluation_date() -> date:
    return datetime.now(ZoneInfo("Europe/Brussels")).date()


async def refresh_due_diligence(
    db: AsyncSession, user: UUID, workspace_id: UUID, evaluation_date: date | None = None
) -> EvaluationOut:
    await owned_workspace(db, user, workspace_id, lock=True)
    when = evaluation_date or current_evaluation_date()
    identity = await snapshot(db, workspace_id, user)
    documents = list(
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
    superseded = {d.supersedes_document_id for d in documents if d.supersedes_document_id}
    documents = [d for d in documents if d.id not in superseded]
    runs = list(
        (
            await db.scalars(
                select(DocumentAnalysis)
                .where(
                    DocumentAnalysis.workspace_id == workspace_id,
                )
                .order_by(DocumentAnalysis.generation.desc())
            )
        ).all()
    )
    evidence = list(
        (
            await db.scalars(
                select(EvidenceItem)
                .where(
                    EvidenceItem.workspace_id == workspace_id,
                    EvidenceItem.superseded_at.is_(None),
                )
                .order_by(EvidenceItem.id)
            )
        ).all()
    )
    by_id = {str(e.id): e for e in evidence}
    inputs = []
    for doc in documents:
        latest = next((r for r in runs if r.document_id == doc.id), None)
        if latest is None:
            inputs.append(
                DocumentInput(
                    doc.id,
                    AnalysisKind(doc.document_kind.value)
                    if doc.document_kind.value in AnalysisKind
                    else AnalysisKind.UNKNOWN,
                    ExtractionStatus.PENDING,
                    AssociationStatus.UNVERIFIED,
                    {},
                )
            )
            continue
        fields = [ExtractedField.model_validate(f) for f in latest.fields]
        association = associate(fields, identity)
        grouped: dict[str, list[Fact]] = {}
        valid_ids = []
        for field, eid in zip(fields, latest.evidence_ids, strict=True):
            item = by_id.get(eid)
            if item is None or item.authority != Authority.DOCUMENTED or item.document_id != doc.id:
                continue
            key = field.key.split(".", 2)[2]
            grouped.setdefault(key, []).append(Fact(field.value, (item.id,)))
            valid_ids.append(item.id)
        inputs.append(
            DocumentInput(
                doc.id,
                latest.effective_classification,
                latest.status,
                association.status,
                {key: tuple(values) for key, values in grouped.items()},
                tuple(valid_ids),
            )
        )
    # Regulatory predicates accept explicit trusted facts, never inferred AI or
    # document-type guesses. Future ingestion can supply these stable keys.
    facts: dict[str, Fact] = {}
    matched_docs = {
        d.id
        for d in inputs
        if d.association == AssociationStatus.MATCHED and d.status == ExtractionStatus.READY
    }
    for key in sorted({e.key for e in evidence}):
        if not key.startswith(("property.", "transaction.", "electrical.")):
            continue
        candidates = [
            e
            for e in evidence
            if e.key == key
            and (
                (
                    e.authority == Authority.OFFICIAL
                    and e.provider is not None
                    and not identity.stale
                )
                or (e.authority == Authority.DOCUMENTED and e.document_id in matched_docs)
            )
        ]
        values = {json.dumps(e.typed_value, sort_keys=True) for e in candidates}
        if len(values) == 1:
            raw = candidates[0].typed_value.get("value")
            if key.endswith("_date"):
                if candidates[0].typed_value.get("kind") != "date" or not isinstance(raw, str):
                    continue
                try:
                    date.fromisoformat(raw)
                except ValueError:
                    continue
            if isinstance(raw, (str, int, float, bool)):
                facts[key] = Fact(raw, tuple(e.id for e in candidates))
    context = RuleContext(
        when,
        tuple(inputs),
        frozenset(p.capakey for p in identity.parcels) if not identity.stale else frozenset(),
        facts,
    )
    payload: dict[str, JsonValue] = {
        "evaluation_date": when.isoformat(),
        "identity_revision": identity.identity_revision,
        "identity_stale": identity.stale,
        "resolution_status": identity.resolution_status,
        "parcels": [p for p in sorted(context.parcels)],
        "facts": {
            key: {"value": f.value, "evidence_ids": [str(i) for i in f.evidence_ids]}
            for key, f in facts.items()
        },
        "documents": [
            {
                "id": str(d.id),
                "kind": d.kind.value,
                "status": d.status.value,
                "association": d.association.value,
                "fields": {
                    key: [
                        {"value": f.value, "evidence_ids": [str(i) for i in f.evidence_ids]}
                        for f in values
                    ]
                    for key, values in d.fields.items()
                },
            }
            for d in inputs
        ],
        "rules": [r.model_dump(mode="json") for r in CATALOG.values()],
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    previous = await db.scalar(
        select(DueDiligenceEvaluation)
        .where(
            DueDiligenceEvaluation.workspace_id == workspace_id,
        )
        .order_by(DueDiligenceEvaluation.created_at.desc(), DueDiligenceEvaluation.id.desc())
        .limit(1)
    )
    if previous and previous.input_hash == digest:
        await db.commit()
        return EvaluationOut.model_validate(previous)
    result = evaluate(context)
    run = DueDiligenceEvaluation(
        workspace_id=workspace_id,
        evaluation_date=when,
        input_hash=digest,
        identity_revision=identity.identity_revision,
        requirements=[r.model_dump(mode="json") for r in result.requirements],
        rules=[r.model_dump(mode="json") for r in CATALOG.values()],
        inputs=payload,
        finding_ids=[],
    )
    db.add(run)
    await db.flush()
    previous_findings = list(
        (
            await db.scalars(
                select(Finding).where(
                    Finding.workspace_id == workspace_id,
                    Finding.resolved_at.is_(None),
                )
            )
        ).all()
    )
    for finding in previous_findings:
        if finding.provenance.get("source") == "viesett.rules":
            finding.resolved_at = utcnow()
    ids = []
    for conclusion in result.findings:
        row = await record_finding(
            db,
            user,
            workspace_id,
            FindingCreate(
                code=conclusion.code,
                severity=conclusion.severity,
                summary=conclusion.summary,
                details=conclusion.details,
                evidence_ids=list(conclusion.evidence_ids[:100]),
                provenance=FindingProvenance(
                    method="deterministic",
                    source="viesett.rules",
                    version=conclusion.rule.version,
                    rule_code=conclusion.rule.code,
                    evaluation_id=run.id,
                    evaluation_date=when,
                    input_hash=digest,
                    jurisdiction=conclusion.rule.jurisdiction,
                    effective_from=conclusion.rule.effective_from,
                    effective_to=conclusion.rule.effective_to,
                    reviewed_at=conclusion.rule.reviewed_at,
                    official_source_name=conclusion.rule.official_source_name,
                    official_source_reference=conclusion.rule.official_source_reference,
                ),
            ),
        )
        ids.append(str(row.id))
    run.finding_ids = ids
    await db.commit()
    return EvaluationOut.model_validate(run)
