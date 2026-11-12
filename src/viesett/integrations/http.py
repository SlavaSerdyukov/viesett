import asyncio
import logging
import re
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from types import TracebackType
from typing import Self
from urllib.parse import unquote, urlsplit

import httpx
from pydantic import JsonValue, RootModel, ValidationError

from viesett.core.config import Settings

GRAR_HOST = "api.basisregisters.vlaanderen.be"
HERITAGE_HOST = "geo.onroerenderfgoed.be"


class JsonDocument(RootModel[JsonValue]):
    """Typed JSON decoding without retaining or logging the original response."""


class SourceError(Exception):
    def __init__(self, code: str, *, invalid: bool = False, not_found: bool = False) -> None:
        super().__init__(code)
        self.code = code
        self.invalid = invalid
        self.not_found = not_found


def object_value(value: JsonValue) -> dict[str, JsonValue]:
    if not isinstance(value, dict):
        raise SourceError("invalid_object", invalid=True)
    return value


def array_value(value: JsonValue) -> list[JsonValue]:
    if not isinstance(value, list):
        raise SourceError("invalid_array", invalid=True)
    return value


def string_value(value: JsonValue, *, maximum: int = 500) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise SourceError("invalid_string", invalid=True)
    return value


class OfficialHttpClient:
    """Two concrete official services share bounded, content-free HTTP handling."""

    def __init__(
        self,
        host: str,
        settings: Settings,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        if host not in {GRAR_HOST, HERITAGE_HOST}:
            raise ValueError("Unsupported official source")
        self.host = host
        self.settings = settings
        self._sleep = sleep
        self._lock = asyncio.Lock()
        self._next_request = 0.0
        # Third-party DEBUG/INFO logs include URLs or headers. Neither is safe here.
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)
        headers = {
            "User-Agent": "Viesett/0.2.0 official-property-lookup",
            "Accept": "application/json",
        }
        if host == GRAR_HOST and settings.grar_api_key:
            headers["x-api-key"] = settings.grar_api_key.get_secret_value()
        self.client = httpx.AsyncClient(
            base_url=f"https://{host}",
            headers=headers,
            follow_redirects=False,
            trust_env=False,
            timeout=httpx.Timeout(
                connect=settings.source_connect_timeout,
                read=settings.source_read_timeout,
                write=settings.source_write_timeout,
                pool=settings.source_pool_timeout,
            ),
            limits=httpx.Limits(max_connections=1, max_keepalive_connections=1),
            transport=transport,
        )

    @classmethod
    def grar(
        cls,
        settings: Settings | None = None,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> "OfficialHttpClient":
        return cls(GRAR_HOST, settings or Settings(), transport=transport, sleep=sleep)

    def safe_path(self, link: str) -> str:
        if "\\" in link or any(ord(c) < 32 for c in link) or link.startswith("//"):
            raise SourceError("unsafe_navigation", invalid=True)
        try:
            parts = urlsplit(link)
            if parts.username or parts.password or parts.fragment or parts.port not in {None, 443}:
                raise ValueError
        except ValueError:
            raise SourceError("unsafe_navigation", invalid=True) from None
        path = parts.path
        if self.host == GRAR_HOST and parts.hostname == "basisregisters.vlaanderen.be":
            # This official alias appears in provider response options. Canonicalize
            # its documented /api/v2 prefix; never send credentials to another host.
            if not path.startswith("/api/v2/"):
                raise SourceError("unsafe_navigation", invalid=True)
            path = path.removeprefix("/api")
        elif parts.hostname not in {None, self.host}:
            raise SourceError("unsafe_navigation", invalid=True)
        if (parts.scheme and parts.scheme != "https") or (parts.netloc and not parts.scheme):
            raise SourceError("unsafe_navigation", invalid=True)
        if unquote(path) != path or any(p in {".", ".."} for p in path.split("/")):
            raise SourceError("unsafe_navigation", invalid=True)
        if self.host == GRAR_HOST:
            if not re.fullmatch(
                r"/v2/(adressen|gebouweenheden|gebouwen|percelen)(/(zoeken|[A-Za-z0-9_-]+))?", path
            ):
                raise SourceError("unsafe_navigation", invalid=True)
        elif path != "/zoekdiensten/afbakeningen":
            raise SourceError("unsafe_navigation", invalid=True)
        return path + (f"?{parts.query}" if parts.query else "")

    def _retry_delay(self, value: str | None, attempt: int) -> float:
        if value is not None:
            try:
                delay = float(value)
            except ValueError:
                try:
                    delay = (parsedate_to_datetime(value) - datetime.now(UTC)).total_seconds()
                except (ValueError, TypeError, OverflowError):
                    delay = self.settings.source_retry_base * float(2**attempt)
            # If the provider asks us to wait beyond this request's budget, stop.
            if delay > 5:
                raise SourceError("retry_after_exceeds_budget")
            return max(0, delay)
        return self.settings.source_retry_base * float(2**attempt)

    async def get_json(
        self,
        link: str,
        params: dict[str, str] | None = None,
    ) -> JsonValue:
        path = self.safe_path(link)
        async with self._lock:
            for attempt in range(self.settings.source_attempts):
                gap = self._next_request - time.monotonic()
                if gap > 0:
                    await self._sleep(gap)
                self._next_request = time.monotonic() + self.settings.source_min_interval
                try:
                    async with self.client.stream("GET", path, params=params) as response:
                        if response.status_code in {404, 410}:
                            raise SourceError("object_not_found", not_found=True)
                        if response.status_code == 429 or response.status_code >= 500:
                            if attempt + 1 >= self.settings.source_attempts:
                                raise SourceError(
                                    "rate_limited"
                                    if response.status_code == 429
                                    else "upstream_server_error"
                                )
                            delay = self._retry_delay(response.headers.get("Retry-After"), attempt)
                        elif response.status_code != 200:
                            raise SourceError(
                                "unexpected_http_status", invalid=300 <= response.status_code < 400
                            )
                        else:
                            media = response.headers.get("content-type", "").split(";")[0]
                            if media not in {
                                "application/json",
                                "application/ld+json",
                                "application/geo+json",
                            }:
                                raise SourceError("unexpected_media_type", invalid=True)
                            body = bytearray()
                            async for chunk in response.aiter_bytes(chunk_size=65536):
                                body.extend(chunk)
                                if len(body) > 2 * 1024 * 1024:
                                    raise SourceError("response_too_large", invalid=True)
                            try:
                                return JsonDocument.model_validate_json(bytes(body)).root
                            except (ValidationError, RecursionError):
                                raise SourceError("invalid_json", invalid=True) from None
                except httpx.RequestError:
                    if attempt + 1 >= self.settings.source_attempts:
                        raise SourceError("transport_unavailable") from None
                    delay = self._retry_delay(None, attempt)
                await self._sleep(delay)
        raise SourceError("upstream_unavailable")

    async def aclose(self) -> None:
        await self.client.aclose()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.aclose()
