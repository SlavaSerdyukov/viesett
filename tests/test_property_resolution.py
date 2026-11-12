from uuid import uuid4

import httpx
import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import workspace
from tests.official_fixtures import OfficialFixtureService
from viesett.db.models import EvidenceItem


async def resolve(client: AsyncClient, wid: str, **selected: str) -> httpx.Response:
    return await client.post(
        f"/api/v1/workspaces/{wid}/property-resolution",
        json={
            "query": "  Teststr 42   Gent  ",
            **selected,
        },
    )


async def test_unique_address_resolves_without_questions(property_client: AsyncClient) -> None:
    wid = await workspace(property_client)
    response = await resolve(property_client, wid)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == "RESOLVED" and data["applied_to_snapshot"]
    assert data["input_address_query"] == "Teststr 42 Gent"
    assert data["address"]["canonical_address"] == "Teststraat 42, 9000 Gent"
    assert data["selected_building_unit"]["official_id"] == "10"
    assert data["building"]["official_id"] == "100"
    assert len(data["parcels"]) == 2 and data["parcels"][0]["capakey"] == "11001B0001/00S000"
    assert data["address"]["native_geometry"]["crs"] == "EPSG:31370"
    read = await property_client.get(f"/api/v1/workspaces/{wid}/property-resolution")
    assert read.json() == data
    snapshot = (await property_client.get(f"/api/v1/workspaces/{wid}/property-snapshot")).json()
    assert snapshot["address"]["official_id"] == "1" and not snapshot["stale"]
    assert (
        len(snapshot["parcels"]) == 2
        and snapshot["sources"][0]["attribution_text"] == "Bron: Digitaal Vlaanderen"
    )


async def test_raw_input_has_no_official_evidence(
    property_client: AsyncClient, db: AsyncSession
) -> None:
    wid = await workspace(property_client)
    assert (await property_client.get(f"/api/v1/workspaces/{wid}/property-snapshot")).json()[
        "address"
    ] is None
    assert await db.scalar(select(func.count()).select_from(EvidenceItem)) == 0
    assert (
        await property_client.get(f"/api/v1/workspaces/{wid}/property-resolution")
    ).status_code == 404


async def test_not_found_is_distinct_from_outage(
    property_client: AsyncClient,
    official_service: OfficialFixtureService,
) -> None:
    wid = await workspace(property_client)
    official_service.search_ids = []
    assert (await resolve(property_client, wid)).json()["status"] == "NOT_FOUND"
    official_service.status_by_path["/v2/adressen/zoeken"] = 503
    result = (await resolve(property_client, wid)).json()
    assert (
        result["status"] == "UPSTREAM_UNAVAILABLE"
        and result["error_code"] == "upstream_server_error"
    )


async def test_multiple_addresses_and_validated_bus_selection(
    property_client: AsyncClient,
    official_service: OfficialFixtureService,
) -> None:
    wid = await workspace(property_client)
    official_service.search_ids = ["1", "2"]
    choices = (await resolve(property_client, wid)).json()
    assert choices["status"] == "NEEDS_SELECTION" and len(choices["address_candidates"]) == 2
    selected = (
        await resolve(
            property_client,
            wid,
            selected_address_object_id="2",
            selected_building_unit_object_id="20",
        )
    ).json()
    assert selected["status"] == "RESOLVED"
    assert selected["address"]["box_number"] == "1"
    invalid = (
        await resolve(
            property_client,
            wid,
            selected_address_object_id="2",
            selected_building_unit_object_id="10",
        )
    ).json()
    assert invalid["status"] == "INVALID_SOURCE_RESPONSE"
    assert "selection_not_related" in invalid["error_code"]


async def test_multiple_private_units_never_selects_first_and_common_is_excluded(
    property_client: AsyncClient,
    official_service: OfficialFixtureService,
) -> None:
    wid = await workspace(property_client)
    official_service.units_by_address["1"] = ["10", "11", "12"]
    result = (await resolve(property_client, wid)).json()
    assert result["status"] == "NEEDS_SELECTION"
    assert {u["official_id"] for u in result["building_unit_candidates"]} == {"10", "11"}
    assert result["selected_building_unit"] is None
    chosen = (
        await resolve(
            property_client,
            wid,
            selected_address_object_id="1",
            selected_building_unit_object_id="11",
        )
    ).json()
    assert chosen["selected_building_unit"]["official_id"] == "11"
    common = (
        await resolve(
            property_client,
            wid,
            selected_address_object_id="1",
            selected_building_unit_object_id="12",
        )
    ).json()
    assert common["status"] == "INVALID_SOURCE_RESPONSE"


@pytest.mark.parametrize("relationship", ["units", "parcels", "building"])
async def test_missing_relations_are_partial(
    property_client: AsyncClient,
    official_service: OfficialFixtureService,
    relationship: str,
) -> None:
    wid = await workspace(property_client)
    if relationship == "units":
        official_service.units_by_address["1"] = []
    elif relationship == "parcels":
        official_service.parcels_by_address["1"] = []
    else:
        official_service.status_by_path["/v2/gebouwen/100"] = 404
    result = (await resolve(property_client, wid)).json()
    assert result["status"] == "PARTIALLY_RESOLVED" and result["missing_relationships"]
    if relationship == "parcels":
        assert result["parcels"] == []


async def test_navigation_and_documented_relationship_fallback(
    property_client: AsyncClient,
    official_service: OfficialFixtureService,
) -> None:
    wid = await workspace(property_client)
    official_service.addresses["1"].pop("_links")
    assert (await resolve(property_client, wid)).json()["status"] == "RESOLVED"
    assert any(
        r.url.path == "/v2/percelen" and r.url.params["adresobjectid"] == "1"
        for r in official_service.requests
    )
    official_service.addresses["1"]["_links"] = {
        "gebouweenheden": {"href": "https://evil.example/v2/gebouweenheden"}
    }
    assert (await resolve(property_client, wid)).json()["status"] == "INVALID_SOURCE_RESPONSE"
    assert all(r.url.host != "evil.example" for r in official_service.requests)


@pytest.mark.parametrize(
    "method,path",
    [
        ("POST", "property-resolution"),
        ("GET", "property-resolution"),
        ("POST", "public-enrichment/refresh"),
        ("GET", "property-snapshot"),
    ],
)
async def test_new_api_ownership_is_uniform(
    property_client: AsyncClient,
    other_client: AsyncClient,
    official_service: OfficialFixtureService,
    method: str,
    path: str,
) -> None:
    foreign_wid = await workspace(other_client)
    foreign = await property_client.request(
        method,
        f"/api/v1/workspaces/{foreign_wid}/{path}",
        json={"query": "Teststraat 42"} if method == "POST" else None,
    )
    absent = await property_client.request(
        method,
        f"/api/v1/workspaces/{uuid4()}/{path}",
        json={"query": "Teststraat 42"} if method == "POST" else None,
    )
    assert foreign.status_code == absent.status_code == 404
    assert foreign.json() == absent.json()
    assert official_service.requests == []


async def test_evidence_is_official_versioned_and_unchanged_is_deduplicated(
    property_client: AsyncClient,
    official_service: OfficialFixtureService,
    db: AsyncSession,
) -> None:
    wid = await workspace(property_client)
    await resolve(property_client, wid)
    first = (await property_client.get(f"/api/v1/workspaces/{wid}/evidence")).json()
    assert first and all(e["authority"] == "OFFICIAL" and e["source_retrieved_at"] for e in first)
    assert all(e["provider"] == "GRAR" and e["source_uri"] and e["source_version"] for e in first)
    await resolve(property_client, wid)
    assert await db.scalar(select(func.count()).select_from(EvidenceItem)) == len(first)
    official_service.addresses["1"]["volledigAdres"] = {
        "geografischeNaam": {"spelling": "Updated official address", "taal": "nl"}
    }
    await resolve(property_client, wid)
    history = (
        await property_client.get(f"/api/v1/workspaces/{wid}/evidence?include_history=true")
    ).json()
    old = next(
        e for e in history if e["key"] == "property.address.canonical" and e["superseded_at"]
    )
    current = (await property_client.get(f"/api/v1/workspaces/{wid}/evidence")).json()
    new = next(e for e in current if e["key"] == "property.address.canonical")
    assert new["supersedes_evidence_id"] == old["id"] and old["id"] in {e["id"] for e in first}


async def test_previous_identity_survives_outage_and_staleness_is_explicit(
    property_client: AsyncClient,
    official_service: OfficialFixtureService,
) -> None:
    wid = await workspace(property_client)
    await resolve(property_client, wid)
    official_service.status_by_path["/v2/adressen/zoeken"] = 500
    await resolve(property_client, wid)
    snapshot = (await property_client.get(f"/api/v1/workspaces/{wid}/property-snapshot")).json()
    assert snapshot["address"]["official_id"] == "1" and snapshot["stale"]
    assert snapshot["resolution_status"] == "UPSTREAM_UNAVAILABLE"
    state = next(s for s in snapshot["source_states"] if s["provider"] == "GRAR")
    assert (
        state["last_successful_retrieval"]
        and state["current_refresh_status"] == "SOURCE_UNAVAILABLE"
    )


async def test_malformed_source_and_unvalidated_selected_id_are_not_found_guesses(
    property_client: AsyncClient,
    official_service: OfficialFixtureService,
) -> None:
    wid = await workspace(property_client)
    invalid = (await resolve(property_client, wid, selected_address_object_id="999")).json()
    assert invalid["status"] == "INVALID_SOURCE_RESPONSE"
    official_service.payload_by_path["/v2/adressen/zoeken"] = {
        "unexpected": "UPSTREAM_PRIVATE_BODY"
    }
    bad = await resolve(property_client, wid)
    assert bad.json()["status"] == "INVALID_SOURCE_RESPONSE"
    assert "UPSTREAM_PRIVATE_BODY" not in bad.text
