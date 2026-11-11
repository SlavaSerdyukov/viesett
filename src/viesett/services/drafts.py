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


def generate_request(data: DraftCreate) -> tuple[list[str], str]:
    kinds = sorted(set(data.requested_document_types), key=lambda k: list(DocumentKind).index(k))
    mapping = dict(zip(DocumentKind, LABELS[data.language], strict=True))
    labels = [mapping[kind] for kind in kinds]
    conjunction = " and " if data.language == "en" else " en "
    joined = labels[0] if len(labels) == 1 else ", ".join(labels[:-1]) + conjunction + labels[-1]
    text = (
        f"Could you please provide the {joined} for this property?"
        if data.language == "en"
        else f"Kunt u het volgende bezorgen voor dit pand: {joined}?"
    )
    return [kind.value for kind in kinds], text
