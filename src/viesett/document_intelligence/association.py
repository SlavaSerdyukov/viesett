import re
import unicodedata

from viesett.domain.intelligence import Association, AssociationStatus, ExtractedField
from viesett.domain.property import PropertySnapshot


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFC", value).casefold()
    value = re.sub(r"\bstr\.(?=\s|$)", "straat", value)
    value = re.sub(r"(?<=\w)str\.(?=\s|$)", "straat", value)
    return re.sub(r"[\W_]+", " ", value).strip()


def address_parts(value: str) -> tuple[str, str, str | None, str] | None:
    match = re.fullmatch(
        (
            "\\s*(.+?)\\s+(\\d+[a-zA-Z]?)(?:\\s*(?:bus|box|bte)\\s*([\\w-]+))?\\"
            "s*[,;]?\\s+(\\d{4})\\s+[^\\d\\n]+\\s*"
        ),
        value,
        re.I,
    )
    if not match:
        return None
    street, number, box, postal = match.groups()
    return normalize(street), normalize(number), normalize(box) if box else None, postal


def associate(fields: list[ExtractedField], snapshot: PropertySnapshot) -> Association:
    revision = snapshot.identity_revision
    default = {"identity_revision": revision}
    if (
        snapshot.address is None
        or snapshot.stale
        or snapshot.resolution_status not in {"RESOLVED", "PARTIALLY_RESOLVED"}
    ):
        return Association(reason="A current selected official identity is unavailable", **default)
    address = snapshot.address
    official_parcels = {p.capakey for p in snapshot.parcels}
    parcels = {str(f.value) for f in fields if f.key.endswith(".parcel.capakey")}
    matched = sorted(parcels & official_parcels)
    statuses = []
    signals = []
    if parcels and official_parcels:
        statuses.append(
            AssociationStatus.MATCHED if parcels <= official_parcels else AssociationStatus.MISMATCH
        )
        signals.append("exact_capakey" if matched else "different_capakey")
    for f in fields:
        if not f.key.endswith(".address"):
            continue
        parsed = address_parts(str(f.value))
        if parsed is None:
            continue
        street, number, box, postal = parsed
        if (street, number, postal) != (
            normalize(address.street_name),
            normalize(address.house_number),
            address.postal_code,
        ):
            statuses.append(AssociationStatus.MISMATCH)
            signals.append("different_address")
        elif box != (normalize(address.box_number) if address.box_number else None):
            statuses.append(
                AssociationStatus.MISMATCH
                if box is not None and address.box_number is not None
                else AssociationStatus.POSSIBLE_MATCH
            )
            signals.append("box_missing_or_different")
        else:
            statuses.append(AssociationStatus.MATCHED)
            signals.append("exact_address_components")
    # A separately printed bus number must also agree, even if the address line
    # omits it. A parcel match never overrides a conflicting private unit.
    boxes = {normalize(str(f.value)) for f in fields if f.key.endswith(".box_number")}
    if boxes and boxes != {normalize(address.box_number or "")}:
        statuses.append(AssociationStatus.MISMATCH)
        signals.append("different_explicit_box")
    status = AssociationStatus.UNVERIFIED
    if AssociationStatus.MISMATCH in statuses:
        status = AssociationStatus.MISMATCH
    elif AssociationStatus.POSSIBLE_MATCH in statuses:
        status = AssociationStatus.POSSIBLE_MATCH
    elif AssociationStatus.MATCHED in statuses:
        status = AssociationStatus.MATCHED
    return Association(
        status=status,
        reason={
            AssociationStatus.MATCHED: "Explicit document identifiers match the official property",
            AssociationStatus.MISMATCH: (
                "Document address/unit/parcel conflicts with the official property"
            ),
            AssociationStatus.POSSIBLE_MATCH: (
                "Property components agree but private-unit identity needs review"
            ),
            AssociationStatus.UNVERIFIED: "No sufficiently precise comparable document identity",
        }[status],
        signals=signals,
        matched_parcels=matched,
        **default,
    )
