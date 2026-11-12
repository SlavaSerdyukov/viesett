from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from viesett.api.dependencies import Runtime
from viesett.db.models import PropertyWorkspace
from viesett.db.product_models import DemoWorkspace
from viesett.domain.intelligence import AnalyzeRequest
from viesett.domain.property import ResolutionRequest
from viesett.domain.types import DocumentKind
from viesett.services.document_analysis import analyze_document
from viesett.services.documents import upload_document
from viesett.services.property_resolution import resolve_property
from viesett.services.public_enrichment import refresh_enrichment


async def create_dossier(
    db: AsyncSession, user: UUID, data: ResolutionRequest, context: Runtime
) -> UUID:
    workspace = PropertyWorkspace(owner_user_id=user)
    db.add(workspace)
    await db.flush()
    if context.settings.demo_mode:
        db.add(DemoWorkspace(workspace_id=workspace.id))
    await db.commit()
    # Independent official relationship validation; no client result is trusted.
    await resolve_property(db, user, workspace.id, data, context.sources, context.settings)
    return workspace.id


async def intake(
    db: AsyncSession,
    user: UUID,
    wid: UUID,
    content: bytes,
    filename: str,
    media: str,
    context: Runtime,
) -> UUID:
    document, _ = await upload_document(
        db,
        user,
        wid,
        content,
        filename,
        media,
        DocumentKind.UNKNOWN,
        context.settings.max_upload_bytes,
        context.storage,
        context.pipeline,
    )
    if document.status == "READY":
        await analyze_document(
            db, user, wid, document.id, AnalyzeRequest(), context.settings, context.storage
        )
    return document.id


async def seed_demo(db: AsyncSession, user: UUID, context: Runtime) -> UUID:
    from viesett.db.models import EvidenceItem, utcnow
    from viesett.demo_documents import AGM_NL, DEED_NL, ELECTRICAL, EPC, SYNDIC_NL, text_pdf
    from viesett.domain.types import Authority, SourceType

    wid = await create_dossier(
        db, user, ResolutionRequest(query="Teststraat 42, 9000 Gent"), context
    )
    await refresh_enrichment(db, user, wid, context.sources, context.settings)
    for filename, text in [
        ("EPC demo.pdf", EPC),
        ("Electrical demo.pdf", ELECTRICAL),
        ("Basis deed demo.pdf", DEED_NL),
        ("AGM 2026 demo.pdf", AGM_NL),
        ("Syndic demo.pdf", SYNDIC_NL),
    ]:
        if filename.startswith("EPC"):
            text += (
                "\nDEMO transaction context: qualifying transfer = true; "
                "EPC exemption = false; ground transfer = true.\n"
            )
        await intake(db, user, wid, text_pdf(text), filename, "application/pdf", context)
    # Fictional explicit transaction facts, never asserted as real official data.
    epc = await db.scalar(
        __import__("sqlalchemy")
        .select(EvidenceItem)
        .where(EvidenceItem.workspace_id == wid, EvidenceItem.key == "document.epc.label")
    )
    assert epc and epc.document_id
    for key, value, kind in [
        ("transaction.qualifying_transfer", True, "boolean"),
        ("transaction.epc_exemption", False, "boolean"),
        ("transaction.ground_transfer", True, "boolean"),
    ]:
        db.add(
            EvidenceItem(
                workspace_id=wid,
                document_id=epc.document_id,
                key=key,
                typed_value={"kind": kind, "value": value},
                source_type=SourceType.DOCUMENT,
                authority=Authority.DOCUMENTED,
                source_locator={
                    "document_id": str(epc.document_id),
                    "page": 1,
                    "section": "Explicit synthetic transaction context — DEMO ONLY",
                },
                confidence=1,
                observed_at=utcnow(),
            )
        )
    await db.commit()
    return wid
