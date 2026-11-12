import hashlib
from datetime import timedelta
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from viesett.core.config import Settings
from viesett.db.intelligence_models import DocumentAnalysis, DocumentTextArtifact
from viesett.db.models import EvidenceItem, ObjectDeletionTask, utcnow
from viesett.document_intelligence.association import associate
from viesett.document_intelligence.classification import classify
from viesett.document_intelligence.extractors import VERSIONS, extract_fields
from viesett.document_intelligence.pdf import ExtractionFailure, PdfLimits, extract_isolated
from viesett.domain.intelligence import (
    AnalysisKind,
    AnalysisOut,
    AnalysisReport,
    AnalyzeRequest,
    Association,
    Classification,
    ExtractionStatus,
)
from viesett.domain.schemas import EvidenceCreate, SourceLocator, TypedValue
from viesett.domain.types import (
    Authority,
    DocumentKind,
    DocumentStatus,
    SourceType,
    WorkspaceStatus,
)
from viesett.services.evidence import record_evidence
from viesett.services.ownership import owned_document, owned_workspace
from viesett.services.property_snapshot import snapshot
from viesett.storage.private import PrivateObjectStorage


async def analyses(
    db: AsyncSession, workspace_id: UUID, document_id: UUID
) -> list[DocumentAnalysis]:
    return list(
        (
            await db.scalars(
                select(DocumentAnalysis)
                .where(
                    DocumentAnalysis.workspace_id == workspace_id,
                    DocumentAnalysis.document_id == document_id,
                )
                .order_by(DocumentAnalysis.generation.desc())
            )
        ).all()
    )


async def analysis_report(
    db: AsyncSession, user: UUID, workspace_id: UUID, document_id: UUID, history: bool = False
) -> AnalysisReport:
    await owned_document(db, user, workspace_id, document_id)
    rows = await analyses(db, workspace_id, document_id)
    if not rows:
        raise HTTPException(404, "Not found")
    return AnalysisReport(
        current=AnalysisOut.model_validate(rows[0]),
        history=[AnalysisOut.model_validate(row) for row in rows[1:]] if history else [],
    )


async def analyze_document(
    db: AsyncSession,
    user: UUID,
    workspace_id: UUID,
    document_id: UUID,
    request: AnalyzeRequest,
    config: Settings,
    storage: PrivateObjectStorage,
) -> AnalysisOut:
    from viesett.services.due_diligence import refresh_due_diligence

    workspace = await owned_workspace(db, user, workspace_id, lock=True)
    document = await owned_document(db, user, workspace_id, document_id)
    if workspace.status != WorkspaceStatus.ACTIVE or document.status != DocumentStatus.READY:
        raise HTTPException(409, "Analysis requires an active workspace and a ready document")
    previous = await analyses(db, workspace_id, document_id)
    latest = previous[0] if previous else None
    manual = (
        request.manual_kind
        if request.manual_kind is not None
        else (latest.manual_classification if latest else None)
    )
    if (
        latest
        and latest.status == ExtractionStatus.READY
        and latest.source_sha256 == document.sha256
        and latest.manual_classification == manual
        and latest.parser_version == VERSIONS[latest.effective_classification]
    ):
        await refresh_due_diligence(db, user, workspace_id, request.evaluation_date)
        return AnalysisOut.model_validate(latest)
    key = storage.new_key()
    reservation = ObjectDeletionTask(storage_key=key, not_before=utcnow() + timedelta(minutes=10))
    run = DocumentAnalysis(
        workspace_id=workspace_id,
        document_id=document_id,
        generation=latest.generation + 1 if latest else 1,
        status=ExtractionStatus.EXTRACTING,
        automated_classification=Classification().model_dump(mode="json"),
        manual_classification=manual,
        correction_recorded=request.manual_kind is not None,
        effective_classification=manual or AnalysisKind.UNKNOWN,
        association=Association(reason="Processing not complete").model_dump(mode="json"),
        fields=[],
        evidence_ids=[],
        page_count=0,
        parser_version="pdf-text:1.0.0",
        source_sha256=document.sha256,
        artifact_storage_key=key,
        failure_code=None,
        retry_eligible=True,
    )
    db.add_all([reservation, run])
    await db.commit()
    # Reacquire and revalidate after the durable reservation. Keep this bounded
    # transaction locked through processing/storage so deletion cannot race it.
    workspace = await owned_workspace(db, user, workspace_id, lock=True)
    document = await owned_document(db, user, workspace_id, document_id)
    current = await analyses(db, workspace_id, document_id)
    if current[0].id != run.id or workspace.status != WorkspaceStatus.ACTIVE:
        run.status = ExtractionStatus.FAILED
        run.failure_code = "superseded_or_archived"
        run.retry_eligible = True
        run.completed_at = utcnow()
        await db.commit()
        return AnalysisOut.model_validate(run)
    try:
        content = storage.read(document.storage_key)
        if (
            len(content) != document.size_bytes
            or hashlib.sha256(content).hexdigest() != document.sha256
        ):
            raise ExtractionFailure("source_integrity_failure")
        pages = await extract_isolated(
            content,
            PdfLimits(
                config.max_upload_bytes,
                config.pdf_max_pages,
                config.pdf_max_characters,
                config.pdf_max_stream_bytes,
                config.pdf_timeout_seconds,
            ),
        )
        prediction = classify(pages)
        kind = manual if manual is not None else prediction.predicted_kind
        fields = extract_fields(pages, kind)
        association = associate(fields, await snapshot(db, workspace_id, user))
        run.automated_classification = prediction.model_dump(mode="json")
        run.effective_classification = kind
        run.parser_version = VERSIONS[kind]
        run.association = association.model_dump(mode="json")
        run.page_count = len(pages.pages)
        run.fields = [f.model_dump(mode="json") for f in fields]
        artifact = pages.model_dump_json().encode()
        db.add(
            DocumentTextArtifact(
                document_id=document_id,
                workspace_id=workspace_id,
                analysis_id=run.id,
                parser_name="pypdf",
                parser_version=pages.parser_version,
                page_count=len(pages.pages),
                content_hash=hashlib.sha256(artifact).hexdigest(),
                storage_key=key,
            )
        )
        await db.flush()
        storage.put(key, artifact)
        prior = list(
            (
                await db.scalars(
                    select(EvidenceItem).where(
                        EvidenceItem.document_id == document_id,
                        EvidenceItem.workspace_id == workspace_id,
                        EvidenceItem.source_version.like("document-extractor:%"),
                        EvidenceItem.superseded_at.is_(None),
                    )
                )
            ).all()
        )
        for item in prior:
            item.superseded_at = utcnow()
        await db.flush()
        ids = []
        for field in fields:
            old = next(
                (
                    e
                    for e in prior
                    if e.key == field.key and e.typed_value.get("value") == field.value
                ),
                None,
            )
            item = await record_evidence(
                db,
                user,
                workspace_id,
                EvidenceCreate(
                    document_id=document_id,
                    key=field.key,
                    typed_value=TypedValue(kind=field.value_kind, value=field.value),
                    source_type=SourceType.DOCUMENT,
                    authority=Authority.DOCUMENTED,
                    source_locator=SourceLocator(
                        document_id=document_id,
                        page=field.page,
                        start_offset=field.start,
                        end_offset=field.end,
                        parser_version=field.parser_version,
                    ),
                    confidence=field.confidence,
                    observed_at=utcnow(),
                ),
            )
            item.source_version = "document-extractor:" + field.parser_version
            item.supersedes_evidence_id = old.id if old else None
            ids.append(str(item.id))
        run.evidence_ids = ids
        document.document_kind = DocumentKind(kind.value)
        run.status = ExtractionStatus.READY
        run.retry_eligible = False
        await db.execute(delete(ObjectDeletionTask).where(ObjectDeletionTask.storage_key == key))
    except (ExtractionFailure, OSError) as error:
        failure = (
            error
            if isinstance(error, ExtractionFailure)
            else ExtractionFailure("private_storage_unavailable", retry=True)
        )
        run.status = (
            ExtractionStatus.OCR_REQUIRED
            if failure.code == "ocr_required"
            else ExtractionStatus.FAILED
        )
        run.failure_code = failure.code
        run.retry_eligible = failure.retry
        run.fields = []
        # The durable reservation handles failed writes/cleanup without logging.
    run.completed_at = utcnow()
    await db.flush()
    await refresh_due_diligence(db, user, workspace_id, request.evaluation_date)
    return AnalysisOut.model_validate(run)
