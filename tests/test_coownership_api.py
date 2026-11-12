import json
import logging
from typing import Any, cast
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.coownership_fixtures import AGM_NL, DEED_NL, IDENTITY_NL, SAMPLES, SYNDIC_NL
from tests.document_fixtures import text_pdf
from tests.helpers import attest, upload, workspace
from tests.test_document_analysis import WHEN, analyze
from tests.test_property_resolution import resolve
from viesett.core.config import Settings
from viesett.db.coownership_models import (
    CoOwnershipEvaluation,
    CoOwnershipIdentityRecord,
    PlannedWorkRecord,
)
from viesett.db.intelligence_models import DocumentTextArtifact
from viesett.db.models import Finding
from viesett.domain.intelligence import AnalysisKind
from viesett.storage.private import LocalPrivateStorage


async def add(client: AsyncClient, wid: str, text: str) -> str:
    response = await upload(client, wid, text_pdf(text))
    assert response.status_code in {200, 201}, response.text
    did = response.json()["id"]
    processed = await analyze(client, wid, did)
    assert processed.status_code == 200, processed.text
    assert processed.json()["status"] == "READY", processed.text
    return str(did)


async def setup(client: AsyncClient) -> str:
    wid = await workspace(client)
    await attest(client)
    await resolve(client, wid)
    return wid


async def co(client: AsyncClient, wid: str) -> dict[str, Any]:
    response = await client.get(f"/api/v1/workspaces/{wid}/co-ownership?evaluation_date={WHEN}")
    assert response.status_code == 200, response.text
    return cast(dict[str, Any], response.json())


async def test_analysis_automatically_builds_dossier_and_idempotent_evaluation(
    analysis_client: AsyncClient,
    db: AsyncSession,
) -> None:
    wid = await setup(analysis_client)
    await add(analysis_client, wid, DEED_NL)
    await add(analysis_client, wid, AGM_NL)
    await add(analysis_client, wid, SYNDIC_NL)
    # Automatic recomputation already happened, without a co-ownership refresh call.
    assert await db.scalar(select(func.count()).select_from(CoOwnershipIdentityRecord)) == 1
    first = await co(analysis_client, wid)
    assert first["co_ownership_status"] == "DOCUMENTED"
    assert first["identity"]["lot_identifier"] == "A1"
    assert (
        first["financial_exposure_estimates"][0]["estimated_proportional_amount"]["amount"]
        == "6000.00"
    )
    assert len(first["planned_works"]) == 1
    count = await db.scalar(select(func.count()).select_from(Finding))
    repeated = await co(analysis_client, wid)
    assert repeated["evaluation_id"] == first["evaluation_id"]
    assert await db.scalar(select(func.count()).select_from(Finding)) == count
    assert (
        await db.scalar(
            select(func.count())
            .select_from(PlannedWorkRecord)
            .where(PlannedWorkRecord.superseded_at.is_(None))
        )
        == 1
    )
    export = (await analysis_client.get("/api/v1/me/export")).json()
    assert export["co_ownership_evaluations"]
    assert "storage_key" not in json.dumps(export) and "artifact_storage_key" not in json.dumps(
        export
    )
    evidence = (await analysis_client.get(f"/api/v1/workspaces/{wid}/evidence")).json()
    money = [e for e in evidence if e["typed_value"]["kind"] == "money"]
    assert money and all(
        e["authority"] == "DOCUMENTED" and e["source_locator"]["currency"] == "EUR" for e in money
    )
    assert all(e["source_locator"]["page"] and e["source_locator"]["effective_date"] for e in money)


@pytest.mark.parametrize("kind", list(SAMPLES))
async def test_each_m4_kind_works_through_existing_analysis_endpoint(
    analysis_client: AsyncClient, kind: AnalysisKind
) -> None:
    wid = await setup(analysis_client)
    did = await add(analysis_client, wid, SAMPLES[kind][1])
    analysis = (
        await analysis_client.get(f"/api/v1/workspaces/{wid}/documents/{did}/analysis")
    ).json()["current"]
    assert analysis["effective_classification"] == kind
    assert analysis["co_metadata"]["detected_language"] == "fr"
    assert analysis["co_metadata"]["parse_status"] in {"PARSED", "PARTIALLY_PARSED"}


@pytest.mark.parametrize(
    "suffix,method",
    [
        ("co-ownership", "GET"),
        ("co-ownership/refresh", "POST"),
        ("cross-document-findings", "GET"),
        ("buyer-questions", "GET"),
    ],
)
async def test_co_ownership_ownership_isolation(
    analysis_client: AsyncClient, other_client: AsyncClient, suffix: str, method: str
) -> None:
    wid = await setup(analysis_client)
    response = await other_client.request(
        method, f"/api/v1/workspaces/{wid}/{suffix}", json={} if method == "POST" else None
    )
    absent = await other_client.request(
        method, f"/api/v1/workspaces/{uuid4()}/{suffix}", json={} if method == "POST" else None
    )
    assert response.status_code == absent.status_code == 404
    assert response.json() == absent.json()
    assert (await other_client.get("/api/v1/me/export")).json()["co_ownership_evaluations"] == []


async def test_newer_fund_observation_has_current_value_and_keeps_history(
    analysis_client: AsyncClient,
) -> None:
    wid = await setup(analysis_client)
    await add(
        analysis_client,
        wid,
        SYNDIC_NL.replace("Toestand op: 2026-11-12", "Toestand op: 2026-01-01"),
    )
    first = await co(analysis_client, wid)
    await add(analysis_client, wid, SYNDIC_NL.replace("EUR 50000,00", "EUR 60000,00"))
    latest = await co(analysis_client, wid)
    assert latest["current_reserve_capital"]["money"]["amount"] == "60000.00"
    assert len(latest["reserve_capital"]) == 2
    assert not any(
        f["code"] == "RESERVE_CAPITAL_AMOUNT_CONSISTENCY" for f in latest["cross_document_findings"]
    )
    export = (await analysis_client.get("/api/v1/me/export")).json()
    assert first["evaluation_id"] in {
        e["evaluation_id"] for e in export["co_ownership_evaluations"]
    }


@pytest.mark.parametrize("scope", ["document", "workspace", "account"])
async def test_source_deletion_cleans_m4_derived_state(
    analysis_client: AsyncClient, db: AsyncSession, scope: str
) -> None:
    wid = await setup(analysis_client)
    did = await add(analysis_client, wid, AGM_NL)
    assert (await co(analysis_client, wid))["planned_works"]
    url = {
        "document": f"/api/v1/workspaces/{wid}/documents/{did}",
        "workspace": f"/api/v1/workspaces/{wid}",
        "account": "/api/v1/me",
    }[scope]
    assert (await analysis_client.delete(url)).status_code == 204
    for model in (CoOwnershipEvaluation, CoOwnershipIdentityRecord, PlannedWorkRecord):
        assert await db.scalar(select(func.count()).select_from(model)) == 0


async def test_manual_m4_correction_keeps_prediction_and_private_names_out(
    analysis_client: AsyncClient,
) -> None:
    wid = await setup(analysis_client)
    text = (
        SYNDIC_NL.replace("Inlichtingen artikel 3.94", "Synthetic package")
        + "Aanwezigen: Jan Geheim\n"
    )
    did = await add(analysis_client, wid, text)
    corrected = await analyze(analysis_client, wid, did, manual_kind="SYNDIC_INFORMATION")
    assert corrected.json()["automated_classification"]["predicted_kind"] == "UNKNOWN"
    assert corrected.json()["correction_recorded"]
    assert "Jan Geheim" not in corrected.text
    assert "Jan Geheim" not in (await analysis_client.get("/api/v1/me/export")).text


async def test_request_draft_uses_missing_co_ownership_periods(
    analysis_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from datetime import date

    from viesett.services import coownership

    monkeypatch.setattr(coownership, "current_evaluation_date", lambda: date(2026, 11, 12))
    wid = await setup(analysis_client)
    await add(analysis_client, wid, "Syndicusinformatie\n" + IDENTITY_NL)
    response = await analysis_client.post(
        f"/api/v1/workspaces/{wid}/document-request-draft",
        json={"requested_document_types": ["SYNDIC_INFORMATION"], "language": "nl"},
    )
    assert response.status_code == 201, response.text
    assert "notulen gewone en buitengewone AV" in response.json()["generated_text"]
    assert "2023-11-12" in response.json()["generated_text"]
    assert not any(k in response.json() for k in ("recipient", "sent_at", "email"))


async def test_m4_private_artifact_does_not_duplicate_attendance_or_bank_details(
    analysis_client: AsyncClient,
    db: AsyncSession,
    settings: Settings,
    caplog: pytest.LogCaptureFixture,
) -> None:
    wid = await setup(analysis_client)
    with caplog.at_level(logging.INFO):
        await add(
            analysis_client,
            wid,
            AGM_NL + "Aanwezigen: SECRET_ATTENDEE_7788\nIBAN: BE00 1234 1234 1234\n",
        )
    artifact = await db.scalar(select(DocumentTextArtifact))
    assert artifact is not None
    content = LocalPrivateStorage(settings.storage_root).read(artifact.storage_key)
    payload = json.loads(content)
    assert payload["format"] == "co-ownership-facts:1.0.0"
    assert payload["fields"] and payload["page_count"] == 1
    assert b"SECRET_ATTENDEE" not in content and b"BE00 1234" not in content
    assert "SECRET_ATTENDEE" not in caplog.text and "BE00 1234" not in caplog.text
