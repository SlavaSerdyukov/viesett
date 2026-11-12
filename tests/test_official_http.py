import logging
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime

import httpx
import pytest
from pydantic import SecretStr

from viesett.core.config import Settings
from viesett.integrations.http import HERITAGE_HOST, OfficialHttpClient, SourceError


def config() -> Settings:
    return Settings(source_min_interval=0, source_retry_base=0, source_attempts=2)


@pytest.mark.parametrize("api_key", [None, SecretStr("synthetic-grar-key-never-log")])
async def test_optional_key_header_and_source_logs_are_private(
    api_key: SecretStr | None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    settings = config().model_copy(update={"grar_api_key": api_key})
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"ok": True})

    caplog.set_level(logging.DEBUG)
    async with OfficialHttpClient.grar(settings, transport=httpx.MockTransport(handler)) as client:
        assert await client.get_json("/v2/adressen/zoeken", {"query": "PRIVATE_ADDRESS_QUERY"}) == {
            "ok": True
        }
    assert bool(requests[0].headers.get("x-api-key")) == bool(api_key)
    assert requests[0].headers["User-Agent"].startswith("Viesett/")
    async with OfficialHttpClient(
        HERITAGE_HOST, settings, transport=httpx.MockTransport(handler)
    ) as heritage:
        await heritage.get_json("/zoekdiensten/afbakeningen")
    assert "x-api-key" not in requests[1].headers
    assert "synthetic-grar-key-never-log" not in caplog.text
    assert "PRIVATE_ADDRESS_QUERY" not in caplog.text


@pytest.mark.parametrize("status", [429, 500, 503])
async def test_retries_are_bounded(status: int) -> None:
    calls = 0
    sleeps = []

    async def sleep(delay: float) -> None:
        sleeps.append(delay)

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(status, json={"private": "UPSTREAM_BODY"})

    async with OfficialHttpClient.grar(
        config(), transport=httpx.MockTransport(handler), sleep=sleep
    ) as client:
        with pytest.raises(SourceError) as error:
            await client.get_json("/v2/adressen/1")
    assert calls == 2 and len(sleeps) == 1
    assert "UPSTREAM_BODY" not in str(error.value)


@pytest.mark.parametrize(
    "retry_after", ["2", format_datetime(datetime.now(UTC) + timedelta(seconds=2))]
)
async def test_retry_after_is_respected(retry_after: str) -> None:
    calls = 0
    sleeps = []

    async def sleep(delay: float) -> None:
        sleeps.append(delay)

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return (
            httpx.Response(429, headers={"Retry-After": retry_after})
            if calls == 1
            else httpx.Response(200, json={"ok": True})
        )

    async with OfficialHttpClient.grar(
        config(), transport=httpx.MockTransport(handler), sleep=sleep
    ) as client:
        assert await client.get_json("/v2/adressen/1") == {"ok": True}
    assert calls == 2 and 0 <= sleeps[0] <= 2


async def test_long_retry_after_stops_instead_of_retrying_early() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(429, headers={"Retry-After": "3600"})

    async with OfficialHttpClient.grar(config(), transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(SourceError, match="retry_after_exceeds_budget"):
            await client.get_json("/v2/adressen/1")
    assert calls == 1


@pytest.mark.parametrize(
    "status,content,headers",
    [
        (200, b"not json secret", {"Content-Type": "application/json"}),
        (200, b"<html>not JSON</html>", {"Content-Type": "text/html"}),
        (302, b"", {"Location": "http://169.254.169.254/"}),
        (403, b"private access information", {}),
        (404, b"missing", {}),
        (200, b"x" * (2 * 1024 * 1024 + 1), {"Content-Type": "application/json"}),
    ],
)
async def test_malformed_unexpected_and_oversized_responses_fail_safely(
    status: int,
    content: bytes,
    headers: dict[str, str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(status, content=content, headers=headers)

    caplog.set_level(logging.DEBUG)
    async with OfficialHttpClient.grar(config(), transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(SourceError) as error:
            await client.get_json("/v2/adressen/1")
    assert calls == 1 and "secret" not in caplog.text + str(error.value)
    assert "private access information" not in caplog.text + str(error.value)


async def test_transport_failure_has_no_response_or_secret_repr() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ConnectError("PRIVATE_PROVIDER_EXCEPTION", request=request)

    async with OfficialHttpClient.grar(config(), transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(SourceError, match="transport_unavailable"):
            await client.get_json("/v2/adressen/1")
    assert calls == 2


def test_official_alias_canonicalizes_to_the_single_request_host() -> None:
    client = OfficialHttpClient.grar(
        config(), transport=httpx.MockTransport(lambda r: httpx.Response(200))
    )
    assert (
        client.safe_path("https://basisregisters.vlaanderen.be/api/v2/percelen?adresobjectid=1")
        == "/v2/percelen?adresobjectid=1"
    )
