from datetime import date

from viesett.domain.intelligence import RuleMetadata

EPC_SOURCE = "https://www.vlaanderen.be/bouwen-wonen-en-energie/energieprestatiecertificaat-epc-bij-overdracht-of-verhuur-van-een-wooneenheid"
RENOVATION_SOURCE = "https://www.vlaanderen.be/bouwen-wonen-en-energie/kopen-en-verkopen/een-huis-of-appartement-kopen/renovatieverplichting-voor-residentiele-gebouwen"
ASBESTOS_SOURCE = "https://ovam.vlaanderen.be/heb-ik-een-asbestattest-nodig"
COMMON_SOURCE = "https://ovam.vlaanderen.be/w/asbestattest-gemene-delen-tegen-31/12/2026"
VALIDITY_SOURCE = "https://ovam.vlaanderen.be/veelgestelde-vragen-over-het-asbestattest"
ELECTRICAL_SOURCE = "https://economie.fgov.be/nl/themas/energie/bronnen-en-dragers-van-energie/elektriciteit/veiligheid-en-controle-van/controle-van-huishoudelijke/soorten-controles-van"
SOIL_SOURCE = "https://ovam.vlaanderen.be/welke-gegevens-staan-op-het-bodemattest"


def rule(
    code: str,
    source: str,
    name: str,
    start: date = date(2026, 11, 12),
    *,
    jurisdiction: str = "BE-VLG",
) -> RuleMetadata:
    return RuleMetadata(
        code=code,
        official_source_reference=source,
        official_source_name=name,
        effective_from=start,
        jurisdiction=jurisdiction,
    )


CATALOG = {
    r.code: r
    for r in [
        rule("FL_EPC_REQUIRED", EPC_SOURCE, "Vlaanderen / VEKA"),
        rule("FL_EPC_RENOVATION", RENOVATION_SOURCE, "Vlaanderen / VEKA"),
        rule("FL_ASBESTOS_REQUIRED", ASBESTOS_SOURCE, "OVAM", date(2022, 11, 23)),
        rule("FL_ASBESTOS_COMMON_PARTS", COMMON_SOURCE, "OVAM", date(2027, 1, 1)),
        rule("FL_ASBESTOS_COMMONLY_USED", COMMON_SOURCE, "OVAM", date(2025, 5, 1)),
        rule("FL_ASBESTOS_VALIDITY", VALIDITY_SOURCE, "OVAM"),
        rule("BE_ELECTRICAL_REQUIRED", ELECTRICAL_SOURCE, "FOD Economie / AREI", jurisdiction="BE"),
        rule(
            "BE_ELECTRICAL_NEGATIVE_SALE",
            ELECTRICAL_SOURCE,
            "FOD Economie / AREI",
            jurisdiction="BE",
        ),
        rule("FL_SOIL_REQUIRED", SOIL_SOURCE, "OVAM"),
        rule("FL_SOIL_PARCEL_COVERAGE", SOIL_SOURCE, "OVAM"),
        rule("FL_SOIL_RISK_GROUND", SOIL_SOURCE, "OVAM"),
        rule(
            "DOCUMENT_PROPERTY_ASSOCIATION",
            "https://data.vlaanderen.be/ns/adres",
            "Viesett deterministic identity comparison",
        ),
    ]
}


def effective(rule: RuleMetadata, evaluation_date: date) -> bool:
    return rule.effective_from <= evaluation_date and (
        rule.effective_to is None or evaluation_date <= rule.effective_to
    )
