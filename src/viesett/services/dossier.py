from collections import Counter
from hashlib import sha256
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Executable

from viesett.db.intelligence_models import DocumentAnalysis
from viesett.db.models import EvidenceItem, PropertyDocument
from viesett.db.product_models import DemoWorkspace
from viesett.db.property_models import PropertyResolution, PublicEnrichmentRun
from viesett.document_intelligence.association import associate
from viesett.domain.coownership import CoSnapshot
from viesett.domain.intelligence import ExtractedField, Requirement
from viesett.domain.product import (
    CitationResponse,
    CompletenessResponse,
    CoOwnershipSummaryResponse,
    DocumentSummaryResponse,
    DossierSnapshotResponse,
    EvidenceResponse,
    FindingResponse,
    PropertyView,
    QuestionResponse,
)
from viesett.domain.schemas import WorkspaceOut
from viesett.domain.types import DocumentStatus
from viesett.services.coownership import refresh_if_present
from viesett.services.due_diligence import refresh_due_diligence
from viesett.services.evidence import list_findings
from viesett.services.ownership import owned_workspace
from viesett.services.property_snapshot import snapshot
from viesett.services.transaction_context import answers, missing_questions

GROUPS = [
    ("EPC", "Energy"),
    ("ASBESTOS", "Asbestos"),
    ("ELECTRICAL", "Electrical"),
    ("SOIL", "Soil"),
    ("CO_", "Co-ownership"),
    ("RESERVE", "Co-ownership"),
    ("CAPITAL", "Co-ownership"),
    ("AGM", "Co-ownership"),
    ("ARTICLE", "Co-ownership"),
    ("SHARE", "Co-ownership"),
    ("ADDRESS", "Property identity"),
    ("UNIT", "Property identity"),
    ("PARCEL", "Property identity"),
]


def completeness(
    requirements: list[Requirement], co: CoSnapshot | None, *, in_progress: bool = False
) -> CompletenessResponse:
    applicable = [r for r in requirements if r.applicability == "REQUIRED"]
    done = sum(r.presence == "PRESENT" and r.validity_status != "EXPIRED" for r in applicable)
    total = len(applicable)
    conditional = sum(r.applicability in {"CONDITIONAL", "UNKNOWN"} for r in requirements)
    if co and co.co_ownership_status != "NOT_ESTABLISHED":
        components = [c for c in co.article_3_94_completeness if c.status != "NOT_APPLICABLE"]
        total += len(components)
        done += sum(c.status in {"PRESENT", "EXPLICIT_NONE"} for c in components)
    state = (
        "IN_PROGRESS"
        if in_progress
        else "BLOCKED_BY_MISSING_DATA"
        if total == 0
        else "COMPLETE"
        if done == total and conditional == 0
        else "INCOMPLETE"
    )
    return CompletenessResponse(
        state=state,
        completed_count=done,
        applicable_count=total,
        percentage=round(done * 100 / total) if total else None,
        conditional_count=conditional,
    )


def finding_group(code: str) -> str:
    if "CONSISTENCY" in code or "_VS_" in code:
        return "Consistency"
    return next((group for marker, group in GROUPS if marker in code), "Documents")


def fact_label(key: str) -> str:
    return (
        key.removeprefix("document.")
        .removeprefix("property.")
        .replace("_", " ")
        .replace(".", " · ")
    )


async def source_signature(db: AsyncSession, workspace_id: UUID) -> str:
    statements: list[Executable] = [
        select(
            PropertyDocument.id, PropertyDocument.status, PropertyDocument.supersedes_document_id
        )
        .where(PropertyDocument.workspace_id == workspace_id)
        .order_by(PropertyDocument.id),
        select(DocumentAnalysis.document_id, DocumentAnalysis.id, DocumentAnalysis.status)
        .where(DocumentAnalysis.workspace_id == workspace_id)
        .distinct(DocumentAnalysis.document_id)
        .order_by(DocumentAnalysis.document_id, DocumentAnalysis.generation.desc()),
        select(EvidenceItem.id)
        .where(EvidenceItem.workspace_id == workspace_id, EvidenceItem.superseded_at.is_(None))
        .order_by(EvidenceItem.id),
        select(PropertyResolution.id, PropertyResolution.status)
        .where(PropertyResolution.workspace_id == workspace_id)
        .order_by(PropertyResolution.generation.desc())
        .limit(1),
        select(PublicEnrichmentRun.id)
        .where(PublicEnrichmentRun.workspace_id == workspace_id)
        .order_by(PublicEnrichmentRun.attempted_at.desc(), PublicEnrichmentRun.id.desc())
        .limit(1),
    ]
    digest = sha256()
    for statement in statements:
        digest.update(str((await db.execute(statement)).all()).encode())
    return digest.hexdigest()


async def dossier(db: AsyncSession, user: UUID, workspace_id: UUID) -> DossierSnapshotResponse:
    # Existing refresh services are idempotent and hold workspace locks. Recheck
    # their input hashes under the final read lock to avoid composing generations.
    for _ in range(3):
        await owned_workspace(db, user, workspace_id, lock=True)
        before = await source_signature(db, workspace_id)
        await db.commit()
        due = await refresh_due_diligence(db, user, workspace_id)
        co = await refresh_if_present(db, user, workspace_id)
        workspace = await owned_workspace(db, user, workspace_id, lock=True)
        prop = await snapshot(db, workspace_id, user)
        unchanged = before == await source_signature(db, workspace_id)
        if (
            unchanged
            and prop.identity_revision == due.identity_revision
            and (co is None or co.identity_revision == prop.identity_revision)
        ):
            break
    else:
        from fastapi import HTTPException

        raise HTTPException(409, "Dossier changed; refresh again")
    docs = list(
        (
            await db.scalars(
                select(PropertyDocument)
                .where(
                    PropertyDocument.workspace_id == workspace_id,
                    PropertyDocument.status != DocumentStatus.DELETED,
                )
                .order_by(PropertyDocument.created_at.desc(), PropertyDocument.id)
                .limit(101)
            )
        ).all()
    )
    truncated = len(docs) > 100
    docs = docs[:100]
    raw_findings = await list_findings(db, [workspace_id], current_only=True, limit=201)
    # One latest analysis per document, no full analysis/evidence history in response.
    query = (
        select(DocumentAnalysis)
        .where(DocumentAnalysis.workspace_id == workspace_id)
        .distinct(DocumentAnalysis.document_id)
        .order_by(DocumentAnalysis.document_id, DocumentAnalysis.generation.desc())
    )
    runs = {r.document_id: r for r in (await db.scalars(query)).all()}
    count = (
        await db.scalar(
            select(func.count())
            .select_from(EvidenceItem)
            .where(EvidenceItem.workspace_id == workspace_id, EvidenceItem.superseded_at.is_(None))
        )
        or 0
    )
    evidence = list(
        (
            await db.scalars(
                select(EvidenceItem)
                .where(
                    EvidenceItem.workspace_id == workspace_id, EvidenceItem.superseded_at.is_(None)
                )
                .order_by(EvidenceItem.created_at, EvidenceItem.id)
                .limit(500)
            )
        ).all()
    )
    by_evidence = {e.id: e for e in evidence}
    # Bound the facts page without losing sources for claims using later rows.
    reference_ids = {eid for f in raw_findings[:200] for eid in f.evidence_ids}
    if co:

        def collect(value: object) -> None:
            if isinstance(value, dict):
                for key, item in value.items():
                    if key in {"evidence_ids", "source_evidence_ids"} and isinstance(item, list):
                        reference_ids.update(UUID(str(eid)) for eid in item)
                    elif isinstance(item, (list, dict)):
                        collect(item)
            elif isinstance(value, list):
                for item in value:
                    collect(item)

        collect(co.model_dump(mode="json"))
    if reference_ids - by_evidence.keys():
        extra = list(
            (
                await db.scalars(
                    select(EvidenceItem)
                    .where(
                        EvidenceItem.workspace_id == workspace_id,
                        EvidenceItem.id.in_(reference_ids - by_evidence.keys()),
                        EvidenceItem.superseded_at.is_(None),
                    )
                    .order_by(EvidenceItem.id)
                    .limit(5001)
                )
            ).all()
        )
        truncated |= len(extra) > 5000
        by_evidence.update({e.id: e for e in extra[:5000]})
    source_documents = {
        d.id: d
        for d in (
            await db.scalars(
                select(PropertyDocument).where(
                    PropertyDocument.workspace_id == workspace_id,
                    PropertyDocument.id.in_(
                        {e.document_id for e in by_evidence.values() if e.document_id}
                    ),
                )
            )
        ).all()
    }

    def citations(eids: list[UUID]) -> list[CitationResponse]:
        values: dict[str, CitationResponse] = {}
        for eid in eids:
            e = by_evidence.get(eid)
            if not e:
                continue
            document = source_documents.get(e.document_id) if e.document_id else None
            raw_page = e.source_locator.get("page")
            page = int(raw_page) if isinstance(raw_page, int) and raw_page > 0 else None
            source = CitationResponse(
                label=document.original_filename
                if document
                else "Official Flemish register"
                if e.authority == "OFFICIAL"
                else "Buyer-provided transaction detail — unverified"
                if e.authority == "UNVERIFIED"
                else "Derived information",
                document_id=document.id if document else None,
                page=page,
                uri=None if document else e.source_uri,
                retrieved_at=e.source_retrieved_at or e.observed_at,
            )
            values[source.model_dump_json()] = source
        return sorted(
            values.values(),
            key=lambda source: (
                str(source.document_id or ""),
                source.page or 0,
                source.uri or "",
                source.label,
            ),
        )

    summaries = []
    for d in docs:
        r = runs.get(d.id)
        state = (
            "SAFETY_REVIEW"
            if d.status != "READY"
            else r.status.value
            if r and r.status != "READY"
            else "UNKNOWN"
            if r and r.effective_classification == "UNKNOWN"
            else "ANALYZED"
            if r
            else "NOT_ANALYZED"
        )
        if r and r.status == "READY" and r.co_metadata:
            parsed = str(r.co_metadata.get("parse_status", "PARSED"))
            if parsed in {"PARTIALLY_PARSED", "UNSUPPORTED_LAYOUT", "UNPARSEABLE"}:
                state = parsed
        assoc = (
            associate([ExtractedField.model_validate(f) for f in r.fields], prop).status
            if r
            else "UNVERIFIED"
        )
        if co:
            match = next((a for a in co.associations if a.document_id == d.id), None)
            if match:
                assoc = match.status
        safe_fields = [
            f
            for f in (r.fields if r else [])
            if f.get("key")
            in {
                "document.epc.label",
                "document.epc.score",
                "document.electrical.conclusion",
                "document.asbestos.conclusion",
                "document.soil.attestation_date",
            }
        ]
        summaries.append(
            DocumentSummaryResponse(
                id=d.id,
                processing_since=r.created_at if r else d.created_at,
                filename=d.original_filename,
                kind=r.effective_classification.value if r else d.document_kind.value,
                status=state,
                association=str(assoc),
                created_at=d.created_at,
                analysis_id=r.id if r else None,
                summary=[fact_label(str(f["key"])) + ": " + str(f["value"]) for f in safe_fields],
                can_view=d.status == "READY",
                can_retry=d.status == "READY" and bool(r and r.retry_eligible),
            )
        )
    findings = []
    questions = []
    for f in raw_findings[:200]:
        group = finding_group(f.code)
        role = "NOTARY" if group == "Co-ownership" else "SELLER"
        conclusion = next(
            (
                c
                for c in (co.cross_document_findings if co else [])
                if c.code == f.code and c.summary == f.summary
            ),
            None,
        )
        question = next(
            (q for q in (co.questions if co else []) if conclusion and q.key == conclusion.key),
            None,
        )
        next_step = (
            question.question_text if question else f"Clarify with the {role.lower()}: " + f.summary
        )
        sources = citations(f.evidence_ids)
        if f.provenance.official_source_reference:
            sources.append(
                CitationResponse(
                    label=f.provenance.official_source_name or "Reviewed rule source",
                    uri=f.provenance.official_source_reference,
                )
            )
        findings.append(
            FindingResponse(
                id=f.id,
                code=f.code,
                group=group,
                severity=f.severity,
                title=f.summary,
                explanation=f.details or "Review the available source information.",
                next_step=next_step,
                sources=sources,
                rule_version=f.provenance.version,
            )
        )
        if not question and f.severity != "INFO":
            questions.append(
                QuestionResponse(
                    key=str(f.id),
                    target_role=role,
                    question_text=next_step,
                    reason=f.details or f.summary,
                    sources=sources,
                )
            )
    if co:
        questions.extend(
            QuestionResponse(
                key=q.key,
                target_role=q.target_role,
                question_text=q.question_text,
                reason=q.reason,
                sources=citations(q.evidence_ids),
            )
            for q in co.questions
        )
    is_demo = await db.get(DemoWorkspace, workspace_id) is not None
    co_summary = None
    if co:
        payload = co.model_dump(include=set(CoOwnershipSummaryResponse.model_fields))
        for key in (
            "planned_works",
            "capital_calls",
            "pending_litigation",
            "financial_exposure_estimates",
        ):
            rows = payload[key]
            if len(rows) > 100:
                truncated = True
                payload[key] = rows[:100]
        co_summary = CoOwnershipSummaryResponse.model_validate(payload)
    result = DossierSnapshotResponse(
        workspace=WorkspaceOut.model_validate(workspace).model_copy(update={"is_demo": is_demo}),
        is_demo=is_demo,
        property=PropertyView(
            status=prop.resolution_status or "NOT_RESOLVED",
            query=prop.latest_input_address_query,
            address=prop.address.canonical_address if prop.address else workspace.canonical_address,
            address_id=prop.address.official_id if prop.address else None,
            box=prop.address.box_number if prop.address else None,
            unit_id=prop.selected_building_unit.official_id
            if prop.selected_building_unit
            else None,
            parcels=[p.capakey for p in prop.parcels],
            last_refreshed=prop.last_successful_retrieval,
            stale=prop.stale,
            flood=prop.flood,
            heritage=prop.heritage[:100],
            sources=prop.sources,
            source_states=prop.source_states,
        ),
        completeness=completeness(
            due.requirements,
            co,
            in_progress=any(d.status in {"PENDING", "IN_PROGRESS"} for d in summaries),
        ),
        requirements=due.requirements,
        documents=summaries,
        findings=findings,
        findings_summary=dict(Counter(f.severity.value for f in findings)),
        co_ownership=co_summary,
        questions=questions,
        evidence=[
            EvidenceResponse(
                id=e.id,
                label=fact_label(e.key),
                value=str(e.typed_value.get("value", "")),
                authority=e.authority,
                date=e.observed_at,
                effective_date=e.source_locator.get("effective_date"),
                sources=citations([e.id]),
            )
            for e in evidence
        ],
        evidence_total=count,
        truncated=truncated or count > 500 or len(raw_findings) > 200,
        evaluation_date=due.evaluation_date,
        context_questions=missing_questions(due),
        context_answers=await answers(db, workspace_id, prop.identity_revision),
        last_updated=max(
            [workspace.updated_at, due.created_at]
            + [d.created_at for d in docs]
            + [r.completed_at or r.created_at for r in runs.values()]
            + [s.last_attempt_at for s in prop.source_states if s.last_attempt_at]
        ),
    )
    await db.commit()
    return result
