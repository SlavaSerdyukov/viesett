"""Read-only official example verification. No customer input or credential output."""

import asyncio
import errno
import json
import os
import socket
import ssl
from collections.abc import Awaitable, Callable
from typing import cast

import httpx
from pydantic import JsonValue

from viesett.core.config import Settings
from viesett.domain.property import ResolutionRequest
from viesett.integrations.grar import GrarClient
from viesett.integrations.http import GRAR_HOST, OfficialHttpClient
from viesett.integrations.smoke import EXAMPLE_QUERY


async def network_probe() -> list[dict[str, str]]:
    stages: list[dict[str, str]] = []
    try:
        await asyncio.wait_for(asyncio.to_thread(socket.getaddrinfo, GRAR_HOST, 443), 3)
        stages.append({"stage": "DNS", "status": "SUCCESS"})
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(
                GRAR_HOST, 443, ssl=ssl.create_default_context(), server_hostname=GRAR_HOST
            ),
            4,
        )
        writer.close()
        await writer.wait_closed()
        stages.append({"stage": "TLS", "status": "SUCCESS"})
    except Exception as error:
        category = (
            "NETWORK_BLOCKED"
            if isinstance(error, OSError)
            and error.errno in {errno.EPERM, errno.EACCES, errno.ENETUNREACH}
            else "DNS_FAILURE"
            if isinstance(error, socket.gaierror)
            else "TLS_FAILURE"
            if isinstance(error, ssl.SSLError)
            else "CONNECT_TIMEOUT"
            if isinstance(error, TimeoutError)
            else "NETWORK_FAILURE"
        )
        stages.append({"stage": "CONNECT", "status": category})
    return stages


async def verify(
    settings: Settings,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
    probe: Callable[[], Awaitable[list[dict[str, str]]]] = network_probe,
) -> dict[str, JsonValue]:
    if not settings.run_live_source_tests or (
        os.environ.get("CI") and not isinstance(transport, httpx.MockTransport)
    ):
        raise RuntimeError("Live verification requires explicit opt-in outside CI")
    stages = await probe()
    if stages and stages[-1]["status"] != "SUCCESS":
        category = stages[-1]["status"]
        return {
            "result": "NETWORK_BLOCKED" if category == "NETWORK_BLOCKED" else "OTHER_SAFE_CATEGORY",
            "stages": cast(JsonValue, stages),
        }

    def diagnostic(stage: str, category: str) -> None:
        stages.append({"stage": stage, "status": category})

    async with OfficialHttpClient.grar(
        settings, transport=transport, diagnostic=diagnostic
    ) as http:
        try:
            async with asyncio.timeout(settings.source_operation_timeout):
                result = await GrarClient(http).resolve(ResolutionRequest(query=EXAMPLE_QUERY))
        except TimeoutError:
            stages.append({"stage": "OPERATION", "status": "READ_TIMEOUT"})
            return {"result": "PROVIDER_UNAVAILABLE", "stages": cast(JsonValue, stages)}
    if result.address and result.status in {"RESOLVED", "PARTIALLY_RESOLVED", "NEEDS_SELECTION"}:
        stages.append({"stage": "NORMALIZATION", "status": "SUCCESS"})
        return {
            "result": "LIVE_SUCCESS" if transport is None else "SYNTHETIC_SUCCESS",
            "stages": cast(JsonValue, stages),
            "resolution_status": result.status,
            "address_normalized": True,
            "building_unit_normalized": result.selected_building_unit is not None,
            "parcel_count": len(result.parcels),
            "missing_relationships": [value for value in result.missing_relationships],
        }
    invalid = result.status == "INVALID_SOURCE_RESPONSE"
    stages.append(
        {"stage": "NORMALIZATION", "status": "INVALID_CONTRACT" if invalid else "NOT_COMPLETED"}
    )
    return {
        "result": "CONTRACT_FAILURE"
        if invalid
        else "PROVIDER_UNAVAILABLE"
        if result.status == "UPSTREAM_UNAVAILABLE"
        else "OTHER_SAFE_CATEGORY",
        "stages": cast(JsonValue, stages),
        "resolution_status": result.status,
    }


def main() -> None:
    try:
        settings = Settings()
        if not settings.run_live_source_tests or os.environ.get("CI"):
            print(
                json.dumps(
                    {
                        "result": "OPT_IN_REQUIRED",
                        "command": "Set VIESETT_RUN_LIVE_SOURCE_TESTS=1 outside CI",
                    }
                )
            )
            raise SystemExit(2)
        output = asyncio.run(verify(settings))
    except (ValueError, RuntimeError, httpx.RequestError):
        output = {"result": "OTHER_SAFE_CATEGORY"}
    print(json.dumps(output))
    raise SystemExit(0 if output.get("result") == "LIVE_SUCCESS" else 1)


if __name__ == "__main__":
    main()
