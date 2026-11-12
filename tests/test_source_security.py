import httpx
import pytest

from viesett.integrations.http import OfficialHttpClient, SourceError


@pytest.mark.parametrize(
    "link",
    [
        "https://attacker.example/v2/gebouweenheden?adresobjectid=1",
        "http://api.basisregisters.vlaanderen.be/v2/gebouweenheden",
        "https://api.basisregisters.vlaanderen.be:444/v2/gebouweenheden",
        "https://user@api.basisregisters.vlaanderen.be/v2/gebouweenheden",
        "//127.0.0.1/v2/gebouweenheden",
        "/v2/../secret",
        "/v2/%2e%2e/secret",
        "https://api.basisregisters.vlaanderen.be.evil.test/v2/adressen",
    ],
)
async def test_untrusted_navigation_is_rejected_without_a_request(link: str) -> None:
    calls: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(200, json={})

    async with OfficialHttpClient.grar(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(SourceError):
            await client.get_json(link)
    assert calls == []
