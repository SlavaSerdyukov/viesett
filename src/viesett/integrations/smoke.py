import asyncio

import httpx
from pydantic import JsonValue

from viesett.core.config import Settings
from viesett.domain.property import ResolutionRequest, ResolutionResult, ResolutionStatus
from viesett.integrations.http import SourceError
from viesett.integrations.sources import PublicSources, flood_lookup

EXAMPLE_QUERY = "Dahliastraat 97, 9000 Gent"


async def live_source_smoke(
    settings: Settings,
    transport: httpx.AsyncBaseTransport | None = None,
) -> dict[str, JsonValue]:
    if not settings.run_live_source_tests:
        raise RuntimeError(
            "Set VIESETT_RUN_LIVE_SOURCE_TESTS=1 to opt into the official example smoke test"
        )
    sources = PublicSources(settings, transport)
    try:
        if not sources.enabled:
            return {"grar": {"status": "UPSTREAM_UNAVAILABLE", "error_code": "sources_disabled"}}
        try:
            async with asyncio.timeout(settings.source_operation_timeout):
                result = await sources.grar.resolve(ResolutionRequest(query=EXAMPLE_QUERY))
        except TimeoutError:
            result = ResolutionResult(
                status=ResolutionStatus.UPSTREAM_UNAVAILABLE, error_code="source_operation_timeout"
            )
        heritage: dict[str, JsonValue] = {"status": "NOT_APPLICABLE"}
        if result.building and result.building.native_geometry:
            try:
                async with asyncio.timeout(settings.source_operation_timeout):
                    matches = await sources.heritage.lookup(result.building.native_geometry)
                heritage = {
                    "status": "SUCCESS",
                    "matches": [m.model_dump(mode="json") for m in matches],
                }
            except (SourceError, TimeoutError):
                heritage = {"status": "SOURCE_UNAVAILABLE"}
        return {
            "example_query": EXAMPLE_QUERY,
            "grar": result.model_dump(mode="json"),
            "heritage": heritage,
            "flood": flood_lookup(result.parcels).model_dump(mode="json"),
        }
    finally:
        await sources.aclose()
