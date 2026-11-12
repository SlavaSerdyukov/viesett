"""Conservative labeled fields and explicit statements, never a general PDF interpreter."""

import re
from datetime import datetime

from viesett.document_intelligence.pdf import ExtractionFailure
from viesett.domain.coownership import CO_KINDS
from viesett.domain.intelligence import AnalysisKind, AsbestosVariant, ExtractedField, PageText
from viesett.domain.types import EpcLabel

VERSIONS = {
    AnalysisKind.EPC: "epc:1.0.0",
    AnalysisKind.ASBESTOS_CERTIFICATE: "asbestos:1.0.0",
    AnalysisKind.ELECTRICAL_INSPECTION: "electrical:1.0.0",
    AnalysisKind.SOIL_CERTIFICATE: "soil:1.0.0",
    AnalysisKind.UNKNOWN: "unknown:1.0.0",
}

VERSIONS.update({kind: "co-ownership:1.0.0" for kind in CO_KINDS})
CAPAKEY = r"\b[0-9]{5}[A-Z][0-9]{4}[/\-][0-9]{2}[A-Z_0][0-9]{3}\b"
DATE = r"(?:\d{4}-\d{2}-\d{2}|\d{1,2}[./-]\d{1,2}[./-]\d{4})"


def parse_date(value: str) -> str | None:
    for pattern in ("%Y-%m-%d", "%d/%m/%Y", "%d.%m.%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(value, pattern).date().isoformat()
        except ValueError:
            continue
    return None


def extract_fields(pages: PageText, kind: AnalysisKind) -> list[ExtractedField]:
    if kind in CO_KINDS:
        from viesett.coownership.extraction import extract_co

        return extract_co(pages, kind)[0]
    if kind == AnalysisKind.UNKNOWN:
        return []
    prefix = {
        AnalysisKind.EPC: "epc",
        AnalysisKind.ASBESTOS_CERTIFICATE: "asbestos",
        AnalysisKind.ELECTRICAL_INSPECTION: "electrical",
        AnalysisKind.SOIL_CERTIFICATE: "soil",
    }[kind]
    fields: list[ExtractedField] = []

    def add(
        key: str,
        value: str | int | float | bool,
        page: int,
        start: int,
        end: int,
        value_kind: str = "text",
    ) -> None:
        fields.append(
            ExtractedField.model_validate(
                {
                    "key": f"document.{prefix}.{key}",
                    "value": value,
                    "value_kind": value_kind,
                    "page": page,
                    "start": start,
                    "end": end,
                    "parser_version": VERSIONS[kind],
                }
            )
        )

    # Require explicit field labels; an issuer's unlabeled contact address is not
    # the inspected property's address. Next-line values are supported.
    labels: dict[str, str] = {
        "address": r"(?:adres(?: van (?:het gebouw|de woning|de installatie))?|ligging)",
        "certificate_id": (
            "(?:certificaatnummer|attestnummer|unieke code|referentie|verslagnummer)"
        ),
        "box_number": r"(?:busnummer|bus|eenheid)",
    }
    if kind == AnalysisKind.ELECTRICAL_INSPECTION:
        labels.update(
            {
                "inspection_body": r"(?:controleorganisme|keuringsorganisme)",
                "inspection_type": (
                    "(?:type (?:controle|keuring)|aard van (?:het onderzoek|de keuring))"
                ),
            }
        )
    if kind == AnalysisKind.SOIL_CERTIFICATE:
        labels.update(
            {
                "cadastral_division": r"(?:kadastrale afdeling|afdeling)",
                "section": r"sectie",
                "parcel_number": r"perceelnummer",
                "soil_quality_statement": r"(?:bodemkwaliteit|conclusie bodemkwaliteit)",
                "investigation_reference": r"(?:bodemonderzoek|onderzoeksreferentie)",
                "advice": r"(?:advies|voorwaarde)",
            }
        )
    date_labels = {
        "issue_date": (
            "(?:datum (?:van opmaak|attest|certificaat)|opgemaakt op|afgeleverd op|uitgiftedatum)"
        ),
        "valid_until": r"(?:geldig tot(?: en met)?|geldigheidsdatum)",
    }
    if kind == AnalysisKind.ELECTRICAL_INSPECTION:
        date_labels["inspection_date"] = (
            r"(?:inspectiedatum|keuringsdatum|datum (?:controle|onderzoek))"
        )
    if kind == AnalysisKind.SOIL_CERTIFICATE:
        date_labels["issue_date"] = r"(?:datum(?: bodemattest)?|afgeleverd op|uitgiftedatum)"
    for page in pages.pages:
        text = page.text
        for key, label in labels.items():
            for m in re.finditer(r"(?im)^\s*" + label + r"\s*:\s*([^\n]{1,300})$", text):
                value = m.group(1).strip()
                if value:
                    add(key, value, page.number, m.start(1), m.end(1))
        for key, label in date_labels.items():
            for m in re.finditer(r"(?im)^\s*" + label + r"\s*:?\s*(" + DATE + r")\s*$", text):
                value = parse_date(m.group(1))
                if value:
                    add(key, value, page.number, m.start(1), m.end(1), "date")
        if kind == AnalysisKind.EPC:
            for m in re.finditer(
                r"(?im)^\s*(?:EPC.label|energielabel|label)\s*:?\s*(A\+|[A-F])\s*$", text
            ):
                add(
                    "label",
                    EpcLabel(m.group(1).upper()).value,
                    page.number,
                    m.start(1),
                    m.end(1),
                    "epc_label",
                )
            for m in re.finditer(
                (
                    r"(?im)^\s*(?:energiescore|energieverbruik)\s*:?\s*(-?\d{1,4}"
                    r"(?:[.,]\d{1,2})?)\s*kWh\s*/\s*\(?m[²2]"
                    r"(?:[.\s/]*jaar|\s+per jaar)?\)?\s*$"
                ),
                text,
            ):
                score = float(m.group(1).replace(",", "."))
                if -1000 <= score <= 3000:
                    add("energy_score", score, page.number, m.start(1), m.end(1), "decimal")
            for m in re.finditer(
                (
                    "(?im)^\\s*(?:certificaattype|bestemming)\\s*:\\s*(residentieel|"
                    "niet-residentieel|woning|appartement)\\s*$|\\bEPC Residentieel\\b"
                ),
                text,
            ):
                value = m.group(1).lower() if m.group(1) else "residentieel"
                add(
                    "residential",
                    value != "niet-residentieel",
                    page.number,
                    m.start(),
                    m.end(),
                    "boolean",
                )
        elif kind == AnalysisKind.ASBESTOS_CERTIFICATE:
            for m in re.finditer(
                (
                    "(?im)^\\s*(?:eindconclusie|conclusie|asbestveiligheid)\\s*:?\\s"
                    "*(niet[- ]asbestveilig|asbestveilig)\\s*$"
                ),
                text,
            ):
                add(
                    "asbestos_safe",
                    not m.group(1).lower().startswith("niet"),
                    page.number,
                    m.start(1),
                    m.end(1),
                    "boolean",
                )
                add("conclusion", m.group(1), page.number, m.start(1), m.end(1))
            for m in re.finditer(
                (
                    "(?im)^\\s*(?:aantal (?:asbestmaterialen|asbesthoudende "
                    "materialen)|asbestmaterialen)\\s*:\\s*(\\d{1,4})\\s*$"
                ),
                text,
            ):
                add("material_count", int(m.group(1)), page.number, m.start(1), m.end(1), "integer")
            variants = {
                "privatieve delen": AsbestosVariant.PRIVATE_UNIT,
                "privatief deel": AsbestosVariant.PRIVATE_UNIT,
                "gemene delen": AsbestosVariant.COMMON_PARTS,
                "gemeenschappelijk gebruikte delen": AsbestosVariant.COMMONLY_USED_PARTS,
            }
            for m in re.finditer(
                (
                    "(?im)^\\s*(?:onderwerp|toepassingsgebied)\\s*:\\s*(privatieve "
                    "delen|privatief deel|gemene delen|gemeenschappelijk gebruikte "
                    "delen)\\s*$"
                ),
                text,
            ):
                add(
                    "variant", variants[m.group(1).lower()].value, page.number, m.start(1), m.end(1)
                )
            for m in re.finditer(
                r"(?im)^\s*(verwijderen|beheren|dringend verwijderen)\s*:\s*([^\n]{1,300})$", text
            ):
                add("action", m.group(0).strip(), page.number, m.start(), m.end())
        elif kind == AnalysisKind.ELECTRICAL_INSPECTION:
            for m in re.finditer(
                (
                    "(?im)^\\s*(?:besluit|conclusie|resultaat)\\s*:\\s*(niet[- "
                    "]conform|conform|voldoet niet|voldoet)\\s*$"
                ),
                text,
            ):
                add(
                    "conforming",
                    m.group(1).lower() in {"conform", "voldoet"},
                    page.number,
                    m.start(1),
                    m.end(1),
                    "boolean",
                )
                add("conclusion", m.group(1), page.number, m.start(1), m.end(1))
            for key, label in {"violation": "inbreuk", "follow_up": "opvolging"}.items():
                for m in re.finditer(
                    r"(?im)^\s*" + label + r"(?:\s+\d+)?\s*:\s*([^\n]{1,300})$", text
                ):
                    add(key, m.group(1).strip(), page.number, m.start(1), m.end(1))
        elif kind == AnalysisKind.SOIL_CERTIFICATE:
            for m in re.finditer(CAPAKEY, text, re.I):
                add(
                    "parcel.capakey",
                    m.group().upper().replace("-", "/"),
                    page.number,
                    m.start(),
                    m.end(),
                )
            for m in re.finditer(
                (
                    "(?i)(?:deze grond|het perceel|de grond) is (niet )?opgenomen in "
                    "het [Gg]rondeninformatieregister"
                ),
                text,
            ):
                add(
                    "gir_recorded", not bool(m.group(1)), page.number, m.start(), m.end(), "boolean"
                )
                add("gir_statement", m.group(), page.number, m.start(), m.end())
            for m in re.finditer(
                (
                    "(?i)(?:deze grond|de grond) is (?:een )?(geen "
                    ")?risicogrond\\b|OVAM heeft geen aanwijzingen dat deze grond een "
                    "risicogrond is"
                ),
                text,
            ):
                negative = bool(m.group(1)) or "geen aanwijzingen" in m.group().lower()
                add("risk_ground", not negative, page.number, m.start(), m.end(), "boolean")
    # Conflicting singleton values are absent, never first-match-wins. Repeated
    # parcels/actions remain separate. Bounded fields cannot retain full pages.
    multi = {
        "document.soil.parcel.capakey",
        "document.soil.parcel_number",
        "document.soil.section",
        "document.soil.cadastral_division",
        "document.soil.investigation_reference",
        "document.soil.advice",
        "document.electrical.violation",
        "document.electrical.follow_up",
        "document.asbestos.action",
    }
    result: list[ExtractedField] = []
    for key in dict.fromkeys(f.key for f in fields):
        group = [f for f in fields if f.key == key]
        values = {str(f.value) for f in group}
        if key in multi:
            result.extend({str(f.value): f for f in group}.values())
        elif len(values) == 1:
            result.append(group[0])
    if len(result) > 300:
        raise ExtractionFailure("structured_field_limit")
    return result
