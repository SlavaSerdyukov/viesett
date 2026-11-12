from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from viesett.db.models import EvidenceItem
from viesett.domain.property import HeritageMatch, OfficialObject, ResolutionResult, SourceProvider
from viesett.domain.schemas import EvidenceCreate, SourceLocator, TypedValue
from viesett.domain.types import Authority, SourceType
from viesett.services.evidence import record_evidence


@dataclass(frozen=True)
class OfficialFact:
    key: str
    value: str
    official_id: str
    source_uri: str
    source_version: str | None
    retrieved_at: datetime


def grar_facts(result: ResolutionResult) -> list[OfficialFact]:
    facts = []

    def add(obj: OfficialObject, key: str, value: str | None) -> None:
        if value is not None:
            facts.append(
                OfficialFact(
                    key,
                    value,
                    obj.official_id,
                    obj.source_uri,
                    obj.source_version,
                    obj.retrieved_at,
                )
            )

    if result.address:
        address = result.address
        for field, value in {
            "canonical": address.canonical_address,
            "object_id": address.official_id,
            "status": address.status,
            "street_name": address.street_name,
            "house_number": address.house_number,
            "box_number": address.box_number,
            "postal_code": address.postal_code,
            "municipality": address.municipality,
            "municipality_code": address.municipality_code,
        }.items():
            add(address, "property.address." + field, value)
    for entity, obj in [
        ("building_unit", result.selected_building_unit),
        ("building", result.building),
    ]:
        if obj:
            add(obj, f"property.{entity}.object_id", obj.official_id)
            add(obj, f"property.{entity}.status", obj.status)
    if result.selected_building_unit:
        add(
            result.selected_building_unit,
            "property.building_unit.function",
            result.selected_building_unit.function,
        )
    for parcel in result.parcels:
        add(parcel, "property.parcel.object_id", parcel.official_id)
        add(parcel, "property.parcel.capakey", parcel.capakey)
        add(parcel, "property.parcel.status", parcel.status)
    return facts


def heritage_facts(matches: list[HeritageMatch]) -> list[OfficialFact]:
    return [
        OfficialFact(
            "property.heritage." + field,
            value,
            match.official_id,
            match.source_uri,
            None,
            match.retrieved_at,
        )
        for match in matches
        for field, value in {
            "object_id": match.official_id,
            "title": match.title,
            "category": match.category,
            "type_uri": match.type_uri,
            "type_label": match.type_label,
            "classification": match.classification,
            "match_basis": match.match_basis,
        }.items()
    ]


async def synchronize_official_evidence(
    db: AsyncSession,
    user_id: UUID,
    workspace_id: UUID,
    provider: SourceProvider,
    facts: list[OfficialFact],
    retrieved_at: datetime,
) -> None:
    if provider not in {SourceProvider.GRAR, SourceProvider.HERITAGE}:
        raise ValueError("No approved automatic fact contract for this source")
    current = {
        row.fact_identifier: row
        for row in (
            await db.scalars(
                select(EvidenceItem).where(
                    EvidenceItem.workspace_id == workspace_id,
                    EvidenceItem.provider == provider.value,
                    EvidenceItem.superseded_at.is_(None),
                )
            )
        ).all()
    }
    incoming = {fact.source_uri + "#" + fact.key: fact for fact in facts}
    for identity, row in current.items():
        fact = incoming.get(identity or "")
        if (
            fact is None
            or row.typed_value != {"kind": "text", "value": fact.value}
            or row.source_version != fact.source_version
        ):
            row.superseded_at = retrieved_at
        else:
            row.last_seen_at = fact.retrieved_at
    await db.flush()
    for identity, fact in incoming.items():
        previous = current.get(identity)
        if previous is not None and previous.superseded_at is None:
            continue
        row = await record_evidence(
            db,
            user_id,
            workspace_id,
            EvidenceCreate(
                key=fact.key,
                typed_value=TypedValue(kind="text", value=fact.value),
                authority=Authority.OFFICIAL,
                source_type=SourceType.PUBLIC_REGISTRY,
                source_locator=SourceLocator(
                    registry=provider.value, source_identifier=fact.official_id, uri=fact.source_uri
                ),
                observed_at=fact.retrieved_at,
            ),
        )
        row.provider = provider.value
        row.fact_identifier = identity
        row.source_uri = fact.source_uri
        row.source_version = fact.source_version
        row.source_retrieved_at = fact.retrieved_at
        row.last_seen_at = fact.retrieved_at
        row.supersedes_evidence_id = previous.id if previous else None
    await db.flush()
