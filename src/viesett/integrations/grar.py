import re
from urllib.parse import parse_qs, urlencode, urlsplit

from pydantic import JsonValue, ValidationError

from viesett.db.models import utcnow
from viesett.domain.property import (
    OfficialAddress,
    OfficialBuilding,
    OfficialBuildingUnit,
    OfficialParcel,
    ResolutionRequest,
    ResolutionResult,
    ResolutionStatus,
)
from viesett.integrations.geometry import parse_gml
from viesett.integrations.http import (
    OfficialHttpClient,
    SourceError,
    array_value,
    object_value,
    string_value,
)

ADDRESS_STATUSES = {"inGebruik", "voorgesteld", "gehistoreerd", "afgekeurd"}
BUILDING_STATUSES = {"gepland", "inAanbouw", "gerealiseerd", "gehistoreerd", "nietGerealiseerd"}
UNIT_STATUSES = {"gepland", "gerealiseerd", "gehistoreerd", "nietGerealiseerd"}
UNIT_FUNCTIONS = {"nietGekend", "gemeenschappelijkDeel"}
PARCEL_STATUSES = {"gerealiseerd", "gehistoreerd"}


def identifier(data: dict[str, JsonValue], entity: str, expected_id: str) -> dict[str, JsonValue]:
    identity = object_value(data.get("identificator"))
    object_id = string_value(identity.get("objectId"), maximum=100)
    uri = string_value(identity.get("id"))
    if object_id != expected_id or uri != f"https://data.vlaanderen.be/id/{entity}/{object_id}":
        raise SourceError("invalid_official_identifier", invalid=True)
    version = identity.get("versieId")
    if version is not None:
        version = string_value(version, maximum=100)
    return {"official_id": object_id, "source_uri": uri, "source_version": version}


def object_id(value: JsonValue, *, parcel: bool = False) -> str:
    result = string_value(value, maximum=100)
    pattern = r"[0-9]{5}[A-Z][0-9]{4}-[0-9]{2}[A-Z_0][0-9]{3}" if parcel else r"[1-9][0-9]{0,15}"
    if not re.fullmatch(pattern, result):
        raise SourceError("invalid_official_identifier", invalid=True)
    return result


def status_value(value: JsonValue, allowed: set[str]) -> str:
    status = string_value(value, maximum=80)
    if status not in allowed:
        raise SourceError("unknown_official_status", invalid=True)
    return status


def spelling(value: JsonValue) -> str:
    return string_value(object_value(object_value(value).get("geografischeNaam")).get("spelling"))


def linked_ids(value: JsonValue) -> list[str]:
    values = array_value(value)
    if len(values) > 500:
        raise SourceError("relationship_limit_exceeded", invalid=True)
    return sorted({object_id(object_value(row).get("objectId")) for row in values})


class GrarClient:
    def __init__(self, http: OfficialHttpClient) -> None:
        self.http = http

    async def address(self, official_id: str) -> tuple[OfficialAddress, dict[str, JsonValue]]:
        data = object_value(await self.http.get_json(f"/v2/adressen/{official_id}"))
        municipality = object_value(data.get("gemeente"))
        street = object_value(data.get("straatnaam"))
        post = data.get("postinfo")
        position = data.get("adresPositie")
        address = OfficialAddress.model_validate(
            {
                **identifier(data, "adres", official_id),
                "retrieved_at": utcnow(),
                "status": status_value(data.get("adresStatus"), ADDRESS_STATUSES),
                "canonical_address": spelling(data.get("volledigAdres")),
                "street_name": spelling(street.get("straatnaam")),
                "house_number": string_value(data.get("huisnummer"), maximum=30),
                "box_number": data.get("busnummer"),
                "postal_code": object_value(post).get("objectId") if post is not None else None,
                "municipality": spelling(municipality.get("gemeentenaam")),
                "municipality_code": municipality.get("objectId"),
                "native_geometry": parse_gml(object_value(position).get("geometrie"))
                if position is not None
                else None,
            }
        )
        return address, data

    async def search(
        self, query: str
    ) -> tuple[list[tuple[OfficialAddress, dict[str, JsonValue]]], bool]:
        data = object_value(
            await self.http.get_json(
                "/v2/adressen/zoeken",
                {
                    "q": query,
                    "resultaatType": "adressen",
                    "status": "inGebruik",
                    "limit": "6",
                },
            )
        )
        results = array_value(data.get("resultaten", data.get("Resultaten")))
        if len(results) > 6:
            raise SourceError("search_limit_exceeded", invalid=True)
        addresses = []
        seen = set()
        for item in results:
            row = object_value(item)
            source_id = object_id(row.get("objectId", row.get("ObjectId")))
            source_uri = string_value(row.get("id", row.get("Id")))
            detail = string_value(row.get("detail", row.get("Detail")))
            if source_uri != f"https://data.vlaanderen.be/id/adres/{source_id}":
                raise SourceError("invalid_official_identifier", invalid=True)
            if self.http.safe_path(detail) != f"/v2/adressen/{source_id}":
                raise SourceError("invalid_detail_navigation", invalid=True)
            if source_id in seen:
                continue
            seen.add(source_id)
            try:
                address, raw = await self.address(source_id)
            except SourceError as error:
                if error.not_found:
                    continue  # An address can be withdrawn between search and detail.
                raise
            if address.status == "inGebruik":
                addresses.append((address, raw))
        return addresses, len(results) == 6

    def relation_link(self, raw: dict[str, JsonValue], family: str, address_id: str) -> str:
        links = object_value(raw["_links"]) if raw.get("_links") is not None else {}
        link = (
            string_value(object_value(links[family]).get("href"))
            if family in links
            else f"/v2/{family}?adresobjectid={address_id}"
        )
        return self.validate_relation(link, family, address_id)

    def validate_relation(self, link: str, family: str, address_id: str) -> str:
        path = self.http.safe_path(link)
        parts = urlsplit(path)
        query = parse_qs(parts.query, keep_blank_values=True)
        if (
            parts.path != f"/v2/{family}"
            or set(query) - {"adresobjectid", "offset", "limit", "sorteer"}
            or ("adresobjectid" in query and query["adresobjectid"] != [address_id])
        ):
            raise SourceError("invalid_relationship_navigation", invalid=True)
        # Some pagination builders only carry offset/limit. Reapply the documented
        # address filter rather than ever making an unscoped relationship query.
        query["adresobjectid"] = [address_id]
        for name, maximum in [("offset", 1000000), ("limit", 100)]:
            if name in query and (
                len(query[name]) != 1
                or not query[name][0].isdigit()
                or int(query[name][0]) > maximum
                or (name == "limit" and int(query[name][0]) == 0)
            ):
                raise SourceError("invalid_relationship_pagination", invalid=True)
        return parts.path + "?" + urlencode(sorted(query.items()), doseq=True)

    async def related(self, raw: dict[str, JsonValue], family: str, address_id: str) -> list[str]:
        link = self.relation_link(raw, family, address_id)
        seen_links = set()
        ids: set[str] = set()
        for _ in range(3):
            if link in seen_links:
                raise SourceError("pagination_cycle", invalid=True)
            seen_links.add(link)
            page = object_value(await self.http.get_json(link))
            for value in array_value(page.get(family)):
                item = object_value(value)
                item_id = object_id(
                    object_value(item.get("identificator")).get("objectId"),
                    parcel=family == "percelen",
                )
                expected = f"/v2/{family}/{item_id}"
                if self.http.safe_path(string_value(item.get("detail"))) != expected:
                    raise SourceError("invalid_detail_navigation", invalid=True)
                ids.add(item_id)
                if len(ids) > 100:
                    raise SourceError("relationship_limit_exceeded", invalid=True)
            if not page.get("volgende"):
                return sorted(ids)
            link = self.validate_relation(string_value(page["volgende"]), family, address_id)
        raise SourceError("pagination_limit_exceeded", invalid=True)

    async def unit(self, official_id: str, address_id: str) -> OfficialBuildingUnit:
        data = object_value(await self.http.get_json(f"/v2/gebouweenheden/{official_id}"))
        addresses = linked_ids(data.get("adressen"))
        if address_id not in addresses:
            raise SourceError("unit_address_relationship_mismatch", invalid=True)
        function = data.get("functie")
        if function is not None:
            function = status_value(function, UNIT_FUNCTIONS)
        position = data.get("gebouweenheidPositie")
        return OfficialBuildingUnit.model_validate(
            {
                **identifier(data, "gebouweenheid", official_id),
                "retrieved_at": utcnow(),
                "status": status_value(data.get("gebouweenheidStatus"), UNIT_STATUSES),
                "function": function,
                "address_official_ids": addresses,
                "building_official_id": object_id(object_value(data.get("gebouw")).get("objectId")),
                "native_geometry": parse_gml(object_value(position).get("geometrie"))
                if position is not None
                else None,
            }
        )

    async def building(self, official_id: str, unit_id: str) -> OfficialBuilding:
        data = object_value(await self.http.get_json(f"/v2/gebouwen/{official_id}"))
        units = linked_ids(data.get("gebouweenheden"))
        if unit_id not in units:
            raise SourceError("building_unit_relationship_mismatch", invalid=True)
        polygon = data.get("gebouwPolygoon")
        return OfficialBuilding.model_validate(
            {
                **identifier(data, "gebouw", official_id),
                "retrieved_at": utcnow(),
                "status": status_value(data.get("gebouwStatus"), BUILDING_STATUSES),
                "unit_official_ids": units,
                "native_geometry": parse_gml(object_value(polygon).get("geometrie"))
                if polygon is not None
                else None,
            }
        )

    async def parcel(self, official_id: str, address_id: str) -> OfficialParcel:
        data = object_value(await self.http.get_json(f"/v2/percelen/{official_id}"))
        addresses = linked_ids(data.get("adressen"))
        if address_id not in addresses:
            raise SourceError("parcel_address_relationship_mismatch", invalid=True)
        capakey = string_value(
            data.get("caPaKey", data.get("capakey", data.get("CaPaKey"))), maximum=30
        )
        if not re.fullmatch(r"[0-9]{5}[A-Z][0-9]{4}/[0-9]{2}[A-Z_0][0-9]{3}", capakey):
            raise SourceError("invalid_capakey", invalid=True)
        return OfficialParcel.model_validate(
            {
                **identifier(data, "perceel", official_id),
                "retrieved_at": utcnow(),
                "status": status_value(data.get("perceelStatus"), PARCEL_STATUSES),
                "capakey": capakey,
                "address_official_ids": addresses,
            }
        )

    async def resolve(self, request: ResolutionRequest) -> ResolutionResult:
        try:
            addresses, truncated = await self.search(request.query)
            if not addresses:
                return ResolutionResult(status=ResolutionStatus.NOT_FOUND)
            exact = []
            if request.selected_address_object_id:
                chosen = [
                    a for a in addresses if a[0].official_id == request.selected_address_object_id
                ]
                if len(chosen) != 1:
                    raise SourceError("selection_not_in_official_candidates", invalid=True)
            else:
                exact = [
                    a
                    for a in addresses
                    if a[0].canonical_address.casefold() == request.query.casefold()
                ]
                chosen = exact if len(exact) == 1 else addresses
            if len(chosen) != 1 or (
                truncated and not request.selected_address_object_id and not exact
            ):
                return ResolutionResult(
                    status=ResolutionStatus.NEEDS_SELECTION,
                    address_candidates=[a for a, _ in addresses[:5]],
                    candidates_truncated=truncated,
                )
            address, raw = chosen[0]
            unit_ids = await self.related(raw, "gebouweenheden", address.official_id)
            if request.selected_building_unit_object_id:
                if request.selected_building_unit_object_id not in unit_ids:
                    raise SourceError("selection_not_related_to_address", invalid=True)
                inspect_ids = [request.selected_building_unit_object_id]
            else:
                inspect_ids = unit_ids[:20]
            units = []
            missing = []
            for unit_id in inspect_ids:
                try:
                    units.append(await self.unit(unit_id, address.official_id))
                except SourceError as error:
                    if not error.not_found:
                        raise
                    missing.append("building_unit_detail")
            usable = [
                u
                for u in units
                if u.status == "gerealiseerd" and u.function != "gemeenschappelijkDeel"
            ]
            if len(usable) > 1 or (
                len(unit_ids) > 20 and not request.selected_building_unit_object_id
            ):
                return ResolutionResult(
                    status=ResolutionStatus.NEEDS_SELECTION,
                    address=address,
                    building_unit_candidates=usable,
                    candidates_truncated=len(unit_ids) > 20,
                )
            if request.selected_building_unit_object_id and not usable:
                raise SourceError("selected_unit_not_usable", invalid=True)
            # A disappeared detail may hide another private unit. Never choose a
            # remaining unit merely because the other detail could not be read.
            unit = usable[0] if len(usable) == 1 and not missing else None
            building = None
            if unit:
                try:
                    building = await self.building(unit.building_official_id, unit.official_id)
                except SourceError as error:
                    if not error.not_found:
                        raise
                    missing.append("building")
            else:
                missing.append("building_unit")
            parcels = []
            for parcel_id in await self.related(raw, "percelen", address.official_id):
                try:
                    parcel = await self.parcel(parcel_id, address.official_id)
                except SourceError as error:
                    if not error.not_found:
                        raise
                    missing.append("parcel_detail")
                    continue
                if parcel.status == "gerealiseerd":
                    parcels.append(parcel)
            if not parcels:
                missing.append("parcels")
            if building is not None and building.status != "gerealiseerd":
                missing.append("current_building")
            return ResolutionResult(
                status=ResolutionStatus.PARTIALLY_RESOLVED
                if missing
                else ResolutionStatus.RESOLVED,
                address=address,
                selected_building_unit=unit,
                building=building,
                parcels=parcels,
                missing_relationships=sorted(set(missing)),
            )
        except SourceError as error:
            return ResolutionResult(
                status=ResolutionStatus.INVALID_SOURCE_RESPONSE
                if error.invalid
                else ResolutionStatus.UPSTREAM_UNAVAILABLE,
                error_code=error.code,
            )
        except (ValidationError, ValueError, KeyError, TypeError):
            return ResolutionResult(
                status=ResolutionStatus.INVALID_SOURCE_RESPONSE, error_code="invalid_grar_contract"
            )
