"""Opt-in drift check against the schema linked by the official API reference."""

import argparse
import asyncio
import hashlib
import json
import logging
import os
from pathlib import Path

import httpx
from pydantic import JsonValue

from viesett.integrations.http import JsonDocument, SourceError, object_value

SCHEMA_URL = "https://docs.basisregisters.vlaanderen.be/docs/v2/docs.json?culture=en-GB"


def check_contract(schema: dict[str, JsonValue]) -> list[str]:
    failures: list[str] = []
    try:
        paths = object_value(schema.get("paths"))
        search = object_value(object_value(paths.get("/v2/adressen/zoeken")).get("get"))
        parameters = search.get("parameters")
        if not isinstance(parameters, list):
            return ["SEARCH_PARAMETERS_MISSING"]
        params = {str(p.get("name")): p for p in parameters if isinstance(p, dict)}
        for name in ["q", "gemeenteNaam", "niscode", "limit", "status", "resultaatType"]:
            if name not in params or params[name].get("in") != "query":
                failures.append("SEARCH_PARAMETER_" + name + "_MISSING")
        for name, choices in [
            ("status", ["inGebruik"]),
            ("resultaatType", ["adressen", "straatnamen"]),
        ]:
            p = params.get(name, {})
            metadata = object_value(p.get("schema", {}))
            # This provider publishes these vocabularies in descriptions rather
            # than schema enums. Accept either documented representation.
            published = metadata.get("enum")
            description = str(p.get("description", ""))
            if any(
                c not in published
                if isinstance(published, list)
                else '"' + c + '"' not in description
                for c in choices
            ):
                failures.append("SEARCH_VOCABULARY_" + name + "_CHANGED")
        if params.get("x-api-key", {}).get("required", False):
            failures.append("ANONYMOUS_SEARCH_CHANGED")
        if params.get("x-api-key", {}).get("in") != "header":
            failures.append("API_KEY_HEADER_CHANGED")
        for path in ["/v2/adressen/{objectId}", "/v2/gebouweenheden", "/v2/percelen"]:
            if "get" not in object_value(paths.get(path)):
                failures.append("DETAIL_OR_RELATION_MISSING")
        components = object_value(object_value(schema.get("components")).get("schemas"))
        response = object_value(components.get("AddressSearchResponse"))
        item = object_value(components.get("AddressSearchItem"))
        if "resultaten" not in object_value(response.get("properties")):
            failures.append("SEARCH_RESULTS_SHAPE_CHANGED")
        if not {"id", "objectId", "detail", "result"}.issubset(
            object_value(item.get("properties"))
        ):
            failures.append("SEARCH_ITEM_SHAPE_CHANGED")
    except (SourceError, ValueError, TypeError, KeyError):
        failures.append("INVALID_SCHEMA")
    return failures


async def fetch_schema(transport: httpx.AsyncBaseTransport | None = None) -> dict[str, JsonValue]:
    logging.getLogger("httpx").setLevel(logging.WARNING)
    async with httpx.AsyncClient(
        timeout=15, follow_redirects=False, trust_env=False, transport=transport
    ) as client:
        async with client.stream(
            "GET", SCHEMA_URL, headers={"Accept": "application/json"}
        ) as response:
            response.raise_for_status()
            content = bytearray()
            async for chunk in response.aiter_bytes():
                content.extend(chunk)
                if len(content) > 8 * 1024 * 1024:
                    raise ValueError("Schema exceeds tooling limit")
    return object_value(JsonDocument.model_validate_json(bytes(content)).root)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--schema", type=Path)
    args = parser.parse_args()
    if not args.schema and (not args.live or os.environ.get("CI")):
        parser.error("Use --schema for offline input, or explicit --live outside CI")
    try:
        schema = (
            object_value(JsonDocument.model_validate_json(args.schema.read_bytes()).root)
            if args.schema
            else asyncio.run(fetch_schema())
        )
        failures = check_contract(schema)
        digest = hashlib.sha256(json.dumps(schema, sort_keys=True).encode()).hexdigest()
        print(
            json.dumps(
                {
                    "result": "CONTRACT_FAILURE" if failures else "SUCCESS",
                    "checks": failures,
                    "schema_sha256": digest,
                }
            )
        )
    except Exception:
        print(json.dumps({"result": "SCHEMA_UNAVAILABLE"}))
        raise SystemExit(1) from None
    raise SystemExit(1 if failures else 0)


if __name__ == "__main__":
    main()
