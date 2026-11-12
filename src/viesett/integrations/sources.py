from datetime import datetime
from urllib.parse import urlencode

import httpx

from viesett.core.config import Settings
from viesett.domain.property import FloodResult, OfficialParcel, SourceAttribution, SourceProvider
from viesett.integrations.grar import GrarClient
from viesett.integrations.heritage import HeritageClient
from viesett.integrations.http import GRAR_HOST, HERITAGE_HOST, OfficialHttpClient

ATTRIBUTIONS = {
    SourceProvider.GRAR: (
        "Digitaal Vlaanderen",
        "Bron: Digitaal Vlaanderen",
        "https://docs.basisregisters.vlaanderen.be/docs/api-documentation.html",
        "https://www.vlaanderen.be/datavindplaats/catalogus/gebouwen-en-adressenregister",
    ),
    SourceProvider.HERITAGE: (
        "Agentschap Onroerend Erfgoed",
        "Onroerend Erfgoed",
        "https://geo.onroerenderfgoed.be/zoekdiensten/api_doc",
        "https://inventaris.onroerenderfgoed.be/hergebruik",
    ),
    SourceProvider.FLOOD: (
        "Vlaamse Milieumaatschappij / Waterinfo",
        "Waterinfo",
        "https://waterinfo.vlaanderen.be/informatieplicht",
        "https://waterinfo.vlaanderen.be/informatieplicht",
    ),
}


def attribution(provider: SourceProvider, when: datetime) -> SourceAttribution:
    name, credit, reference, terms = ATTRIBUTIONS[provider]
    return SourceAttribution(
        provider=provider,
        provider_name=name,
        attribution_text=credit,
        source_reference=reference,
        terms_reference=terms,
        retrieved_at=when,
    )


def flood_lookup(parcels: list[OfficialParcel]) -> FloodResult:
    reference = "https://waterinfo.vlaanderen.be/informatieplicht"
    return FloodResult(
        status="MANUAL_OFFICIAL_LOOKUP_REQUIRED" if parcels else "NOT_APPLICABLE",
        parcel_references={
            p.capakey: reference + "?" + urlencode({"capakey": p.capakey}) for p in parcels
        },
    )


class PublicSources:
    def __init__(
        self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None
    ) -> None:
        self.enabled = settings.official_sources_enabled and (
            settings.environment != "production" or settings.official_sources_reviewed
        )
        self.grar = GrarClient(OfficialHttpClient(GRAR_HOST, settings, transport=transport))
        self.heritage = HeritageClient(
            OfficialHttpClient(HERITAGE_HOST, settings, transport=transport)
        )

    async def aclose(self) -> None:
        await self.grar.http.aclose()
        await self.heritage.http.aclose()
