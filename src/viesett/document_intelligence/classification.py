import re

from viesett.domain.intelligence import AnalysisKind, Classification, PageText

SIGNALS: dict[AnalysisKind, tuple[tuple[str, str, float], ...]] = {
    AnalysisKind.EPC: (
        ("epc_heading", r"\benergieprestatiecertificaat\b", 0.6),
        ("veka_issuer", r"\bVEKA\b|vlaams energie.{0,10}klimaatagentschap", 0.2),
        ("epc_fields", r"\benergiescore\b|\bEPC.label\b|kWh\s*/\s*m[²2]", 0.2),
    ),
    AnalysisKind.ASBESTOS_CERTIFICATE: (
        ("asbestos_heading", r"\basbestattest\b|\basbestinventarisattest\b", 0.6),
        ("ovam_issuer", r"\bOVAM\b|openbare vlaamse afvalstoffenmaatschappij", 0.2),
        ("asbestos_conclusion", r"\basbestveilig\b|asbestmaterialen", 0.2),
    ),
    AnalysisKind.ELECTRICAL_INSPECTION: (
        ("electrical_heading", r"(?:verslag|controle|keuring).{0,50}elektrische installatie", 0.6),
        ("arei_marker", r"\bAREI\b|algemeen reglement op de elektrische", 0.2),
        ("inspection_fields", r"\b(?:inbreuken|gelijkvormigheid|niet.conform|conform)\b", 0.2),
    ),
    AnalysisKind.SOIL_CERTIFICATE: (
        ("soil_heading", r"\bbodemattest\b", 0.6),
        ("ovam_issuer", r"\bOVAM\b|openbare vlaamse afvalstoffenmaatschappij", 0.2),
        ("soil_fields", r"grondeninformatieregister|kadastrale gegevens|CaPaKey", 0.2),
    ),
}
CLASSIFIER_VERSION = "signals:2.0.0"


def classify(pages: PageText) -> Classification:
    from viesett.coownership.extraction import HEADINGS, heading_pattern

    # Character-limited pages; no filename, upstream metadata or AI signal.
    text = "\n".join(page.text for page in pages.pages[:3])
    scored = []
    for kind in HEADINGS:
        heading = bool(re.search(heading_pattern(kind), text))
        organization = bool(
            re.search(r"(?i)\b(?:VME|ACP|syndicus|syndic|mede-eigendom|copropriété)\b", text)
        )
        structure = bool(
            re.search(
                (
                    "(?im)^\\s*(?:gebouwadres|adresse de "
                    "l['’]immeuble|kavel|lot|toestand op|situation au)\\s*:"
                ),
                text,
            )
        )
        matched = (
            (["co_heading"] if heading else [])
            + (["co_organization"] if organization else [])
            + (["co_fields"] if structure else [])
        )
        scored.append((0.6 * heading + 0.2 * organization + 0.2 * structure, kind, matched))
    for kind, definitions in SIGNALS.items():
        matches = [
            (name, weight)
            for name, pattern, weight in definitions
            if re.search(pattern, text, re.I)
        ]
        scored.append((sum(weight for _, weight in matches), kind, [name for name, _ in matches]))
    scored.sort(reverse=True)
    score, kind, signals = scored[0]
    # A mixed packet with two document headings is not a standardized document.
    competing_headings = sum(
        bool(re.search(signals[0][1], text, re.I)) for signals in SIGNALS.values()
    ) + sum(bool(re.search(heading_pattern(kind), text)) for kind in HEADINGS)
    accepted = score >= 0.8 and len(signals) >= 2 and competing_headings == 1
    return Classification(
        predicted_kind=kind if accepted else AnalysisKind.UNKNOWN,
        confidence=round(score, 2),
        matched_signals=signals,
        classifier_version=CLASSIFIER_VERSION,
    )
