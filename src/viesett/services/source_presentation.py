"""Product-only source destinations. Never fetch or change evidence authority."""

from viesett.coownership.catalog import LEGAL_SOURCE
from viesett.domain.product import CitationResponse
from viesett.rules.catalog import (
    ASBESTOS_SOURCE,
    COMMON_SOURCE,
    ELECTRICAL_SOURCE,
    EPC_SOURCE,
    RENOVATION_SOURCE,
    SOIL_SOURCE,
    VALIDITY_SOURCE,
)

# A reviewed, exact destination catalog, also generated into the web contract.
# Register destinations describe the source; they are not object-level deep links.
SOURCE_CATALOG = {
    "GRAR": {
        "label": "Official Flemish Address Register",
        "kind": "OFFICIAL_REGISTER",
        "provider": "GRAR",
        "human_url": "https://www.vlaanderen.be/datavindplaats/catalogus/gebouwen-en-adressenregister",
    },
    "HERITAGE": {
        "label": "Heritage inventory — Onroerend Erfgoed",
        "kind": "OFFICIAL_REGISTER",
        "provider": "HERITAGE",
        "human_url": "https://inventaris.onroerenderfgoed.be/",
    },
    "FLOOD": {
        "label": "Waterinfo — Flood information",
        "kind": "PUBLIC_INFORMATION",
        "provider": "FLOOD",
        "human_url": "https://waterinfo.vlaanderen.be/informatieplicht",
    },
    "EPC": {
        "label": "Vlaanderen / VEKA — EPC",
        "kind": "RULE_AUTHORITY",
        "provider": "VEKA",
        "human_url": EPC_SOURCE,
    },
    "RENOVATION": {
        "label": "Vlaanderen / VEKA — Renovation obligation",
        "kind": "RULE_AUTHORITY",
        "provider": "VEKA",
        "human_url": RENOVATION_SOURCE,
    },
    "ASBESTOS": {
        "label": "OVAM — Asbestos certificate",
        "kind": "RULE_AUTHORITY",
        "provider": "OVAM",
        "human_url": ASBESTOS_SOURCE,
    },
    "COMMON_ASBESTOS": {
        "label": "OVAM — Common-parts certificate",
        "kind": "RULE_AUTHORITY",
        "provider": "OVAM",
        "human_url": COMMON_SOURCE,
    },
    "ASBESTOS_VALIDITY": {
        "label": "OVAM — Certificate validity",
        "kind": "RULE_AUTHORITY",
        "provider": "OVAM",
        "human_url": VALIDITY_SOURCE,
    },
    "SOIL": {
        "label": "OVAM — Soil certificate",
        "kind": "RULE_AUTHORITY",
        "provider": "OVAM",
        "human_url": SOIL_SOURCE,
    },
    "ELECTRICAL": {
        "label": "FOD Economie / AREI — Electrical inspection",
        "kind": "RULE_AUTHORITY",
        "provider": "FOD_ECONOMIE",
        "human_url": ELECTRICAL_SOURCE,
    },
    "CIVIL_CODE": {
        "label": "Belgian Civil Code — Book 3",
        "kind": "RULE_AUTHORITY",
        "provider": "JUSTEL",
        "human_url": LEGAL_SOURCE,
    },
    "HERITAGE_TERMS": {
        "label": "Heritage reuse conditions",
        "kind": "PUBLIC_INFORMATION",
        "provider": "HERITAGE",
        "human_url": "https://inventaris.onroerenderfgoed.be/hergebruik",
    },
}


def present_citation(source: CitationResponse) -> CitationResponse:
    """Add display metadata, retaining raw URI/locators on the same projection."""
    if source.document_id is not None:
        return source.model_copy(update={"kind": "DOCUMENT", "human_url": None})
    technical = source.technical_uri or source.uri
    destination = None
    if source.kind == "RULE_AUTHORITY":
        destination = next(
            (
                row
                for row in SOURCE_CATALOG.values()
                if row["kind"] == "RULE_AUTHORITY" and row["human_url"] == technical
            ),
            None,
        )
        if technical == "https://data.vlaanderen.be/ns/adres":
            destination = {
                **SOURCE_CATALOG["GRAR"],
                "kind": "RULE_AUTHORITY",
                "label": "Address comparison reference — official address data",
            }
    elif source.provider in {"GRAR", "HERITAGE", "FLOOD"}:
        destination = SOURCE_CATALOG[source.provider]
    return CitationResponse.model_validate(
        {
            **source.model_dump(),
            "technical_uri": technical,
            "human_url": None,
            **(destination or {}),
        }
    )
