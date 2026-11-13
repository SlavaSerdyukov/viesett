import json
import socket
import ssl
from copy import deepcopy
from pathlib import Path
from typing import Any

import httpx
import pytest
from pydantic import SecretStr

from tests.official_fixtures import OfficialFixtureService
from viesett.core.config import Settings
from viesett.integrations.grar import GrarClient
from viesett.integrations.http import OfficialHttpClient, SourceError, transport_diagnostic
from viesett.tools.check_grar_contract import check_contract, fetch_schema
from viesett.tools.verify_grar import verify


@pytest.mark.parametrize("key", [None, "SYNTHETIC_ONLY_API_KEY"])
async def test_current_documented_search_request_and_normalization(
    settings: Settings, key: str | None
) -> None:
    service = OfficialFixtureService()
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return service.handler(request)

    config = settings.model_copy(
        update={"grar_api_key": SecretStr(key) if key else None, "source_min_interval": 0}
    )
    async with OfficialHttpClient.grar(config, transport=httpx.MockTransport(handler)) as http:
        addresses, truncated = await GrarClient(http).search("Teststraat 42, 9000 Gent")
    assert not truncated and addresses[0][0].canonical_address == "Teststraat 42, 9000 Gent"
    request = requests[0]
    assert request.url.path == "/v2/adressen/zoeken"
    assert dict(request.url.params) == {
        "q": "Teststraat 42, 9000 Gent",
        "resultaatType": "adressen",
        "status": "inGebruik",
        "limit": "6",
    }
    assert request.headers.get("x-api-key") == key
    assert requests[1].url.path == "/v2/adressen/1"
    assert addresses[0][0].source_uri == "https://data.vlaanderen.be/id/adres/1"


def official_contract() -> dict[str, Any]:
    value: dict[str, Any] = json.loads(Path("tests/fixtures/grar-contract-m6.json").read_text())
    return value


def test_contract_snapshot_and_detected_drift() -> None:
    schema = official_contract()
    assert check_contract(schema) == []
    changed = deepcopy(schema)
    parameters = changed["paths"]["/v2/adressen/zoeken"]["get"]["parameters"]
    parameters[0]["name"] = "query"
    assert "SEARCH_PARAMETER_q_MISSING" in check_contract(changed)
    parameters[-2]["description"] = '"Address"'
    assert "SEARCH_VOCABULARY_resultaatType_CHANGED" in check_contract(changed)
    assert check_contract({}) == ["INVALID_SCHEMA"]


async def test_schema_fetch_is_fixed_read_only_bounded_and_credential_free() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert (
            str(request.url)
            == "https://docs.basisregisters.vlaanderen.be/docs/v2/docs.json?culture=en-GB"
        )
        assert "x-api-key" not in request.headers and "authorization" not in request.headers
        return httpx.Response(200, json=official_contract())

    assert check_contract(await fetch_schema(httpx.MockTransport(handler))) == []


@pytest.mark.parametrize(
    "error,expected",
    [
        (httpx.ConnectTimeout("private"), "CONNECT_TIMEOUT"),
        (httpx.ReadTimeout("private"), "READ_TIMEOUT"),
        (httpx.ConnectError("private"), "NETWORK_FAILURE"),
        (ssl.SSLError("private"), "TLS_FAILURE"),
        (socket.gaierror("private"), "DNS_FAILURE"),
    ],
)
def test_safe_transport_categories_never_depend_on_exception_text(
    error: BaseException, expected: str
) -> None:
    assert transport_diagnostic(error) == expected
    wrapper = httpx.ConnectError("SECRET_KEY_AND_ADDRESS")
    wrapper.__cause__ = error
    if expected in {"DNS_FAILURE", "TLS_FAILURE"}:
        assert transport_diagnostic(wrapper) == expected


@pytest.mark.parametrize(
    "status,expected",
    [(400, "HTTP_4XX"), (429, "HTTP_429"), (503, "HTTP_5XX"), (302, "INVALID_CONTRACT")],
)
async def test_http_diagnostics_do_not_change_safe_product_errors(
    settings: Settings, status: int, expected: str, caplog: pytest.LogCaptureFixture
) -> None:
    events: list[tuple[str, str]] = []
    config = settings.model_copy(
        update={"source_attempts": 1, "grar_api_key": SecretStr("SYNTHETIC_SECRET")}
    )
    async with OfficialHttpClient.grar(
        config,
        transport=httpx.MockTransport(
            lambda r: httpx.Response(status, text="PRIVATE_PROVIDER_BODY")
        ),
        diagnostic=lambda stage, category: events.append((stage, category)),
    ) as http:
        with pytest.raises(SourceError):
            await http.get_json("/v2/adressen/zoeken", {"q": "PRIVATE_ADDRESS"})
    assert events == [("SEARCH", expected)]
    assert (
        "PRIVATE_PROVIDER_BODY" not in caplog.text
        and "SYNTHETIC_SECRET" not in caplog.text
        and "PRIVATE_ADDRESS" not in caplog.text
    )


async def test_smoke_is_explicit_and_synthetic_results_are_never_live(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def probe() -> list[dict[str, str]]:
        return [{"stage": "DNS", "status": "SUCCESS"}, {"stage": "TLS", "status": "SUCCESS"}]

    with pytest.raises(RuntimeError):
        await verify(settings, probe=probe)
    config = settings.model_copy(update={"run_live_source_tests": True, "source_min_interval": 0})
    output = await verify(
        config, transport=httpx.MockTransport(OfficialFixtureService().handler), probe=probe
    )
    assert output["result"] == "SYNTHETIC_SUCCESS" and output["parcel_count"] == 2
    assert output["building_unit_normalized"]
    assert "?" not in json.dumps(output)
    assert "Teststraat" not in json.dumps(output) and "example_query" not in output
    monkeypatch.setenv("CI", "true")
    with pytest.raises(RuntimeError):
        await verify(config, probe=probe)


async def test_smoke_network_block_has_no_private_diagnostics(settings: Settings) -> None:
    async def blocked() -> list[dict[str, str]]:
        return [{"stage": "CONNECT", "status": "NETWORK_BLOCKED"}]

    output = await verify(
        settings.model_copy(update={"run_live_source_tests": True}),
        transport=httpx.MockTransport(OfficialFixtureService().handler),
        probe=blocked,
    )
    assert output["result"] == "NETWORK_BLOCKED"


async def test_smoke_no_match_is_not_reported_as_provider_downtime(settings: Settings) -> None:
    async def probe() -> list[dict[str, str]]:
        return [{"stage": "TLS", "status": "SUCCESS"}]

    service = OfficialFixtureService(search_ids=[])
    output = await verify(
        settings.model_copy(update={"run_live_source_tests": True}),
        transport=httpx.MockTransport(service.handler),
        probe=probe,
    )
    assert output["result"] == "OTHER_SAFE_CATEGORY" and output["resolution_status"] == "NOT_FOUND"
