from dataclasses import dataclass
from datetime import date
from uuid import UUID

from viesett.domain.coownership import Money
from viesett.domain.intelligence import AnalysisKind, AssociationStatus, ExtractedField
from viesett.domain.property import PropertySnapshot


@dataclass(frozen=True)
class Fact:
    field: ExtractedField
    evidence_id: UUID

    @property
    def key(self) -> str:
        return self.field.key.removeprefix("document.co.")


@dataclass(frozen=True)
class Document:
    id: UUID
    kind: AnalysisKind
    fields: tuple[Fact, ...]
    parse_status: str
    source_sha256: str

    def all(self, key: str, group: str | None = None) -> list[Fact]:
        return [
            f for f in self.fields if f.key == key and (group is None or f.field.group == group)
        ]

    def one(self, key: str, group: str = "root") -> Fact | None:
        values = self.all(key, group)
        return values[0] if values and len({str(f.field.value) for f in values}) == 1 else None

    def value(self, key: str, group: str = "root") -> str | int | float | bool | None:
        fact = self.one(key, group)
        return fact.field.value if fact else None


@dataclass(frozen=True)
class CrossDocumentContext:
    workspace_id: UUID
    evaluation_date: date
    property: PropertySnapshot
    documents: tuple[Document, ...]


def money(fact: Fact | None) -> Money | None:
    if fact is None or fact.field.value_kind != "money" or fact.field.currency is None:
        return None
    return Money.model_validate({"amount": fact.field.value, "currency": fact.field.currency})


def fact_date(fact: Fact | None) -> date | None:
    return (
        date.fromisoformat(str(fact.field.value))
        if fact and fact.field.value_kind == "date"
        else None
    )


def ids(facts: list[Fact] | tuple[Fact, ...]) -> list[UUID]:
    return sorted({f.evidence_id for f in facts})


def initial_association(document: Document, property: PropertySnapshot) -> AssociationStatus:
    from viesett.document_intelligence.association import address_parts, normalize

    address = property.address
    if (
        address is None
        or property.stale
        or property.resolution_status not in {"RESOLVED", "PARTIALLY_RESOLVED"}
    ):
        return AssociationStatus.UNVERIFIED
    printed = document.value("address")
    if not isinstance(printed, str) or (parts := address_parts(printed)) is None:
        return AssociationStatus.UNVERIFIED
    street, number, box, postal = parts
    if (street, number, postal) != (
        normalize(address.street_name),
        normalize(address.house_number),
        address.postal_code,
    ):
        return AssociationStatus.MISMATCH
    if box and box != normalize(address.box_number or ""):
        return AssociationStatus.MISMATCH
    explicit_box = document.value("box_number")
    if explicit_box and normalize(str(explicit_box)) != normalize(address.box_number or ""):
        return AssociationStatus.POSSIBLE_MATCH
    return AssociationStatus.MATCHED


def private_lot_corroborated(document: Document, property: PropertySnapshot) -> bool:
    from viesett.document_intelligence.association import address_parts, normalize

    if property.address is None or not property.address.box_number:
        return True
    box = normalize(property.address.box_number)
    if normalize(str(document.value("box_number") or "")) == box:
        return True
    parts = address_parts(str(document.value("address") or ""))
    return bool(parts and parts[2] == box)
