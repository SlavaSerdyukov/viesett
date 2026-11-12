import json
import logging
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from tests.document_fixtures import EPC, SAMPLES, text_pdf
from tests.helpers import attest, upload, workspace
from tests.official_fixtures import OfficialFixtureService
from tests.test_property_resolution import resolve
from viesett.core.config import Settings
from viesett.db.intelligence_models import (
    DocumentAnalysis,
    DocumentTextArtifact,
    DueDiligenceEvaluation,
)
from viesett.db.models import EvidenceItem, Finding, ObjectDeletionTask, PropertyDocument
from viesett.domain.intelligence import AnalysisKind
from viesett.services.deletion import purge_objects
from viesett.storage.private import LocalPrivateStorage

WHEN = "2026-11-12"


async def prepare(client: AsyncClient, text: str = EPC) -> tuple[str, str]:
    wid = await workspace(client)
    await attest(client)
    await resolve(client, wid)
    uploaded = await upload(client, wid, text_pdf(text))
    assert uploaded.status_code == 201, uploaded.text
    return wid, uploaded.json()["id"]


async def analyze(client: AsyncClient, wid: str, did: str, **data: str) -> Response:
    return await client.post(
        f"/api/v1/workspaces/{wid}/documents/{did}/analyze", json={"evaluation_date": WHEN, **data}
    )


@pytest.mark.parametrize("kind", list(SAMPLES))
async def test_end_to_end_documented_analysis_and_idempotent_rules(
    analysis_client: AsyncClient,
    db: AsyncSession,
    kind: AnalysisKind,
) -> None:
    wid, did = await prepare(analysis_client, SAMPLES[kind])
    response = await analyze(analysis_client, wid, did)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["status"] == "READY" and result["effective_classification"] == kind
    assert result["association"]["status"] == "MATCHED"
    assert result["page_count"] == 1 and result["evidence_ids"]
    assert "storage_key" not in response.text
    evidence = (await analysis_client.get(f"/api/v1/workspaces/{wid}/evidence")).json()
    documented = [e for e in evidence if e["document_id"] == did]
    assert len(documented) == len(result["fields"])
    for e in documented:
        assert e["authority"] == "DOCUMENTED" and e["provider"] is None
        assert e["source_locator"]["document_id"] == did
        assert e["source_locator"]["page"] == 1 and e["source_locator"]["parser_version"]
        assert e["source_locator"]["end_offset"] > e["source_locator"]["start_offset"]
    count = await db.scalar(select(func.count()).select_from(Finding))
    assert (await analyze(analysis_client, wid, did)).json()["id"] == result["id"]
    assert await db.scalar(select(func.count()).select_from(Finding)) == count
    assert await db.scalar(select(func.count()).select_from(DocumentTextArtifact)) == 1
    exported = (await analysis_client.get("/api/v1/me/export")).json()
    assert exported["document_analyses"][0]["document_id"] == did
    assert exported["due_diligence_evaluations"][0]["evaluation_date"] == WHEN
    assert "storage_key" not in json.dumps(exported)


async def test_manual_classification_preserves_prediction_and_history(
    analysis_client: AsyncClient,
) -> None:
    text = EPC.replace("Energieprestatiecertificaat", "Synthetic certificate")
    wid, did = await prepare(analysis_client, text)
    auto = (await analyze(analysis_client, wid, did)).json()
    assert auto["automated_classification"]["predicted_kind"] == "UNKNOWN"
    corrected = (await analyze(analysis_client, wid, did, manual_kind="EPC")).json()
    assert corrected["status"] == "READY" and corrected["correction_recorded"]
    assert corrected["automated_classification"] == auto["automated_classification"]
    assert corrected["manual_classification"] == corrected["effective_classification"] == "EPC"
    assert corrected["evidence_ids"]
    history = (
        await analysis_client.get(
            f"/api/v1/workspaces/{wid}/documents/{did}/analysis?include_history=true"
        )
    ).json()
    assert history["current"]["id"] == corrected["id"]
    assert history["history"][0]["id"] == auto["id"]
    assert (await analyze(analysis_client, wid, did)).json()["id"] == corrected["id"]


@pytest.mark.parametrize(
    "replacement,status",
    [
        ("Teststraat 43, 9000 Gent", "MISMATCH"),
        ("Teststraat 42 bus 2, 9000 Gent", "POSSIBLE_MATCH"),
        ("teststraat 42, 9000 gent", "MATCHED"),
        ("Teststraat 42, 8000 Gent", "MISMATCH"),
        ("unparseable property address", "UNVERIFIED"),
    ],
)
async def test_document_identity_controls_substantive_findings(
    analysis_client: AsyncClient,
    replacement: str,
    status: str,
) -> None:
    wid, did = await prepare(analysis_client, EPC.replace("Teststraat 42, 9000 Gent", replacement))
    result = (await analyze(analysis_client, wid, did)).json()
    assert result["association"]["status"] == status
    evaluated = (
        await analysis_client.post(
            f"/api/v1/workspaces/{wid}/due-diligence/refresh", json={"evaluation_date": WHEN}
        )
    ).json()
    findings = (
        await analysis_client.get(f"/api/v1/workspaces/{wid}/findings?evaluation_date={WHEN}")
    ).json()
    current = [f for f in findings if f["resolved_at"] is None]
    if status == "MATCHED":
        assert any(f["code"] == "FL_EPC_RENOVATION" for f in current)
    else:
        assert not any(f["code"] == "FL_EPC_RENOVATION" for f in current)
        assert result["evidence_ids"]  # retained at document level for review
    assert evaluated["input_hash"]


async def test_box_mismatch_with_official_unit_is_never_matched(
    analysis_client: AsyncClient,
    official_service: OfficialFixtureService,
) -> None:
    official_service.search_ids = ["2"]
    wid, did = await prepare(analysis_client, EPC.replace("42,", "42 bus 2,"))
    assert (await analyze(analysis_client, wid, did)).json()["association"]["status"] == "MISMATCH"


@pytest.mark.parametrize("operation", ["analyze", "analysis", "refresh", "requirements"])
async def test_intelligence_ownership_is_uniform_and_cross_workspace_safe(
    analysis_client: AsyncClient,
    other_client: AsyncClient,
    operation: str,
) -> None:
    wid, did = await prepare(analysis_client)
    method = "GET" if operation in {"analysis", "requirements"} else "POST"
    suffix = {
        "analyze": f"documents/{did}/analyze",
        "analysis": f"documents/{did}/analysis",
        "refresh": "due-diligence/refresh",
        "requirements": "document-requirements",
    }[operation]
    response = await other_client.request(
        method, f"/api/v1/workspaces/{wid}/{suffix}", json={} if method == "POST" else None
    )
    absent = await other_client.request(
        method, f"/api/v1/workspaces/{uuid4()}/{suffix}", json={} if method == "POST" else None
    )
    assert response.status_code == absent.status_code == 404
    assert response.json() == absent.json()
    assert (await other_client.get("/api/v1/me/export")).json()["document_analyses"] == []


@pytest.mark.parametrize(
    "case,expected", [("scan", "OCR_REQUIRED"), ("malformed", "FAILED"), ("encrypted", "FAILED")]
)
async def test_unusable_pdf_typed_state_has_no_documented_evidence(
    analysis_client: AsyncClient,
    case: str,
    expected: str,
) -> None:
    wid = await workspace(analysis_client)
    await attest(analysis_client)
    content = text_pdf("") if case == "scan" else text_pdf(EPC, encrypted=True)
    if case == "malformed":
        content = b"%PDF-1.7\nbad private PDF content\n%%EOF"
    uploaded = await upload(analysis_client, wid, content)
    assert uploaded.status_code == 201, uploaded.text
    did = uploaded.json()["id"]
    result = (await analyze(analysis_client, wid, did)).json()
    assert result["status"] == expected and result["failure_code"]
    assert result["fields"] == result["evidence_ids"] == []
    assert (await analysis_client.get(f"/api/v1/workspaces/{wid}/documents/{did}")).json()[
        "status"
    ] == "READY"


@pytest.mark.parametrize("scope", ["document", "workspace", "account"])
async def test_deleting_source_erases_derived_files_metadata_and_evaluation_inputs(
    analysis_client: AsyncClient,
    db: AsyncSession,
    settings: Settings,
    scope: str,
) -> None:
    wid, did = await prepare(analysis_client)
    assert (await analyze(analysis_client, wid, did)).json()["status"] == "READY"
    artifact = await db.scalar(select(DocumentTextArtifact))
    assert artifact is not None
    storage = LocalPrivateStorage(settings.storage_root)
    key = artifact.storage_key
    assert b"EPC-label" in storage.read(key)
    url = {
        "document": f"/api/v1/workspaces/{wid}/documents/{did}",
        "workspace": f"/api/v1/workspaces/{wid}",
        "account": "/api/v1/me",
    }[scope]
    assert (await analysis_client.delete(url)).status_code == 204
    with pytest.raises(FileNotFoundError):
        storage.read(key)
    for model in (DocumentTextArtifact, DocumentAnalysis, DueDiligenceEvaluation):
        assert await db.scalar(select(func.count()).select_from(model)) == 0


async def test_parser_content_and_private_artifacts_never_leak_into_logs(
    analysis_client: AsyncClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    secret = "SYNTHETIC_PRIVATE_SECRET_NO_LOG"
    wid, did = await prepare(analysis_client, EPC + secret)
    with caplog.at_level(logging.DEBUG):
        result = await analyze(analysis_client, wid, did)
    assert result.json()["status"] == "READY"
    assert secret not in caplog.text
    assert secret not in result.text


async def test_rule_refresh_reassociates_changed_property_and_preserves_history(
    analysis_client: AsyncClient,
    official_service: OfficialFixtureService,
) -> None:
    wid, did = await prepare(analysis_client)
    await analyze(analysis_client, wid, did)
    official_service.addresses["1"]["huisnummer"] = "43"
    await resolve(analysis_client, wid)
    current = (
        await analysis_client.get(f"/api/v1/workspaces/{wid}/findings?evaluation_date={WHEN}")
    ).json()
    renovation = [f for f in current if f["code"] == "FL_EPC_RENOVATION"]
    assert renovation and all(f["resolved_at"] for f in renovation)
    assert any(
        f["code"] == "DOCUMENT_PROPERTY_ASSOCIATION" and not f["resolved_at"] for f in current
    )


@pytest.mark.parametrize(
    "status,expected", [("QUARANTINED", 409), ("REJECTED", 409), ("DELETED", 404)]
)
async def test_only_safe_ready_documents_enter_analysis(
    analysis_client: AsyncClient,
    db: AsyncSession,
    status: str,
    expected: int,
) -> None:
    from viesett.domain.types import DocumentStatus

    wid, did = await prepare(analysis_client)
    document = await db.get(PropertyDocument, UUID(did))
    assert document is not None
    document.status = DocumentStatus(status)
    await db.commit()
    assert (await analyze(analysis_client, wid, did)).status_code == expected
    assert await db.scalar(select(func.count()).select_from(DocumentAnalysis)) == 0


async def test_reextraction_versions_evidence_and_manual_decision(
    analysis_client: AsyncClient,
) -> None:
    wid, did = await prepare(analysis_client)
    original = (await analyze(analysis_client, wid, did)).json()
    corrected = (await analyze(analysis_client, wid, did, manual_kind="EPC")).json()
    assert corrected["generation"] == original["generation"] + 1
    history = (
        await analysis_client.get(f"/api/v1/workspaces/{wid}/evidence?include_history=true")
    ).json()
    old = [e for e in history if e["id"] in original["evidence_ids"]]
    new = [e for e in history if e["id"] in corrected["evidence_ids"]]
    assert all(e["superseded_at"] for e in old)
    assert {e["supersedes_evidence_id"] for e in new} == set(original["evidence_ids"])


async def test_storage_failure_is_retryable_and_never_changes_safety(
    analysis_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    wid, did = await prepare(analysis_client)

    def unavailable(self: LocalPrivateStorage, key: str) -> bytes:
        raise OSError("PRIVATE_STORAGE_EXCEPTION_DO_NOT_LOG")

    with monkeypatch.context() as patch:
        patch.setattr(LocalPrivateStorage, "read", unavailable)
        failed = (await analyze(analysis_client, wid, did)).json()
    assert failed["status"] == "FAILED" and failed["retry_eligible"]
    assert failed["failure_code"] == "private_storage_unavailable"
    assert "PRIVATE_STORAGE_EXCEPTION" not in json.dumps(failed)
    assert (await analyze(analysis_client, wid, did)).json()["status"] == "READY"


async def test_derived_only_deletion_failure_is_durable_and_reported(
    analysis_client: AsyncClient,
    db: AsyncSession,
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    wid, did = await prepare(analysis_client)
    await analyze(analysis_client, wid, did)
    artifact = await db.scalar(select(DocumentTextArtifact))
    assert artifact is not None
    derived_key = artifact.storage_key
    original_delete = LocalPrivateStorage.delete

    def fail_derived(self: LocalPrivateStorage, key: str) -> None:
        if key == derived_key:
            raise OSError("synthetic derived storage failure")
        original_delete(self, key)

    with monkeypatch.context() as patch:
        patch.setattr(LocalPrivateStorage, "delete", fail_derived)
        result = await analysis_client.delete(f"/api/v1/workspaces/{wid}/documents/{did}")
    assert result.status_code == 503
    assert (
        await db.scalar(
            select(ObjectDeletionTask.storage_key).where(
                ObjectDeletionTask.storage_key == derived_key
            )
        )
        == derived_key
    )
    assert (
        await analysis_client.get(f"/api/v1/workspaces/{wid}/documents/{did}/analysis")
    ).status_code == 404
    await purge_objects(db, LocalPrivateStorage(settings.storage_root))
    with pytest.raises(FileNotFoundError):
        LocalPrivateStorage(settings.storage_root).read(derived_key)


async def test_scanned_manual_epc_stays_ocr_required_in_requirements(
    analysis_client: AsyncClient,
) -> None:
    wid, did = await prepare(analysis_client, "")
    result = (await analyze(analysis_client, wid, did, manual_kind="EPC")).json()
    assert result["status"] == "OCR_REQUIRED"
    evaluation = (
        await analysis_client.post(
            f"/api/v1/workspaces/{wid}/due-diligence/refresh", json={"evaluation_date": WHEN}
        )
    ).json()
    assert (
        next(r for r in evaluation["requirements"] if r["kind"] == "EPC")["presence"]
        == "OCR_REQUIRED"
    )


async def test_database_rejects_promoting_extracted_pdf_evidence_to_official(
    analysis_client: AsyncClient,
    db: AsyncSession,
) -> None:
    from viesett.domain.types import Authority, SourceType

    wid, did = await prepare(analysis_client)
    await analyze(analysis_client, wid, did)
    item = await db.scalar(select(EvidenceItem).where(EvidenceItem.document_id == UUID(did)))
    assert item is not None
    with pytest.raises(IntegrityError):
        async with db.begin_nested():
            item.authority = Authority.OFFICIAL
            item.source_type = SourceType.PUBLIC_REGISTRY
            await db.flush()


async def test_source_deletion_invalidates_indirect_managed_findings_and_recomputes(
    analysis_client: AsyncClient,
    db: AsyncSession,
) -> None:
    from tests.helpers import owner
    from viesett.domain.schemas import FindingCreate, FindingProvenance
    from viesett.domain.types import Severity
    from viesett.services.evidence import record_finding

    wid, did = await prepare(analysis_client)
    await analyze(analysis_client, wid, did)
    indirect = await record_finding(
        db,
        await owner(analysis_client),
        UUID(wid),
        FindingCreate(
            code="INDIRECT_OLD_CONCLUSION",
            severity=Severity.REVIEW,
            summary="Synthetic indirect dependency",
            provenance=FindingProvenance(
                method="deterministic", source="viesett.rules", version="1.0.0"
            ),
        ),
    )
    await db.commit()
    assert (
        await analysis_client.delete(f"/api/v1/workspaces/{wid}/documents/{did}")
    ).status_code == 204
    exported = (await analysis_client.get("/api/v1/me/export")).json()
    stored = next(f for f in exported["findings"] if f["id"] == str(indirect.id))
    assert stored["resolved_at"]  # cannot remain current, including before a read refresh
    refreshed = (
        await analysis_client.get(f"/api/v1/workspaces/{wid}/findings?evaluation_date={WHEN}")
    ).json()
    assert not any(f["code"] == "FL_EPC_RENOVATION" and not f["resolved_at"] for f in refreshed)
    assert await db.scalar(select(func.count()).select_from(DueDiligenceEvaluation)) == 1
