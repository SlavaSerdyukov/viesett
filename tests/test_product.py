from collections.abc import AsyncIterator
from datetime import date
from uuid import UUID, uuid4

import httpx
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.coownership_fixtures import SYNDIC_NL
from tests.document_fixtures import EPC, text_pdf
from tests.helpers import attest, workspace
from tests.official_fixtures import OfficialFixtureService
from tests.test_coownership_engine import doc, result
from viesett.api.app import create_app
from viesett.core.config import Settings
from viesett.db.models import Account, EvidenceItem, Finding, PropertyDocument, PropertyWorkspace
from viesett.db.product_models import DemoWorkspace
from viesett.domain.intelligence import AnalysisKind, EvaluationOut, Requirement
from viesett.rules.catalog import CATALOG
from viesett.services.auth import provision_account
from viesett.services.dossier import completeness


@pytest.fixture
async def product_client(
    settings: Settings, db: AsyncSession, official_service: OfficialFixtureService
) -> AsyncIterator[AsyncClient]:
    _, token = await provision_account(db)
    config = settings.model_copy(
        update={
            "source_min_interval": 0,
            "source_retry_base": 0,
            "max_upload_bytes": 128 * 1024,
            "max_request_bytes": 130 * 1024,
            "web_origins": ["http://localhost:5173"],
            "allow_development_web_sessions": True,
            "preview_rate_limit_per_minute": 3,
        }
    )
    app = create_app(config, source_transport=httpx.MockTransport(official_service.handler))
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"Authorization": "Bearer " + token},
    ) as client:
        yield client
    await app.state.runtime.sources.aclose()
    await app.state.engine.dispose()


@pytest.mark.parametrize(
    "mode,status",
    [
        ("success", "RESOLVED"),
        ("ambiguity", "NEEDS_SELECTION"),
        ("missing", "NOT_FOUND"),
        ("outage", "UPSTREAM_UNAVAILABLE"),
    ],
)
async def test_preview_states_and_no_private_persistence(
    product_client: AsyncClient,
    db: AsyncSession,
    official_service: OfficialFixtureService,
    mode: str,
    status: str,
) -> None:
    if mode == "ambiguity":
        official_service.units_by_address["1"] = ["10", "11"]
    if mode == "missing":
        official_service.search_ids = []
    if mode == "outage":
        official_service.status_by_path["/v2/adressen/zoeken"] = 503
    response = await product_client.post(
        "/api/v1/property-preview",
        json={"query": "Teststraat 42 Gent"},
        headers={"Authorization": ""},
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == status
    for model in [PropertyWorkspace, PropertyDocument, EvidenceItem, Finding]:
        assert await db.scalar(select(func.count()).select_from(model)) == 0
    assert not any(
        key in response.text
        for key in ["workspace_id", "storage_key", "document_id", "raw_payload"]
    )
    if mode == "ambiguity":
        assert len(response.json()["choices"]) == 2


async def test_preview_cannot_accept_private_fields_and_has_strict_limits(
    product_client: AsyncClient,
) -> None:
    assert (
        await product_client.post(
            "/api/v1/property-preview", json={"query": "Teststraat", "workspace_id": str(uuid4())}
        )
    ).status_code == 422
    for i in range(3):
        response = await product_client.post(
            "/api/v1/property-preview",
            json={"query": "Teststraat"},
            headers={"X-Forwarded-For": str(i)},
        )
        assert response.status_code == 200
    limited = await product_client.post(
        "/api/v1/property-preview",
        json={"query": "Teststraat"},
        headers={"X-Forwarded-For": "another"},
    )
    assert limited.status_code == 429 and "no-store" in limited.headers["cache-control"]


async def test_create_independently_revalidates_selection(
    product_client: AsyncClient, official_service: OfficialFixtureService
) -> None:
    await product_client.post("/api/v1/property-preview", json={"query": "Teststraat"})
    before = official_service.counts["/v2/adressen/zoeken"]
    created = await product_client.post(
        "/api/v1/dossiers", json={"query": "Teststraat", "selected_address_object_id": "999"}
    )
    assert created.status_code == 201, created.text
    assert official_service.counts["/v2/adressen/zoeken"] > before
    assert created.json()["property"]["address_id"] is None
    assert created.json()["property"]["unit_id"] is None


async def test_product_automatic_upload_analysis_dossier_citations_and_idempotence(
    product_client: AsyncClient, db: AsyncSession
) -> None:
    await attest(product_client)
    response = await product_client.post("/api/v1/dossiers", json={"query": "Teststraat 42 Gent"})
    assert response.status_code == 201, response.text
    wid = response.json()["workspace"]["id"]
    content = text_pdf(EPC)
    uploaded = await product_client.post(
        f"/api/v1/workspaces/{wid}/document-intake",
        content=content,
        headers={"Content-Type": "application/pdf", "X-Filename": "EPC.pdf"},
    )
    assert uploaded.status_code == 200, uploaded.text
    data = uploaded.json()
    assert data["documents"][0]["status"] == "ANALYZED"
    assert data["documents"][0]["kind"] == "EPC"
    assert data["findings"] and data["questions"]
    sources = [s for f in data["findings"] for s in f["sources"]]
    assert any(s["document_id"] == data["documents"][0]["id"] and s["page"] == 1 for s in sources)
    assert not any(
        x in uploaded.text
        for x in ["storage_key", "artifact_storage_key", "source_sha256", "inputs"]
    )
    repeated = await product_client.post(
        f"/api/v1/workspaces/{wid}/document-intake",
        content=content,
        headers={"Content-Type": "application/pdf"},
    )
    assert repeated.status_code == 200, repeated.text
    assert len(repeated.json()["documents"]) == 1
    assert await db.scalar(select(func.count()).select_from(PropertyDocument)) == 1
    assert repeated.json()["completeness"]["conditional_count"] > 0
    assert (await product_client.get(f"/api/v1/workspaces/{wid}/dossier")).json()[
        "schema_version"
    ] == "buyer-dossier:1.0.0"


@pytest.mark.parametrize(
    "variant,state", [("scan", "OCR_REQUIRED"), ("unknown", "UNKNOWN"), ("safe", "ANALYZED")]
)
async def test_intake_ocr_and_unknown_states(
    product_client: AsyncClient, variant: str, state: str
) -> None:
    await attest(product_client)
    wid = await workspace(product_client)
    text = (
        ""
        if variant == "scan"
        else "An unrecognized property document with useful text.\n"
        if variant == "unknown"
        else EPC
    )
    response = await product_client.post(
        f"/api/v1/workspaces/{wid}/document-intake",
        content=text_pdf(text),
        headers={"Content-Type": "application/pdf"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["documents"][0]["status"] == state


async def test_quarantined_document_is_not_analyzed(
    product_client: AsyncClient, db: AsyncSession
) -> None:
    await attest(product_client)
    wid = await workspace(product_client)
    response = await product_client.post(
        f"/api/v1/workspaces/{wid}/document-intake",
        content=text_pdf("BELGIAN EID\nNational Register\nidentiteitskaart\n"),
        headers={"Content-Type": "application/pdf"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["documents"][0]["status"] == "SAFETY_REVIEW"
    assert response.json()["documents"][0]["analysis_id"] is None


async def test_dossier_and_private_citation_isolation(
    product_client: AsyncClient, other_client: AsyncClient
) -> None:
    await attest(product_client)
    wid = await workspace(product_client)
    data = (
        await product_client.post(
            f"/api/v1/workspaces/{wid}/document-intake",
            content=text_pdf(EPC),
            headers={"Content-Type": "application/pdf"},
        )
    ).json()
    did = data["documents"][0]["id"]
    for path in [f"/workspaces/{wid}/dossier", f"/workspaces/{wid}/documents/{did}/content"]:
        response = await other_client.get("/api/v1" + path)
        assert response.status_code == 404
    assert (
        await other_client.post(f"/api/v1/workspaces/{wid}/refresh", json={})
    ).status_code == 404
    assert (
        await product_client.get(f"/api/v1/workspaces/{wid}/dossier", headers={"Authorization": ""})
    ).status_code == 401


async def test_session_bridge_requires_optin_loopback_origin_and_random_tokens(
    product_client: AsyncClient, client: AsyncClient, db: AsyncSession
) -> None:
    assert (await client.post("/api/v1/development/session")).status_code == 404
    assert (await product_client.post("/api/v1/development/session")).status_code == 403
    headers = {"Origin": "http://localhost:5173"}
    a = await product_client.post("/api/v1/development/session", headers=headers)
    b = await product_client.post("/api/v1/development/session", headers=headers)
    assert a.status_code == b.status_code == 200
    assert a.json()["token"] != b.json()["token"] and a.json()["expires_in_seconds"] == 3600
    assert "set-cookie" not in a.headers and "no-store" in a.headers["cache-control"]
    assert (
        await product_client.post(
            "/api/v1/development/session", headers={"Origin": "https://attacker.test"}
        )
    ).status_code == 403
    assert (await db.scalar(select(func.count()).select_from(Account)) or 0) >= 3


async def test_cors_is_explicit_and_credentials_are_not_cookie_based(
    product_client: AsyncClient,
) -> None:
    for origin, allowed in [("http://localhost:5173", True), ("https://attacker.test", False)]:
        response = await product_client.options(
            "/api/v1/dossiers",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "authorization,content-type",
            },
        )
        assert ("access-control-allow-origin" in response.headers) == allowed
        assert response.headers.get("access-control-allow-credentials") != "true"


@pytest.mark.parametrize("flag", ["demo_mode", "allow_development_web_sessions"])
def test_production_cannot_enable_development_features(flag: str, settings: Settings) -> None:
    values = settings.model_dump()
    values.update(environment="production", allow_development_safety=False)
    values[flag] = True
    with pytest.raises(ValueError):
        Settings(**values)


@pytest.mark.parametrize(
    "presence,done",
    [("PRESENT", 1), ("MISSING", 0), ("OCR_REQUIRED", 0), ("MISMATCHED", 0), ("UNUSABLE", 0)],
)
def test_completeness_counts_only_usable_required_information(presence: str, done: int) -> None:
    rule = next(iter(CATALOG.values()))
    base = dict(
        kind="EPC",
        rule=rule,
        applicability="REQUIRED",
        presence=presence,
        reason="synthetic",
        evaluation_date="2026-11-12",
    )
    required = Requirement.model_validate(base)
    conditional = Requirement.model_validate(
        {
            **base,
            "kind": "ASBESTOS_CERTIFICATE",
            "applicability": "CONDITIONAL",
            "presence": "MISSING",
        }
    )
    result = completeness([required, conditional], None)
    assert result.applicable_count == 1 and result.completed_count == done
    assert result.conditional_count == 1 and result.percentage == done * 100
    assert result.state != "COMPLETE"


def test_zero_applicable_is_not_one_hundred_percent_and_co_package_counts() -> None:
    assert completeness([], None).percentage is None
    co = result(doc(SYNDIC_NL, AnalysisKind.SYNDIC_INFORMATION))
    c = completeness([], co)
    assert c.applicable_count == 8 and c.completed_count == 7
    assert completeness([], co, in_progress=True).state == "IN_PROGRESS"


async def test_refresh_and_deletion_recompute_product_state(product_client: AsyncClient) -> None:
    await attest(product_client)
    wid = await workspace(product_client)
    data = (
        await product_client.post(
            f"/api/v1/workspaces/{wid}/document-intake",
            content=text_pdf(EPC),
            headers={"Content-Type": "application/pdf"},
        )
    ).json()
    assert data["findings"]
    assert (
        await product_client.delete(
            f"/api/v1/workspaces/{wid}/documents/{data['documents'][0]['id']}"
        )
    ).status_code == 204
    refreshed = await product_client.post(f"/api/v1/workspaces/{wid}/refresh", json={})
    assert refreshed.status_code == 200
    assert refreshed.json()["documents"] == []
    assert not any("epc label" in f["label"] for f in refreshed.json()["evidence"])


async def test_aggregate_retries_if_sources_change_between_evaluations(
    product_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from viesett.db.models import utcnow
    from viesett.domain.types import Authority, SourceType
    from viesett.services import dossier as service
    from viesett.services.due_diligence import refresh_due_diligence

    original = refresh_due_diligence
    calls = 0

    async def changing(
        db: AsyncSession, user: UUID, wid: UUID, evaluation_date: date | None = None
    ) -> EvaluationOut:
        nonlocal calls
        value = await original(db, user, wid, evaluation_date)
        calls += 1
        if calls == 1:
            db.add(
                EvidenceItem(
                    workspace_id=wid,
                    key="manual.synthetic",
                    typed_value={"kind": "text", "value": "new source generation"},
                    authority=Authority.INFERRED,
                    source_type=SourceType.MANUAL,
                    source_locator={"section": "Synthetic concurrency test"},
                    confidence=1,
                    observed_at=utcnow(),
                )
            )
            await db.commit()
        return value

    monkeypatch.setattr(service, "refresh_due_diligence", changing)
    wid = await workspace(product_client)
    response = await product_client.get(f"/api/v1/workspaces/{wid}/dossier")
    assert response.status_code == 200, response.text
    assert calls == 2
    assert response.json()["evidence"][0]["value"] == "new source generation"


async def test_document_association_uses_current_property_not_old_analysis(
    product_client: AsyncClient,
    official_service: OfficialFixtureService,
) -> None:
    from tests.official_fixtures import name

    await attest(product_client)
    created = await product_client.post("/api/v1/dossiers", json={"query": "Teststraat"})
    wid = created.json()["workspace"]["id"]
    uploaded = await product_client.post(
        f"/api/v1/workspaces/{wid}/document-intake",
        content=text_pdf(EPC),
        headers={"Content-Type": "application/pdf"},
    )
    assert uploaded.json()["documents"][0]["association"] == "MATCHED"
    official_service.addresses["1"]["straatnaam"] = {"straatnaam": name("Andereweg")}
    official_service.addresses["1"]["volledigAdres"] = name("Andereweg 42, 9000 Gent")
    await product_client.post(
        f"/api/v1/workspaces/{wid}/property-resolution", json={"query": "Andereweg 42 Gent"}
    )
    response = await product_client.get(f"/api/v1/workspaces/{wid}/dossier")
    assert response.status_code == 200, response.text
    assert response.json()["documents"][0]["association"] == "MISMATCH"


async def test_demo_uses_real_pipelines_and_is_persistently_labelled(
    settings: Settings,
    db: AsyncSession,
) -> None:
    _, token = await provision_account(db)
    config = settings.model_copy(
        update={
            "demo_mode": True,
            "allow_development_safety": True,
            "max_upload_bytes": 128 * 1024,
            "max_request_bytes": 130 * 1024,
            "source_min_interval": 0,
        }
    )
    app = create_app(config)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"Authorization": "Bearer " + token},
    ) as c:
        await attest(c)
        response = await c.post("/api/v1/development/demo-dossier")
        assert response.status_code == 201, response.text
        data = response.json()
        assert data["is_demo"] and data["workspace"]["is_demo"]
        assert len(data["documents"]) == 5
        exported = (await c.get("/api/v1/me/export")).json()
        assert exported["workspaces"][0]["is_demo"] is True
        assert (await c.get("/api/v1/workspaces")).json()[0]["is_demo"] is True
        assert (
            data["co_ownership"]["financial_exposure_estimates"][0][
                "estimated_proportional_amount"
            ]["amount"]
            == "6000.00"
        )
        assert any(
            r["kind"] == "SOIL_CERTIFICATE"
            and r["presence"] == "MISSING"
            and r["applicability"] == "REQUIRED"
            for r in data["requirements"]
        )
        assert any(f["group"] == "Electrical" for f in data["findings"])
        assert data["completeness"]["percentage"] == 80
        wid = UUID(data["workspace"]["id"])
        assert await db.get(DemoWorkspace, wid) is not None
        assert (await c.get(f"/api/v1/workspaces/{wid}/dossier")).json()["is_demo"]
        assert (await c.delete(f"/api/v1/workspaces/{wid}")).status_code == 204
        assert await db.get(DemoWorkspace, wid, populate_existing=True) is None
    await app.state.runtime.sources.aclose()
    await app.state.engine.dispose()


async def test_normal_instance_cannot_create_demo_and_remote_cannot_bootstrap(
    product_client: AsyncClient,
    settings: Settings,
) -> None:
    assert (await product_client.post("/api/v1/development/demo-dossier")).status_code == 404
    app = create_app(
        settings.model_copy(
            update={
                "allow_development_web_sessions": True,
                "web_origins": ["http://localhost:5173"],
            }
        )
    )
    async with AsyncClient(
        transport=ASGITransport(app=app, client=("198.51.100.7", 12345)),
        base_url="http://testserver",
    ) as c:
        assert (
            await c.post("/api/v1/development/session", headers={"Origin": "http://localhost:5173"})
        ).status_code == 404
    await app.state.runtime.sources.aclose()
    await app.state.engine.dispose()


def test_complete_has_a_transparent_unweighted_denominator() -> None:
    base = dict(
        kind="EPC",
        rule=next(iter(CATALOG.values())),
        applicability="REQUIRED",
        presence="PRESENT",
        reason="synthetic",
        evaluation_date="2026-11-12",
    )
    result = completeness(
        [
            Requirement.model_validate(base),
            Requirement.model_validate(
                {
                    **base,
                    "kind": "SOIL_CERTIFICATE",
                    "applicability": "NOT_REQUIRED",
                    "presence": "MISSING",
                }
            ),
        ],
        None,
    )
    assert result.state == "COMPLETE" and result.percentage == 100
    assert (result.completed_count, result.applicable_count) == (1, 1)


async def test_pending_property_can_be_confirmed_without_creating_another_dossier(
    product_client: AsyncClient,
    official_service: OfficialFixtureService,
) -> None:
    official_service.status_by_path["/v2/adressen/zoeken"] = 503
    created = await product_client.post("/api/v1/dossiers", json={"query": "Teststraat 42 Gent"})
    data = created.json()
    wid = data["workspace"]["id"]
    assert data["property"]["status"] == "UPSTREAM_UNAVAILABLE"
    assert data["property"]["query"] == "Teststraat 42 Gent"
    official_service.status_by_path.clear()
    confirmed = await product_client.post(
        f"/api/v1/workspaces/{wid}/property-resolution", json={"query": "Teststraat 42 Gent"}
    )
    assert confirmed.json()["status"] == "RESOLVED"
    result = (await product_client.get(f"/api/v1/workspaces/{wid}/dossier")).json()
    assert result["workspace"]["id"] == wid and result["property"]["status"] == "RESOLVED"


async def test_source_citations_survive_evidence_page_limit(
    product_client: AsyncClient,
    db: AsyncSession,
) -> None:
    from viesett.db.models import FindingEvidence, utcnow
    from viesett.domain.types import Authority, Severity, SourceType

    await attest(product_client)
    wid = await workspace(product_client)
    content = await product_client.post(
        f"/api/v1/workspaces/{wid}/documents",
        content=text_pdf(EPC),
        headers={"Content-Type": "application/pdf"},
    )
    did = UUID(content.json()["id"])
    for i in range(500):
        db.add(
            EvidenceItem(
                workspace_id=UUID(wid),
                key=f"manual.synthetic.{i}",
                typed_value={"kind": "text", "value": "synthetic"},
                source_type=SourceType.MANUAL,
                authority=Authority.INFERRED,
                source_locator={"section": "synthetic"},
                observed_at=utcnow(),
            )
        )
    await db.flush()
    cited = EvidenceItem(
        workspace_id=UUID(wid),
        document_id=did,
        key="manual.cited",
        typed_value={"kind": "text", "value": "synthetic cited fact"},
        source_type=SourceType.DOCUMENT,
        authority=Authority.DOCUMENTED,
        source_locator={"page": 1, "document_id": str(did)},
        observed_at=utcnow(),
    )
    db.add(cited)
    await db.flush()
    finding = Finding(
        workspace_id=UUID(wid),
        code="SYNTHETIC_CITATION",
        severity=Severity.REVIEW,
        summary="Synthetic citation test",
        provenance={"method": "manual", "source": "test", "version": "1"},
    )
    db.add(finding)
    await db.flush()
    db.add(FindingEvidence(workspace_id=UUID(wid), finding_id=finding.id, evidence_id=cited.id))
    await db.commit()
    response = await product_client.get(f"/api/v1/workspaces/{wid}/dossier")
    assert response.status_code == 200, response.text
    data = response.json()
    assert len(data["evidence"]) == 500 and data["truncated"]
    target = next(f for f in data["findings"] if f["code"] == "SYNTHETIC_CITATION")
    assert target["sources"][0]["document_id"] == str(did) and target["sources"][0]["page"] == 1
    derived = next(e for e in data["evidence"] if e["authority"] == "INFERRED")
    assert derived["sources"][0]["label"] == "Derived information"
