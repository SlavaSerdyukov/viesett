import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.document_fixtures import EPC, text_pdf
from tests.helpers import attest
from viesett.db.models import EvidenceItem
from viesett.domain.product import CitationResponse
from viesett.rules.catalog import SOIL_SOURCE
from viesett.services.source_presentation import SOURCE_CATALOG, present_citation


@pytest.mark.parametrize(
    "uri",
    [
        "https://api.basisregisters.vlaanderen.be/v2/adressen/1",
        "https://data.vlaanderen.be/id/adres/1",
    ],
)
def test_grar_human_destination_preserves_exact_technical_provenance(uri: str) -> None:
    source = present_citation(
        CitationResponse(
            label="Official Flemish register",
            kind="OFFICIAL_REGISTER",
            provider="GRAR",
            uri=uri,
            source_identifier="address:1",
        )
    )
    assert source.human_url == SOURCE_CATALOG["GRAR"]["human_url"]
    assert source.human_url != uri
    assert source.technical_uri == source.uri == uri
    assert source.source_identifier == "address:1"
    assert source.kind == "OFFICIAL_REGISTER"


@pytest.mark.parametrize(
    "uri",
    [
        "https://unapproved.example/source",
        "javascript:alert(1)",
        "https://www.vlaanderen.be@unapproved.example/source",
    ],
)
def test_unknown_rule_uri_stays_non_clickable_provenance(uri: str) -> None:
    source = present_citation(
        CitationResponse(label="Unreviewed source", uri=uri, kind="RULE_AUTHORITY", human_url=uri)
    )
    assert source.human_url is None
    assert source.technical_uri == source.uri == uri


@pytest.mark.parametrize("provider", ["GRAR", "HERITAGE", "FLOOD"])
def test_known_provider_uses_only_its_reviewed_human_destination(provider: str) -> None:
    source = present_citation(
        CitationResponse(label="Source", provider=provider, uri="https://unapproved.example/raw")
    )
    assert source.human_url == SOURCE_CATALOG[provider]["human_url"]
    assert source.technical_uri == "https://unapproved.example/raw"


def test_rule_guidance_is_separate_from_registry_evidence() -> None:
    source = present_citation(
        CitationResponse(label="OVAM", uri=SOIL_SOURCE, kind="RULE_AUTHORITY")
    )
    assert source.kind == "RULE_AUTHORITY" and source.provider == "OVAM"
    assert source.human_url == SOIL_SOURCE


async def test_dossier_projects_sources_without_modifying_official_evidence(
    analysis_client: AsyncClient, db: AsyncSession
) -> None:
    await attest(analysis_client)
    created = await analysis_client.post("/api/v1/dossiers", json={"query": "Teststraat 42 Gent"})
    assert created.status_code == 201
    wid = created.json()["workspace"]["id"]
    response = await analysis_client.post(
        f"/api/v1/workspaces/{wid}/document-intake",
        content=text_pdf(EPC),
        headers={"Content-Type": "application/pdf"},
    )
    assert response.status_code == 200, response.text
    before = {
        e.id: (
            e.provider,
            e.fact_identifier,
            e.source_uri,
            e.source_retrieved_at,
            e.source_version,
            e.authority,
            e.source_locator,
        )
        for e in (
            await db.scalars(select(EvidenceItem).where(EvidenceItem.provider == "GRAR"))
        ).all()
    }
    assert before
    data = (await analysis_client.get(f"/api/v1/workspaces/{wid}/dossier")).json()
    sources = [s for e in data["evidence"] for s in e["sources"]]
    official = [s for s in sources if s["provider"] == "GRAR"]
    assert all(e["key"] for e in data["evidence"])
    assert any(e["key"] == "property.address.object_id" for e in data["evidence"])
    assert official and all(s["kind"] == "OFFICIAL_REGISTER" for s in official)
    assert all(s["human_url"] == SOURCE_CATALOG["GRAR"]["human_url"] for s in official)
    assert all(s["technical_uri"] == s["uri"] for s in official)
    assert any(s["kind"] == "DOCUMENT" and s["document_id"] and s["page"] == 1 for s in sources)
    assert any(s["kind"] == "RULE_AUTHORITY" for f in data["findings"] for s in f["sources"])
    after = {
        e.id: (
            e.provider,
            e.fact_identifier,
            e.source_uri,
            e.source_retrieved_at,
            e.source_version,
            e.authority,
            e.source_locator,
        )
        for e in (
            await db.scalars(select(EvidenceItem).where(EvidenceItem.provider == "GRAR"))
        ).all()
    }
    assert before == after
