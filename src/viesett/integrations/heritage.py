import json
import re

from viesett.db.models import utcnow
from viesett.domain.property import Geometry, HeritageMatch
from viesett.integrations.geometry import to_wgs84
from viesett.integrations.http import (
    OfficialHttpClient,
    SourceError,
    array_value,
    object_value,
    string_value,
)


class HeritageClient:
    def __init__(self, http: OfficialHttpClient) -> None:
        self.http = http

    async def lookup(self, native_area: Geometry) -> list[HeritageMatch]:
        if native_area.type not in {"Polygon", "MultiPolygon"}:
            raise SourceError("property_area_required", invalid=True)
        geometry = to_wgs84(native_area)
        query = json.dumps(geometry.model_dump(mode="json", exclude={"crs"}), separators=(",", ":"))
        if len(query) > 6000:
            raise SourceError("geometry_query_too_large")
        payload = array_value(
            await self.http.get_json(
                "/zoekdiensten/afbakeningen",
                {
                    "geometrie": query,
                    "buffer": "0",
                    "geef_geometrie": "0",
                },
            )
        )
        if len(payload) > 1000:
            raise SourceError("heritage_match_limit_exceeded", invalid=True)
        matches: dict[str, HeritageMatch] = {}
        for value in payload:
            row = object_value(value)
            identifier = row.get("id")
            if isinstance(identifier, bool) or not isinstance(identifier, (str, int)):
                raise SourceError("invalid_heritage_identifier", invalid=True)
            official_id = str(identifier)
            if not re.fullmatch(r"[0-9]{1,15}", official_id):
                raise SourceError("invalid_heritage_identifier", invalid=True)
            category = string_value(row.get("categorie"), maximum=80)
            uri = string_value(row.get("uri"))
            if category not in {"erfgoedobjecten", "aanduidingsobjecten", "plannen"} or (
                uri != f"https://id.erfgoed.net/{category}/{official_id}"
            ):
                raise SourceError("invalid_heritage_identifier", invalid=True)
            kind = object_value(row.get("type"))
            kind_uri = string_value(kind.get("uri"))
            if not re.fullmatch(r"https://id\.erfgoed\.net/thesauri/[a-z]+/[0-9]+", kind_uri):
                raise SourceError("invalid_heritage_type", invalid=True)
            match = HeritageMatch(
                official_id=official_id,
                source_uri=uri,
                title=string_value(row.get("naam"), maximum=500),
                category=category,
                type_uri=kind_uri,
                type_label=string_value(kind.get("label"), maximum=200),
                classification=(
                    "DESIGNATION"
                    if category == "aanduidingsobjecten"
                    else "INVENTORY_ONLY"
                    if category == "erfgoedobjecten"
                    else "OTHER"
                ),
                match_basis=(
                    f"official building polygon intersection; "
                    f"{native_area.crs} to EPSG:4326; buffer=0"
                ),
                retrieved_at=utcnow(),
            )
            previous = matches.get(uri)
            if previous and previous.model_dump(exclude={"retrieved_at"}) != match.model_dump(
                exclude={"retrieved_at"}
            ):
                raise SourceError("conflicting_heritage_matches", invalid=True)
            matches[uri] = match
        return sorted(matches.values(), key=lambda match: match.source_uri)
