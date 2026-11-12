from viesett.domain.schemas import DraftCreate
from viesett.domain.types import DocumentKind

LABELS = {
    "en": [
        "unspecified property document",
        "listing",
        "EPC",
        "asbestos certificate",
        "electrical inspection report",
        "soil certificate",
        "urban planning information",
        "syndic minutes",
        "co-ownership statutes",
        "reserve fund information",
        "other property document",
    ],
    "nl": [
        "onbekend vastgoeddocument",
        "verkoopadvertentie",
        "EPC",
        "asbestattest",
        "elektrisch keuringsverslag",
        "bodemattest",
        "stedenbouwkundige inlichtingen",
        "notulen van de syndicus",
        "statuten van de mede-eigendom",
        "informatie over het reservefonds",
        "ander vastgoeddocument",
    ],
}

CO_COMPONENT_LABELS = {
    "en": {
        "WORKING_CAPITAL": "current working-capital amount",
        "RESERVE_CAPITAL": "current reserve-capital amount",
        "SELLER_ARREARS": "seller's outstanding arrears for the purchased lot",
        "RESERVE_CAPITAL_CALLS": "status of reserve-capital calls",
        "PENDING_LITIGATION": "pending co-ownership proceedings and amounts involved",
        "AGM_MINUTES_3Y": "ordinary and extraordinary AGM minutes",
        "PERIODIC_CHARGES_2Y": "periodic charge statements",
        "LATEST_APPROVED_BALANCE_SHEET": "copy of the latest AGM-approved balance sheet",
    },
    "nl": {
        "WORKING_CAPITAL": "actueel bedrag van het werkkapitaal",
        "RESERVE_CAPITAL": "actueel bedrag van het reservekapitaal",
        "SELLER_ARREARS": "achterstallen van de verkoper voor de betrokken kavel",
        "RESERVE_CAPITAL_CALLS": "stand van de oproepen voor het reservekapitaal",
        "PENDING_LITIGATION": "hangende rechtszaken van de VME en de betrokken bedragen",
        "AGM_MINUTES_3Y": "notulen gewone en buitengewone AV",
        "PERIODIC_CHARGES_2Y": "periodieke afrekeningen",
        "LATEST_APPROVED_BALANCE_SHEET": "kopie van de laatste door de AV goedgekeurde balans",
    },
}


def generate_request(data: DraftCreate) -> tuple[list[str], str]:
    kinds = sorted(set(data.requested_document_types), key=lambda k: list(DocumentKind).index(k))
    extra = {
        "en": [
            "Article 3.94 syndic information",
            "ordinary AGM minutes",
            "extraordinary AGM minutes",
            "basis deed",
            "co-ownership regulations",
            "internal rules",
            "periodic charge statements",
            "latest approved balance sheet",
            "capital call",
            "reserve-capital statement",
            "other co-ownership document",
        ],
        "nl": [
            "syndicusinformatie artikel 3.94",
            "notulen gewone AV",
            "notulen buitengewone AV",
            "basisakte",
            "reglement van mede-eigendom",
            "reglement van interne orde",
            "periodieke afrekeningen",
            "laatste goedgekeurde balans",
            "kapitaaloproep",
            "reservekapitaalstaat",
            "ander mede-eigendomsdocument",
        ],
    }
    mapping = dict(zip(DocumentKind, LABELS[data.language] + extra[data.language], strict=True))
    labels = [mapping[kind] for kind in kinds]
    conjunction = " and " if data.language == "en" else " en "
    joined = labels[0] if len(labels) == 1 else ", ".join(labels[:-1]) + conjunction + labels[-1]
    text = (
        f"Could you please provide the {joined} for this property?"
        if data.language == "en"
        else f"Kunt u het volgende bezorgen voor dit pand: {joined}?"
    )
    return [kind.value for kind in kinds], text
