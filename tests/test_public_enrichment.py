import json

import pytest
from httpx import AsyncClient
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import workspace
from tests.official_fixtures import OfficialFixtureService
from tests.test_property_resolution import resolve
from viesett.db.models import EvidenceItem
from viesett.db.property_models import (
    HeritageObservation,
    PropertyBuilding,
    PropertyBuildingUnit,
    PropertyIdentity,
    PropertyParcel,
    PropertyResolution,
    PublicEnrichmentRun,
)
from viesett.domain.property import FloodResult


async def test_heritage_matches_remain_distinct_and_flood_is_manual(
    property_client: AsyncClient,
    official_service: OfficialFixtureService,
) -> None:
    wid = await workspace(property_client)
    await resolve(property_client, wid)
    response = await property_client.post(f"/api/v1/workspaces/{wid}/public-enrichment/refresh")
    assert response.status_code == 200, response.text
    data = response.json()
    assert len(data["heritage"]) == 3
    assert {h["classification"] for h in data["heritage"]} == {"DESIGNATION", "INVENTORY_ONLY"}
    assert {h["type_label"] for h in data["heritage"]} == {
        "beschermd monument",
        "vastgesteld bouwkundig erfgoed",
        "bouwkundig erfgoed",
    }
    assert all(h["designation_status"] is None and h["source_uri"] for h in data["heritage"])
    assert "Onroerend Erfgoed" in {s["attribution_text"] for s in data["sources"]}
    assert data["flood"]["status"] == "MANUAL_OFFICIAL_LOOKUP_REQUIRED"
    assert data["flood"]["p_score"] is data["flood"]["g_score"] is None
    assert len(data["flood"]["parcel_references"]) == 2
    assert all(
        "capakey=" in url and "%2F" in url for url in data["flood"]["parcel_references"].values()
    )
    states = {s["provider"]: s for s in data["source_states"]}
    assert states["HERITAGE"]["current_refresh_status"] == "SUCCESS"
    assert states["FLOOD"]["current_refresh_status"] == "MANUAL_OFFICIAL_LOOKUP_REQUIRED"
    request = next(r for r in official_service.requests if r.url.host == "geo.onroerenderfgoed.be")
    geometry = json.loads(request.url.params["geometrie"])
    assert geometry["type"] == "Polygon" and "crs" not in geometry
    x, y = geometry["coordinates"][0][0]
    assert 3 < x < 5 and 50 < y < 52
    assert request.url.params["buffer"] == "0"
    assert all("waterinfo" not in r.url.host for r in official_service.requests)
    evidence = (await property_client.get(f"/api/v1/workspaces/{wid}/evidence")).json()
    heritage = [e for e in evidence if e["provider"] == "HERITAGE"]
    assert heritage and all(e["authority"] == "OFFICIAL" for e in heritage)


async def test_heritage_outage_does_not_erase_successful_data(
    property_client: AsyncClient,
    official_service: OfficialFixtureService,
    db: AsyncSession,
) -> None:
    wid = await workspace(property_client)
    await resolve(property_client, wid)
    path = f"/api/v1/workspaces/{wid}/public-enrichment/refresh"
    first = (await property_client.post(path)).json()
    count = await db.scalar(select(func.count()).select_from(EvidenceItem))
    second = (await property_client.post(path)).json()
    assert await db.scalar(select(func.count()).select_from(EvidenceItem)) == count
    official_service.status_by_path["/zoekdiensten/afbakeningen"] = 503
    failed = (await property_client.post(path)).json()
    assert failed["address"] == first["address"] and failed["heritage"] == second["heritage"]
    state = next(s for s in failed["source_states"] if s["provider"] == "HERITAGE")
    assert state["stale"] and state["current_refresh_status"] == "SOURCE_UNAVAILABLE"
    assert state["last_successful_retrieval"]
    assert failed["flood"]["status"] == "MANUAL_OFFICIAL_LOOKUP_REQUIRED"


async def test_successful_empty_heritage_expires_previous_observations(
    property_client: AsyncClient,
    official_service: OfficialFixtureService,
) -> None:
    wid = await workspace(property_client)
    await resolve(property_client, wid)
    path = f"/api/v1/workspaces/{wid}/public-enrichment/refresh"
    await property_client.post(path)
    official_service.heritage_matches = []
    data = (await property_client.post(path)).json()
    assert data["heritage"] == []
    current = (await property_client.get(f"/api/v1/workspaces/{wid}/evidence")).json()
    assert all(e["provider"] != "HERITAGE" for e in current)
    history = (
        await property_client.get(f"/api/v1/workspaces/{wid}/evidence?include_history=true")
    ).json()
    assert any(e["provider"] == "HERITAGE" and e["superseded_at"] for e in history)


async def test_invalid_heritage_response_is_explicit_and_preserves_grar(
    property_client: AsyncClient,
    official_service: OfficialFixtureService,
) -> None:
    wid = await workspace(property_client)
    await resolve(property_client, wid)
    official_service.payload_by_path["/zoekdiensten/afbakeningen"] = {"unexpected": "body"}
    data = (
        await property_client.post(f"/api/v1/workspaces/{wid}/public-enrichment/refresh")
    ).json()
    assert data["address"]["official_id"] == "1"
    assert (
        next(s for s in data["source_states"] if s["provider"] == "HERITAGE")[
            "current_refresh_status"
        ]
        == "INVALID_SOURCE_RESPONSE"
    )


async def test_missing_area_is_not_a_negative_heritage_claim(
    property_client: AsyncClient,
    official_service: OfficialFixtureService,
) -> None:
    wid = await workspace(property_client)
    official_service.building.pop("gebouwPolygoon")
    await resolve(property_client, wid)
    data = (
        await property_client.post(f"/api/v1/workspaces/{wid}/public-enrichment/refresh")
    ).json()
    state = next(s for s in data["source_states"] if s["provider"] == "HERITAGE")
    assert state["current_refresh_status"] == "NOT_APPLICABLE"
    assert state["error_code"] == "precise_property_area_unavailable"
    assert not any(r.url.host == "geo.onroerenderfgoed.be" for r in official_service.requests)


async def test_enrichment_requires_a_selected_current_property(
    property_client: AsyncClient,
    official_service: OfficialFixtureService,
) -> None:
    wid = await workspace(property_client)
    path = f"/api/v1/workspaces/{wid}/public-enrichment/refresh"
    assert (await property_client.post(path)).status_code == 409
    await resolve(property_client, wid)
    official_service.search_ids = ["1", "2"]
    await resolve(property_client, wid)
    assert (await property_client.post(path)).status_code == 409
    await property_client.patch(f"/api/v1/workspaces/{wid}", json={"status": "ARCHIVED"})
    assert (await property_client.post(path)).status_code == 409
    assert (await resolve(property_client, wid)).status_code == 409


def test_unapproved_flood_scores_cannot_enter_the_result_contract() -> None:
    with pytest.raises(ValidationError):
        FloodResult.model_validate({"status": "AVAILABLE", "p_score": "A", "g_score": "B"})
    with pytest.raises(ValidationError):
        FloodResult.model_validate({"status": "MANUAL_OFFICIAL_LOOKUP_REQUIRED", "p_score": "A"})


async def test_property_data_export_and_deletion_are_owner_scoped(
    property_client: AsyncClient,
    other_client: AsyncClient,
    db: AsyncSession,
) -> None:
    wid = await workspace(property_client)
    await resolve(property_client, wid)
    await property_client.post(f"/api/v1/workspaces/{wid}/public-enrichment/refresh")
    exported = (await property_client.get("/api/v1/me/export")).json()
    assert exported["property_resolutions"][0]["workspace_id"] == wid
    assert exported["property_snapshots"][0]["address"]["official_id"] == "1"
    assert {r["provider"] for r in exported["public_enrichment_runs"]} == {
        "GRAR",
        "HERITAGE",
        "FLOOD",
    }
    foreign = (await other_client.get("/api/v1/me/export")).json()
    assert foreign["property_resolutions"] == foreign["public_enrichment_runs"] == []
    assert wid not in json.dumps(foreign)
    assert (await property_client.delete(f"/api/v1/workspaces/{wid}")).status_code == 204
    for model in [
        PropertyIdentity,
        PropertyBuildingUnit,
        PropertyBuilding,
        PropertyParcel,
        PropertyResolution,
        PublicEnrichmentRun,
        HeritageObservation,
        EvidenceItem,
    ]:
        assert await db.scalar(select(func.count()).select_from(model)) == 0


async def test_geometry_revision_marks_heritage_stale_until_refreshed(
    property_client: AsyncClient,
    official_service: OfficialFixtureService,
) -> None:
    wid = await workspace(property_client)
    await resolve(property_client, wid)
    await property_client.post(f"/api/v1/workspaces/{wid}/public-enrichment/refresh")
    official_service.building["gebouwStatus"] = "inAanbouw"
    await resolve(property_client, wid)
    data = (await property_client.get(f"/api/v1/workspaces/{wid}/property-snapshot")).json()
    assert (
        data["heritage"]
        and next(s for s in data["source_states"] if s["provider"] == "HERITAGE")["stale"]
    )
    await property_client.post(f"/api/v1/workspaces/{wid}/public-enrichment/refresh")
    fresh = (await property_client.get(f"/api/v1/workspaces/{wid}/property-snapshot")).json()
    assert not next(s for s in fresh["source_states"] if s["provider"] == "HERITAGE")["stale"]
