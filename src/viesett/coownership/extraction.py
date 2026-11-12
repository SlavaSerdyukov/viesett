"""Bounded NL/FR labeled layouts; never arbitrary minutes or personal profiles."""

import re
from datetime import date
from decimal import Decimal, InvalidOperation

from viesett.document_intelligence.extractors import DATE, parse_date
from viesett.document_intelligence.pdf import ExtractionFailure
from viesett.domain.coownership import CO_KINDS, DecisionStatus, WorkCategory
from viesett.domain.intelligence import AnalysisKind, CoMetadata, ExtractedField, PageText

VERSION = "co-ownership:1.0.0"
HEADINGS = {
    AnalysisKind.SYNDIC_INFORMATION: (
        "(?:syndicusinformatie|inlichtingen (?:artikel|art[.]) "
        "3[.]94|renseignements (?:article|art[.]) 3[.]94)"
    ),
    AnalysisKind.AGM_MINUTES: (
        "(?:notulen (?:gewone )?algemene "
        "vergadering|procès-verbal (?:de l['’])?assemblée "
        "générale ordinaire)"
    ),
    AnalysisKind.EXTRAORDINARY_AGM_MINUTES: (
        "(?:notulen buitengewone algemene "
        "vergadering|procès-verbal (?:de l['’])?assemblée "
        "générale extraordinaire)"
    ),
    AnalysisKind.BASIS_DEED: r"(?:basisakte|acte de base)",
    AnalysisKind.CO_OWNERSHIP_REGULATIONS: (
        "(?:reglement van mede-eigendom|règlement de copropriété)"
    ),
    AnalysisKind.INTERNAL_RULES: r"(?:reglement van interne orde|règlement d['’]ordre intérieur)",
    AnalysisKind.PERIODIC_CHARGE_STATEMENT: (
        "(?:periodieke afrekening|décompte périodique des charges)"
    ),
    AnalysisKind.BALANCE_SHEET: r"(?:balans|bilan de copropriété)",
    AnalysisKind.CAPITAL_CALL: r"(?:kapitaaloproep|appel de fonds)",
    AnalysisKind.RESERVE_FUND_STATEMENT: r"(?:reservekapitaalstaat|état du fonds de réserve)",
    AnalysisKind.OTHER_CO_OWNERSHIP_DOCUMENT: r"(?:mede-eigendomsdocument|document de copropriété)",
}


def heading_pattern(kind: AnalysisKind) -> str:
    return r"(?im)^\s*" + HEADINGS[kind] + r"\s*$"


def category(text: str) -> WorkCategory:
    patterns = {
        WorkCategory.ROOF: r"dak|toiture",
        WorkCategory.FACADE: r"gevel|façade|facade",
        WorkCategory.LIFT: r"lift|ascenseur",
        WorkCategory.HEATING: r"verwarming|chauffage",
        WorkCategory.INSULATION: r"isolatie|isolation",
        WorkCategory.WINDOWS: r"ramen|fenêtres",
        WorkCategory.STRUCTURAL: r"structuur|structure",
        WorkCategory.ELECTRICAL_COMMON: r"elektr|électr",
        WorkCategory.FIRE_SAFETY: r"brandveilig|incendie",
    }
    matches = [key for key, pattern in patterns.items() if re.search(pattern, text, re.I)]
    return matches[0] if len(matches) == 1 else WorkCategory.OTHER


def amount(value: str) -> tuple[str, str] | None:
    match = re.fullmatch(
        (
            "\\s*(?:(EUR|USD|GBP|€)\\s*)?(-?[0-9][0-9 "
            ".]*(?:,[0-9]{2})?|-?[0-9]+[.][0-9]{2})\\s*(EUR|USD|"
            "GBP|€)?\\s*"
        ),
        value,
    )
    if not match:
        return None
    before, number, after = match.groups()
    if not (before or after) or (before and after and before != after):
        return None
    currency = "EUR" if (before or after) == "€" else (before or after)
    number = number.strip()
    if " " in number and not re.fullmatch(r"-?\d{1,3}(?: \d{3})+(?:[,.]\d{2})?", number):
        return None
    number = number.replace(" ", "")
    if "," in number:
        integer, cents = number.split(",")
        if "." in integer and not re.fullmatch(r"-?\d{1,3}(?:[.]\d{3})+", integer):
            return None
        number = integer.replace(".", "") + "." + cents
    elif number.count(".") > 1 or ("." in number and not re.fullmatch(r"-?\d+[.]\d{2}", number)):
        return None
    try:
        parsed = Decimal(number)
        if not parsed.is_finite() or abs(parsed) > Decimal("999999999999.99"):
            return None
        return format(parsed.quantize(Decimal("0.01")), ".2f"), str(currency)
    except InvalidOperation:
        return None


def enterprise(value: str) -> str | None:
    digits = re.sub(r"[.\s]", "", value.removeprefix("BE"))
    if re.fullmatch(r"[01]\d{9}", digits) and int(digits[-2:]) == 97 - int(digits[:8]) % 97:
        return digits
    return None


def extract_co(pages: PageText, kind: AnalysisKind) -> tuple[list[ExtractedField], CoMetadata]:
    if kind not in CO_KINDS:
        raise ValueError("Unsupported co-ownership adapter")
    text = "\n".join(p.text for p in pages.pages)
    nl = len(
        re.findall(
            (
                "(?i)\\b(?:syndicus|vergadering|kapitaal|notulen|bas"
                "isakte|afrekening|kavel|gebouwadres|werkkapitaal|r"
                "eservekapitaal|inlichtingen)\\b"
            ),
            text,
        )
    )
    fr = len(
        re.findall(
            (
                "(?i)\\b(?:syndic|assemblée|fonds|copropriété|bilan|"
                "règlement|lot|décompte|charges|immeuble|renseignem"
                "ents)\\b"
            ),
            text,
        )
    )
    language = "nl" if nl >= 2 and nl > fr else "fr" if fr >= 2 and fr > nl else "unknown"
    fields: list[ExtractedField] = []
    group = "root"
    malformed = False
    string_labels = {
        "association_name": (
            "(?:VME|ACP|vereniging van mede-eigenaars|association des copropriétaires)"
        ),
        "address": r"(?:gebouwadres|adresse de l['’]immeuble)",
        "enterprise_number": (
            "(?:VME ondernemingsnummer|numéro d['’]entreprise ACP|ondernemingsnummer|numéro BCE)"
        ),
        "syndic_name": r"(?:syndicus|syndic)",
        "syndic_enterprise_number": r"(?:ondernemingsnummer syndicus|numéro BCE syndic)",
        "lot": r"(?:kavel|lot privatif|lot)",
        "box_number": r"(?:bus|busnummer|boîte)",
        "private_designation": r"(?:private eenheid|désignation privative)",
        "attached_lot": r"(?:bijbehorende kavel|lot annexe lié)",
        "share": r"(?:aandeel gemeenschappelijke delen|quote-part des parties communes)",
        "allocation_share": r"(?:kostensleutel|clé de répartition)",
        "balance_reference": r"(?:laatste goedgekeurde balans|dernier bilan approuvé)",
        "balance_identifier": r"(?:balansreferentie|référence du bilan)",
        "project_reference": r"(?:projectreferentie|référence du projet|beslissingsreferentie)",
        "call_reference": r"(?:oproepreferentie|référence de l['’]appel)",
        "decision_status": r"(?:besluit|beslissing|décision)",
        "litigation_status": r"(?:status geschil|statut du litige)",
        "vote_result": r"(?:stemresultaat|résultat du vote)",
        "funding_source": r"(?:financieringsbron|source de financement)",
        "fund_type": r"(?:fondstype|type de fonds)",
        "reporting_context": r"(?:context|contexte)",
    }
    date_labels = {
        "as_of": r"(?:toestand op|situatie op|situation au|datum document|date du document)",
        "meeting_date": r"(?:vergaderdatum|date de l['’]assemblée)",
        "request_date": r"(?:aanvraagdatum|date de demande)",
        "response_date": r"(?:antwoorddatum|date de réponse)",
        "approved_date": r"(?:goedgekeurd op AV|approuvé par AG le)",
        "balance_date": r"(?:balansdatum|date du bilan)",
        "due_date": r"(?:vervaldatum|date d['’]échéance)",
        "expected_start": r"(?:geplande uitvoering|exécution prévue)",
        "provisional_acceptance_date": (
            "(?:voorlopige oplevering gemene delen|réception provisoire des parties communes)"
        ),
    }
    money_labels = {
        "working_capital": r"(?:werkkapitaal|fonds de roulement)",
        "reserve_capital": r"(?:reservekapitaal|fonds de réserve)",
        "seller_arrears": r"(?:achterstallen verkoper|arriérés du vendeur)",
        "ordinary_charges": r"(?:gewone gemeenschappelijke lasten|charges communes ordinaires)",
        "extraordinary_charges": r"(?:buitengewone lasten|charges extraordinaires)",
        "reserve_contribution": r"(?:reservebijdrage|cotisation au fonds de réserve)",
        "working_contribution": r"(?:bijdrage werkkapitaal|provision fonds de roulement)",
        "annual_reserve_contribution": (
            "(?:jaarlijkse reservebijdrage|cotisation annuelle réserve)"
        ),
        "previous_ordinary_charges": (
            "(?:gewone lasten vorig boekjaar|charges ordinaires exercice précédent)"
        ),
        "cash_bank_total": r"(?:bank en kas totaal|total banque et caisse)",
        "receivables": r"(?:vorderingen totaal|total créances)",
        "payables": r"(?:schulden totaal|total dettes)",
        "amount_due": r"(?:te betalen|montant dû)",
        "credit": r"(?:tegoed|crédit)",
        "budget": r"(?:goedgekeurd budget|budget approuvé)",
        "estimated_budget": r"(?:geraamde kost|coût estimé)",
        "reserve_allocation": r"(?:reserveallocatie project|affectation réserve au projet)",
        "call_total": r"(?:oproep totaal|total de l['’]appel)",
        "lot_amount": r"(?:oproep voor deze kavel|appel pour ce lot)",
        "dispute_amount": r"(?:bedrag geschil|montant en litige)",
    }
    bool_labels = {
        "calls_none": r"(?:reserveoproepen|appels de fonds réserve)",
        "litigation_none": r"(?:hangende rechtszaken|procédures judiciaires en cours)",
        "approved_works_none": r"(?:goedgekeurde werken|travaux approuvés)",
        "general_share_applies": (
            "(?:algemene kostensleutel van toepassing|quote-part générale applicable)"
        ),
        "full_project_call": r"(?:oproep dekt volledig project|appel couvre tout le projet)",
        "reserve_waiver": r"(?:vrijstelling reservekapitaal AV|dispense fonds de réserve AG)",
    }

    def add(
        key: str,
        value: str | int | bool,
        page: int,
        start: int,
        end: int,
        value_kind: str = "text",
        *,
        field_group: str | None = None,
        currency: str | None = None,
    ) -> None:
        fields.append(
            ExtractedField.model_validate(
                {
                    "key": "document.co." + key,
                    "value": value,
                    "value_kind": value_kind,
                    "page": page,
                    "start": start,
                    "end": end,
                    "parser_version": VERSION,
                    "group": field_group or group,
                    "currency": currency,
                }
            )
        )

    for page in pages.pages:
        for line in re.finditer(r"[^\n]+", page.text):
            value_line = line.group().strip()
            item = re.fullmatch(
                r"(?i)(?:agendapunt|point)\s+(\d{1,3})\s*:\s*(.{1,150})", value_line
            )
            call = re.fullmatch(
                r"(?i)(?:kapitaaloproep|appel de fonds)\s+(\d{1,3})\s*:\s*([A-Z0-9_-]{1,60})",
                value_line,
            )
            case = re.fullmatch(
                r"(?i)(hangend geschil|litige en cours|geschil|litige)"
                r"\s+(\d{1,3})\s*:\s*(.{1,150})",
                value_line,
            )
            if item:
                group = "work_" + item.group(1)
                add(
                    "category", category(item.group(2)).value, page.number, line.start(), line.end()
                )
            elif call:
                group = "call_" + call.group(1)
                add("call_reference", call.group(2), page.number, line.start(), line.end())
            elif case:
                group = "litigation_" + case.group(2)
                add(
                    "litigation_category",
                    category(case.group(3)).value,
                    page.number,
                    line.start(),
                    line.end(),
                )
                if case.group(1).lower() in {"hangend geschil", "litige en cours"}:
                    add("litigation_status", "PENDING", page.number, line.start(), line.end())
            for key, label in string_labels.items():
                match = re.fullmatch(label + r"\s*:\s*(.{1,180})", value_line, re.I)
                if not match:
                    continue
                value = match.group(1).strip()
                chosen_group = (
                    "root"
                    if key
                    in {
                        "association_name",
                        "enterprise_number",
                        "syndic_name",
                        "syndic_enterprise_number",
                        "address",
                        "lot",
                        "box_number",
                        "share",
                        "attached_lot",
                        "private_designation",
                        "balance_reference",
                    }
                    else group
                )
                if key in {"enterprise_number", "syndic_enterprise_number"}:
                    parsed_enterprise = enterprise(value)
                    if parsed_enterprise is None:
                        malformed = True
                        continue
                    value = parsed_enterprise
                elif key == "association_name":
                    value = ("VME " if language != "fr" else "ACP ") + value
                elif key == "syndic_name" and not re.search(
                    r"\b(?:BV|NV|SRL|SA|SC)\b", value, re.I
                ):
                    continue
                elif key in {"share", "allocation_share", "vote_result"}:
                    fraction = re.fullmatch(r"\s*(\d{1,9})\s*/\s*(\d{1,9})\s*", value)
                    if (
                        not fraction
                        or not 0 <= int(fraction.group(1)) <= int(fraction.group(2))
                        or int(fraction.group(2)) == 0
                    ):
                        malformed = True
                        continue
                    if key == "vote_result":
                        value = fraction.group(1) + "/" + fraction.group(2)
                elif key in {
                    "lot",
                    "box_number",
                    "attached_lot",
                    "private_designation",
                    "project_reference",
                    "call_reference",
                }:
                    if not re.fullmatch(r"[A-Za-z0-9_./ -]{1,60}", value):
                        malformed = True
                        continue
                elif key == "litigation_status":
                    value = {
                        "hangend": "PENDING",
                        "lopend": "PENDING",
                        "en cours": "PENDING",
                        "afgesloten": "CLOSED",
                        "clôturé": "CLOSED",
                    }.get(value.lower(), "UNKNOWN")
                elif key == "decision_status":
                    statuses = {
                        "goedgekeurd": DecisionStatus.APPROVED,
                        "approuvé": DecisionStatus.APPROVED,
                        "voorgesteld": DecisionStatus.PROPOSED,
                        "proposé": DecisionStatus.PROPOSED,
                        "verworpen": DecisionStatus.REJECTED,
                        "rejeté": DecisionStatus.REJECTED,
                        "uitgesteld": DecisionStatus.POSTPONED,
                        "reporté": DecisionStatus.POSTPONED,
                        "informatie": DecisionStatus.INFORMATION_ONLY,
                        "information": DecisionStatus.INFORMATION_ONLY,
                    }
                    value = statuses.get(value.lower(), DecisionStatus.UNKNOWN).value
                elif key in {"fund_type", "funding_source"}:
                    terms = {
                        "reservekapitaal": "RESERVE_CAPITAL",
                        "fonds de réserve": "RESERVE_CAPITAL",
                        "werkkapitaal": "WORKING_CAPITAL",
                        "fonds de roulement": "WORKING_CAPITAL",
                        "buitengewoon": "EXTRAORDINARY",
                        "extraordinaire": "EXTRAORDINARY",
                    }
                    value = terms.get(value.lower(), "UNKNOWN")
                elif key == "reporting_context":
                    value = {
                        "gebouw": "BUILDING",
                        "immeuble": "BUILDING",
                        "kavel": "LOT",
                        "lot": "LOT",
                    }.get(value.lower(), "UNSPECIFIED")
                # Contact/attendance/free personal prose is never a supported field.
                if re.search(r"@|\b(?:tel|IBAN|gsm)\b|BE\d{2}[ ]?\d{4}", value, re.I):
                    continue
                add(key, value, page.number, line.start(), line.end(), field_group=chosen_group)
            restriction = re.fullmatch(
                (
                    "(?i)(beroepsgebruik|usage professionnel|structurele "
                    "wijzigingen|modifications structurelles|"
                    "samenvoegen eenheden|réunion des "
                    "lots|huisdieren|animaux|afval|déchets|verhuizen|dé"
                    "ménagement|"
                    "toegang|accès|gebruik gemene delen|usage parties "
                    "communes)\\s*:\\s*(verboden|interdit|toestemming "
                    "vereist|autorisation requise)"
                ),
                value_line,
            )
            if restriction:
                codes = {
                    "beroepsgebruik": "PROFESSIONAL_USE",
                    "usage professionnel": "PROFESSIONAL_USE",
                    "structurele wijzigingen": "STRUCTURAL_ALTERATIONS",
                    "modifications structurelles": "STRUCTURAL_ALTERATIONS",
                    "samenvoegen eenheden": "COMBINING_UNITS",
                    "réunion des lots": "COMBINING_UNITS",
                    "huisdieren": "PETS",
                    "animaux": "PETS",
                    "afval": "WASTE",
                    "déchets": "WASTE",
                    "verhuizen": "MOVING",
                    "déménagement": "MOVING",
                    "toegang": "ACCESS",
                    "accès": "ACCESS",
                    "gebruik gemene delen": "COMMON_USAGE",
                    "usage parties communes": "COMMON_USAGE",
                }
                add(
                    "restriction",
                    codes[restriction.group(1).lower()],
                    page.number,
                    line.start(),
                    line.end(),
                )
            for key, label in date_labels.items():
                match = re.fullmatch(label + r"\s*:\s*(" + DATE + ")", value_line, re.I)
                if match and (parsed := parse_date(match.group(1))):
                    add(
                        key,
                        parsed,
                        page.number,
                        line.start(),
                        line.end(),
                        "date",
                        field_group="root" if key not in {"due_date", "expected_start"} else group,
                    )
            for key, label in money_labels.items():
                match = re.fullmatch(label + r"\s*:\s*(.{1,60})", value_line, re.I)
                if match:
                    money = amount(match.group(1))
                    if money:
                        add(
                            key,
                            money[0],
                            page.number,
                            line.start(),
                            line.end(),
                            "money",
                            currency=money[1],
                            field_group=group
                            if key
                            in {
                                "budget",
                                "estimated_budget",
                                "reserve_allocation",
                                "call_total",
                                "lot_amount",
                                "dispute_amount",
                            }
                            else "root",
                        )
                    else:
                        malformed = True
            for key, label in bool_labels.items():
                match = re.fullmatch(
                    label + r"\s*:\s*(geen|aucun|aucune|ja|oui|nee|non)", value_line, re.I
                )
                if match:
                    raw = match.group(1).lower()
                    value = (
                        raw in {"geen", "aucun", "aucune"}
                        if key.endswith("_none")
                        else raw in {"ja", "oui"}
                    )
                    add(key, value, page.number, line.start(), line.end(), "boolean")
            for key, label in {
                "minutes_coverage": (
                    "(?:volledige dekking gewone en buitengewone "
                    "AV|couverture complète AG ordinaires et "
                    "extraordinaires)"
                ),
                "charges_coverage": (
                    "(?:volledige dekking afrekeningen|couverture complète décomptes)"
                ),
                "period": r"(?:periode|période)",
            }.items():
                match = re.fullmatch(
                    label + r"\s*:\s*(" + DATE + r")\s*(?:tot|au|à)\s*(" + DATE + r")",
                    value_line,
                    re.I,
                )
                if match:
                    start, end = parse_date(match.group(1)), parse_date(match.group(2))
                    if start and end and start <= end:
                        add(
                            key + "_start",
                            start,
                            page.number,
                            line.start(),
                            line.end(),
                            "date",
                            field_group="root",
                        )
                        add(
                            key + "_end",
                            end,
                            page.number,
                            line.start(),
                            line.end(),
                            "date",
                            field_group="root",
                        )
    roots = {}
    for key in {f.key for f in fields if f.group == "root"}:
        candidates = [f for f in fields if f.key == key and f.group == "root"]
        if len({str(f.value) for f in candidates}) == 1:
            roots[key.rsplit(".", 1)[-1]] = candidates[0]
    date_fact = (
        roots.get("as_of")
        or roots.get("response_date")
        or roots.get("balance_date")
        or roots.get("meeting_date")
    )
    for fact in fields:
        basis_date = (
            roots.get("meeting_date")
            if fact.group.startswith("work_")
            else roots.get("balance_date")
            if kind == AnalysisKind.BALANCE_SHEET
            else date_fact
        )
        fact.effective_date = date.fromisoformat(str(basis_date.value)) if basis_date else None
        fact.context = (
            str(roots["reporting_context"].value) if "reporting_context" in roots else "UNSPECIFIED"
        )
    if len(fields) > 300:
        raise ExtractionFailure("structured_field_limit")
    useful = [
        f
        for f in fields
        if f.key.rsplit(".", 1)[-1]
        not in {
            "association_name",
            "address",
            "enterprise_number",
            "syndic_name",
            "syndic_enterprise_number",
            "lot",
            "box_number",
            "reporting_context",
            "as_of",
        }
    ]
    status = (
        "UNPARSEABLE"
        if malformed and not useful
        else "UNSUPPORTED_LAYOUT"
        if not fields
        else "PARSED"
        if useful and not malformed
        else "PARTIALLY_PARSED"
    )
    return fields, CoMetadata.model_validate(
        {
            "detected_language": language,
            "confidence": 0.9 if language != "unknown" else 0,
            "parse_status": status,
            "extractor_version": VERSION,
        }
    )
