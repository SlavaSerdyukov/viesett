import pytest

from tests.coownership_fixtures import AGM_NL, IDENTITY_NL, SAMPLES, SYNDIC_NL
from tests.test_pdf_intelligence import pages
from viesett.coownership.extraction import amount, enterprise, extract_co
from viesett.document_intelligence.classification import classify
from viesett.domain.intelligence import AnalysisKind


@pytest.mark.parametrize("kind", list(SAMPLES))
@pytest.mark.parametrize("language,index", [("nl", 0), ("fr", 1)])
def test_supported_nl_fr_families_classify_and_have_citations(
    kind: AnalysisKind, language: str, index: int
) -> None:
    text = SAMPLES[kind][index]
    assert classify(pages(text)).predicted_kind == kind
    fields, metadata = extract_co(pages(text), kind)
    assert metadata.detected_language == language and metadata.confidence > 0
    assert fields and all(0 <= f.start < f.end <= len(text) for f in fields)
    assert all(text[f.start : f.end].strip() for f in fields)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("EUR 1.234,56", "1234.56"),
        ("€ 0,00", "0.00"),
        ("120000 EUR", "120000.00"),
        ("GBP 1234.56", "1234.56"),
        ("EUR -25,00", "-25.00"),
    ],
)
def test_money_preserves_exact_cents(raw: str, expected: str) -> None:
    parsed = amount(raw)
    assert parsed is not None and parsed[0] == expected


@pytest.mark.parametrize(
    "raw", ["123,45", "EUR 1.23,45", "EUR NaN", "EUR 12.345", "EUR 1,2", "EUR 999999999999999"]
)
def test_money_does_not_guess_currency_or_massaged_amounts(raw: str) -> None:
    assert amount(raw) is None


def test_unknown_and_mixed_packets_remain_unknown() -> None:
    assert classify(pages("Notulen gewone algemene vergadering")).predicted_kind == "UNKNOWN"
    assert classify(pages(AGM_NL + "Basisakte\n")).predicted_kind == "UNKNOWN"


def test_no_personal_attendance_contacts_or_banking_domain_fields() -> None:
    sensitive = (
        "\nAanwezigen: Jan Geheim, Marie Prive\nE-mail: prive@exam"
        "ple.test\nAdres: Privaatstraat 99\nIBAN: BE00 1234 1234 1"
        "234\nSyndicus: Jan Geheim\n"
    )
    fields, _ = extract_co(pages(SYNDIC_NL + sensitive), AnalysisKind.SYNDIC_INFORMATION)
    values = " ".join(str(f.value) for f in fields)
    assert not any(
        value in values
        for value in ("Jan Geheim", "Marie Prive", "prive@example", "Privaatstraat", "BE00")
    )
    assert next(f.value for f in fields if f.key.endswith(".seller_arrears")) == "0.00"
    absent, _ = extract_co(
        pages("Syndicusinformatie\n" + IDENTITY_NL), AnalysisKind.SYNDIC_INFORMATION
    )
    assert not any(f.key.endswith("seller_arrears") for f in absent)
    assert enterprise("0000.000.196") == "0000000196"
    assert enterprise("0000000195") is None
