from copy import deepcopy
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import JsonValue
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import workspace
from tests.official_fixtures import HOST, PARCEL_IDS, OfficialFixtureService
from tests.test_property_resolution import resolve
from viesett.api.app import create_app
from viesett.core.config import Settings
from viesett.domain.property import ResolutionRequest
from viesett.integrations.grar import GrarClient
from viesett.integrations.http import OfficialHttpClient
from viesett.integrations.smoke import live_source_smoke
from viesett.services.auth import provision_account


@pytest.mark.parametrize("exponent", ["_", "0"])
async def test_parcel_without_letter_exponent_survives_resolution_and_flood_reference(
    property_client: AsyncClient,
    official_service: OfficialFixtureService,
    exponent: str,
) -> None:
    wid = await workspace(property_client)
    official_id = f"11001B0001-00{exponent}000"
    capakey = official_id.replace("-", "/")
    official_service.parcels_by_address["1"] = [official_id]
    result = (await resolve(property_client, wid)).json()
    assert result["status"] == "RESOLVED"
    assert result["parcels"][0]["official_id"] == official_id
    snapshot = (
        await property_client.post(f"/api/v1/workspaces/{wid}/public-enrichment/refresh")
    ).json()
    assert snapshot["parcels"][0]["capakey"] == capakey
    link = snapshot["flood"]["parcel_references"][capakey]
    assert parse_qs(urlsplit(link).query) == {"capakey": [capakey]}
    evidence = (await property_client.get(f"/api/v1/workspaces/{wid}/evidence")).json()
    assert any(
        e["typed_value"] == {"kind": "text", "value": capakey} and e["provider"] == "GRAR"
        for e in evidence
    )


@pytest.mark.parametrize("retain_filter", [True, False])
async def test_relation_pagination_preserves_every_parcel(
    official_service: OfficialFixtureService,
    retain_filter: bool,
) -> None:
    original = official_service.handler

    def paginated(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v2/percelen":
            offset = int(request.url.params.get("offset", "0"))
            identifier = PARCEL_IDS[offset]
            payload: dict[str, JsonValue] = {
                "percelen": [
                    {
                        "identificator": {"objectId": identifier},
                        "detail": HOST + "/v2/percelen/" + identifier,
                    }
                ]
            }
            if offset == 0:
                payload["volgende"] = "/v2/percelen?offset=1&limit=1" + (
                    "&adresobjectid=1" if retain_filter else ""
                )
            return httpx.Response(200, json=payload)
        return original(request)

    transport = httpx.MockTransport(paginated)
    async with OfficialHttpClient.grar(
        Settings(source_min_interval=0), transport=transport
    ) as http:
        result = await GrarClient(http).resolve(ResolutionRequest(query="Synthetic property 42"))
    assert result.status == "RESOLVED" and len(result.parcels) == 2


@pytest.mark.parametrize(
    "next_link",
    [
        "/v2/percelen?adresobjectid=1",
        "https://attacker.example/v2/percelen?adresobjectid=1",
        "/v2/percelen?adresobjectid=999",
        "/v2/gebouweenheden?adresobjectid=1",
    ],
)
async def test_bad_pagination_or_relationship_context_is_invalid(next_link: str) -> None:
    service = OfficialFixtureService()
    service.payload_by_path["/v2/percelen"] = {"percelen": [], "volgende": next_link}
    async with OfficialHttpClient.grar(
        Settings(source_min_interval=0), transport=httpx.MockTransport(service.handler)
    ) as http:
        result = await GrarClient(http).resolve(ResolutionRequest(query="Synthetic 42"))
    assert result.status == "INVALID_SOURCE_RESPONSE"
    assert all(request.url.host != "attacker.example" for request in service.requests)


@pytest.mark.parametrize(
    "case",
    [
        "unit_relationship",
        "building_relationship",
        "parcel_relationship",
        "bad_capakey",
        "unknown_function",
        "unknown_status",
    ],
)
async def test_inconsistent_official_relationships_fail_closed(
    property_client: AsyncClient,
    official_service: OfficialFixtureService,
    case: str,
) -> None:
    wid = await workspace(property_client)
    if case == "unit_relationship":
        official_service.units["10"]["adressen"] = [{"objectId": "2"}]
    elif case == "building_relationship":
        official_service.building["gebouweenheden"] = [{"objectId": "20"}]
    elif case in {"parcel_relationship", "bad_capakey"}:
        official_service.payload_by_path["/v2/percelen/" + PARCEL_IDS[0]] = {
            "identificator": {
                "id": "https://data.vlaanderen.be/id/perceel/" + PARCEL_IDS[0],
                "objectId": PARCEL_IDS[0],
            },
            "caPaKey": "bad" if case == "bad_capakey" else PARCEL_IDS[0].replace("-", "/"),
            "perceelStatus": "gerealiseerd",
            "adressen": [{"objectId": "2"}],
        }
    elif case == "unknown_function":
        official_service.units["10"]["functie"] = "guessedResidential"
    else:
        official_service.addresses["1"]["adresStatus"] = "unknown-status"
    result = (await resolve(property_client, wid)).json()
    assert result["status"] == "INVALID_SOURCE_RESPONSE"


async def test_missing_unit_detail_never_selects_the_remaining_unit(
    property_client: AsyncClient,
    official_service: OfficialFixtureService,
) -> None:
    wid = await workspace(property_client)
    official_service.units_by_address["1"] = ["10", "11"]
    official_service.status_by_path["/v2/gebouweenheden/11"] = 404
    result = (await resolve(property_client, wid)).json()
    assert result["status"] == "PARTIALLY_RESOLVED" and result["selected_building_unit"] is None


async def test_withdrawn_address_between_search_and_detail_is_not_an_outage(
    property_client: AsyncClient,
    official_service: OfficialFixtureService,
) -> None:
    wid = await workspace(property_client)
    official_service.status_by_path["/v2/adressen/1"] = 410
    assert (await resolve(property_client, wid)).json()["status"] == "NOT_FOUND"


async def test_exact_full_canonical_address_can_disambiguate_without_a_question(
    property_client: AsyncClient,
    official_service: OfficialFixtureService,
) -> None:
    wid = await workspace(property_client)
    official_service.search_ids = ["1", "2"]
    result = await property_client.post(
        f"/api/v1/workspaces/{wid}/property-resolution",
        json={
            "query": "Teststraat 42 bus 1, 9000 Gent",
        },
    )
    assert result.json()["status"] == "RESOLVED" and result.json()["address"]["official_id"] == "2"


async def test_sources_disabled_is_explicit_without_network(
    settings: Settings,
    db: AsyncSession,
    official_service: OfficialFixtureService,
) -> None:
    _, token = await provision_account(db)
    app = create_app(
        settings.model_copy(update={"official_sources_enabled": False}),
        source_transport=httpx.MockTransport(official_service.handler),
    )
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"Authorization": "Bearer " + token},
    ) as client:
        wid = await workspace(client)
        assert (await resolve(client, wid)).json()["status"] == "UPSTREAM_UNAVAILABLE"
    assert official_service.requests == []
    await app.state.runtime.sources.aclose()
    await app.state.engine.dispose()


async def test_live_smoke_is_opt_in_and_uses_only_mocked_official_contracts(
    settings: Settings,
    official_service: OfficialFixtureService,
) -> None:
    with pytest.raises(RuntimeError, match="opt into"):
        await live_source_smoke(settings.model_copy(update={"run_live_source_tests": False}))
    config = settings.model_copy(update={"run_live_source_tests": True, "source_min_interval": 0})
    result = await live_source_smoke(config, httpx.MockTransport(official_service.handler))
    assert isinstance(result["grar"], dict) and result["grar"]["status"] == "RESOLVED"
    assert isinstance(result["heritage"], dict) and result["heritage"]["status"] == "SUCCESS"
    assert all(
        r.url.params.get("query", "Dahliastraat 97, 9000 Gent") == "Dahliastraat 97, 9000 Gent"
        for r in official_service.requests
    )


async def test_production_requires_explicit_public_source_review(settings: Settings) -> None:
    from viesett.integrations.sources import PublicSources

    config = settings.model_copy(
        update={"environment": "production", "official_sources_reviewed": False}
    )
    sources = PublicSources(config)
    assert not sources.enabled
    await sources.aclose()


@pytest.mark.parametrize("case", ["id", "uri", "type", "category", "conflict"])
async def test_heritage_contract_cannot_smuggle_other_objects(
    property_client: AsyncClient,
    official_service: OfficialFixtureService,
    case: str,
) -> None:
    wid = await workspace(property_client)
    await resolve(property_client, wid)
    bad = deepcopy(official_service.heritage_matches[0])
    if case == "id":
        bad["id"] = True
    elif case == "uri":
        bad["uri"] = "https://attacker.example/1"
    elif case == "type":
        bad["type"] = {"uri": "https://attacker.example/type", "label": "not official"}
    elif case == "category":
        bad["categorie"] = "invented-category"
    else:
        bad["naam"] = "Conflicting title for the same source identifier"
    official_service.heritage_matches.append(bad)
    data = (
        await property_client.post(f"/api/v1/workspaces/{wid}/public-enrichment/refresh")
    ).json()
    state = next(s for s in data["source_states"] if s["provider"] == "HERITAGE")
    assert state["current_refresh_status"] == "INVALID_SOURCE_RESPONSE"
