"""Synthetic contract examples; no customer data and no live service dependency."""

from collections import Counter
from copy import deepcopy
from dataclasses import dataclass, field

import httpx
from pydantic import JsonValue

HOST = "https://api.basisregisters.vlaanderen.be"
VERSION = "2026-11-01T12:00:00+01:00"
PARCEL_IDS = ["11001B0001-00S000", "11001B0009-00G004"]
POINT = (
    '<gml:Point srsName="https://www.opengis.net/def/crs/EPSG/0/31370" '
    'xmlns:gml="http://www.opengis.net/gml/3.2">'
    "<gml:pos>140252.76 198794.27</gml:pos></gml:Point>"
)
POLYGON = (
    '<gml:Polygon srsName="https://www.opengis.net/def/crs/EPSG/0/31370" '
    'xmlns:gml="http://www.opengis.net/gml/3.2"><gml:exterior><gml:LinearRing>'
    "<gml:posList>140250 198790 140260 198790 140260 198800 140250 198800 "
    "140250 198790</gml:posList></gml:LinearRing></gml:exterior></gml:Polygon>"
)


def identity(entity: str, official_id: str) -> dict[str, JsonValue]:
    return {
        "id": f"https://data.vlaanderen.be/id/{entity}/{official_id}",
        "objectId": official_id,
        "versieId": VERSION,
    }


def name(value: str) -> dict[str, JsonValue]:
    return {"geografischeNaam": {"spelling": value, "taal": "nl"}}


def address(official_id: str) -> dict[str, JsonValue]:
    box = "1" if official_id == "2" else None
    return {
        "@type": "Adres",
        "identificator": identity("adres", official_id),
        "gemeente": {"objectId": "44021", "gemeentenaam": name("Gent")},
        "postinfo": {"objectId": "9000"},
        "straatnaam": {"straatnaam": name("Teststraat")},
        "huisnummer": "42",
        "busnummer": box,
        "volledigAdres": name("Teststraat 42" + (" bus 1" if box else "") + ", 9000 Gent"),
        "adresPositie": {"geometrie": {"type": "Point", "gml": POINT}},
        "adresStatus": "inGebruik",
        "officieelToegekend": True,
        "_links": {
            "gebouweenheden": {"href": f"{HOST}/v2/gebouweenheden?adresobjectid={official_id}"},
            "percelen": {"href": f"/v2/percelen?adresobjectid={official_id}"},
        },
    }


def unit(official_id: str, address_id: str = "1") -> dict[str, JsonValue]:
    return {
        "identificator": identity("gebouweenheid", official_id),
        "gebouweenheidStatus": "gerealiseerd",
        "functie": "gemeenschappelijkDeel" if official_id == "12" else "nietGekend",
        "gebouw": {"objectId": "100", "detail": HOST + "/v2/gebouwen/100"},
        "adressen": [{"objectId": address_id}],
        "gebouweenheidPositie": {"geometrie": {"type": "Point", "gml": POINT}},
    }


def heritage(official_id: int, category: str, label: str) -> dict[str, JsonValue]:
    family = "aanduidingstypes" if category == "aanduidingsobjecten" else "inventaristypes"
    return {
        "id": official_id,
        "uri": f"https://id.erfgoed.net/{category}/{official_id}",
        "categorie": category,
        "naam": f"Synthetic heritage {official_id}",
        "type": {"uri": f"https://id.erfgoed.net/thesauri/{family}/1", "label": label},
    }


@dataclass
class OfficialFixtureService:
    search_ids: list[str] = field(default_factory=lambda: ["1"])
    units_by_address: dict[str, list[str]] = field(
        default_factory=lambda: {"1": ["10"], "2": ["20"]}
    )
    parcels_by_address: dict[str, list[str]] = field(
        default_factory=lambda: {"1": PARCEL_IDS.copy(), "2": PARCEL_IDS[:1]}
    )
    addresses: dict[str, dict[str, JsonValue]] = field(
        default_factory=lambda: {"1": address("1"), "2": address("2")}
    )
    units: dict[str, dict[str, JsonValue]] = field(
        default_factory=lambda: {
            "10": unit("10"),
            "11": unit("11"),
            "12": unit("12"),
            "20": unit("20", "2"),
        }
    )
    building: dict[str, JsonValue] = field(
        default_factory=lambda: {
            "identificator": identity("gebouw", "100"),
            "gebouwStatus": "gerealiseerd",
            "gebouwPolygoon": {"geometrie": {"type": "Polygon", "gml": POLYGON}},
            "gebouweenheden": [{"objectId": i} for i in ["10", "11", "12", "20"]],
        }
    )
    heritage_matches: list[dict[str, JsonValue]] = field(
        default_factory=lambda: [
            heritage(1, "aanduidingsobjecten", "beschermd monument"),
            heritage(2, "aanduidingsobjecten", "vastgesteld bouwkundig erfgoed"),
            heritage(3, "erfgoedobjecten", "bouwkundig erfgoed"),
        ]
    )
    status_by_path: dict[str, int] = field(default_factory=dict)
    payload_by_path: dict[str, JsonValue] = field(default_factory=dict)
    requests: list[httpx.Request] = field(default_factory=list)
    counts: Counter[str] = field(default_factory=Counter)

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.path
        self.counts[path] += 1
        status = self.status_by_path.get(path, 200)
        if status != 200:
            return httpx.Response(status, json={"detail": "UPSTREAM_PRIVATE_ERROR_BODY"})
        if path in self.payload_by_path:
            return httpx.Response(200, json=self.payload_by_path[path])
        if request.url.host == "geo.onroerenderfgoed.be":
            assert path == "/zoekdiensten/afbakeningen"
            return httpx.Response(200, json=self.heritage_matches)
        assert request.url.host == "api.basisregisters.vlaanderen.be"
        if path == "/v2/adressen/zoeken":
            assert request.url.params["resultaatType"] == "adressen"
            assert request.url.params["status"] == "inGebruik"
            return httpx.Response(
                200,
                json={
                    "resultaten": [
                        {
                            "objectId": i,
                            "id": f"https://data.vlaanderen.be/id/adres/{i}",
                            "detail": HOST + f"/v2/adressen/{i}",
                            "result": f"Synthetic address {i}",
                        }
                        for i in self.search_ids
                    ]
                },
            )
        if path.startswith("/v2/adressen/"):
            return httpx.Response(200, json=deepcopy(self.addresses[path.split("/")[-1]]))
        if path in {"/v2/gebouweenheden", "/v2/percelen"}:
            address_id = request.url.params["adresobjectid"]
            family = path.split("/")[-1]
            ids = (
                self.units_by_address.get(address_id, [])
                if family == "gebouweenheden"
                else self.parcels_by_address.get(address_id, [])
            )
            return httpx.Response(
                200,
                json={
                    family: [
                        {"identificator": {"objectId": i}, "detail": HOST + path + "/" + i}
                        for i in ids
                    ]
                },
            )
        if path.startswith("/v2/gebouweenheden/"):
            return httpx.Response(200, json=deepcopy(self.units[path.split("/")[-1]]))
        if path.startswith("/v2/gebouwen/"):
            return httpx.Response(200, json=deepcopy(self.building))
        if path.startswith("/v2/percelen/"):
            official_id = path.split("/")[-1]
            return httpx.Response(
                200,
                json={
                    "identificator": identity("perceel", official_id),
                    "caPaKey": official_id.replace("-", "/"),
                    "perceelStatus": "gerealiseerd",
                    "adressen": [{"objectId": "1"}, {"objectId": "2"}],
                },
            )
        raise AssertionError("Unexpected official contract request")
