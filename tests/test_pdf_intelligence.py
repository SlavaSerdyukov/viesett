import logging
from dataclasses import replace

import pytest

from tests.document_fixtures import ASBESTOS, ELECTRICAL, EPC, SAMPLES, SOIL, text_pdf
from viesett.document_intelligence.classification import classify
from viesett.document_intelligence.extractors import extract_fields, parse_date
from viesett.document_intelligence.pdf import (
    ExtractionFailure,
    PdfLimits,
    extract_isolated,
    extract_text,
)
from viesett.domain.intelligence import AnalysisKind, PageText, TextPage
from viesett.domain.schemas import TypedValue

LIMITS = PdfLimits(128 * 1024, 10, 20_000, 1024 * 1024)


def pages(text: str) -> PageText:
    return PageText(pages=[TextPage(number=1, text=text)])


def test_text_and_page_boundaries_are_preserved_without_logging(
    caplog: pytest.LogCaptureFixture,
) -> None:
    secret = "PRIVATE_SYNTHETIC_TEXT_DO_NOT_LOG"
    with caplog.at_level(logging.DEBUG):
        parsed = extract_text(text_pdf(EPC, secret * 3), LIMITS)
    assert [p.number for p in parsed.pages] == [1, 2]
    assert "EPC-label: E" in parsed.pages[0].text and secret in parsed.pages[1].text
    assert secret not in caplog.text


@pytest.mark.parametrize(
    "case,code",
    [
        ("malformed", "malformed_pdf"),
        ("pages", "pdf_page_limit"),
        ("characters", "pdf_text_limit"),
        ("input", "pdf_input_limit"),
        ("stream", "pdf_stream_limit"),
        ("scan", "ocr_required"),
        ("encrypted", "encrypted_pdf"),
        ("mixed_scan", "ocr_required"),
    ],
)
def test_pdf_bounds_and_unusable_layers(case: str, code: str) -> None:
    content = text_pdf(EPC)
    limits = LIMITS
    if case == "malformed":
        content = b"%PDF-1.7\nnot a PDF\n%%EOF"
    elif case == "pages":
        limits = replace(limits, max_pages=1)
        content = text_pdf(EPC, EPC)
    elif case == "characters":
        limits = replace(limits, max_characters=20)
    elif case == "input":
        limits = replace(limits, max_bytes=20)
    elif case == "stream":
        limits = replace(limits, max_stream_bytes=1024)
        content = text_pdf("Z" * 10_000, compress=True)
    elif case == "scan":
        content = text_pdf("")
    elif case == "mixed_scan":
        content = text_pdf(EPC, "scan header")
    else:
        content = text_pdf(EPC, encrypted=True)
    with pytest.raises(ExtractionFailure, match=code):
        extract_text(content, limits)


async def test_isolated_worker_has_bounded_failure_and_success() -> None:
    result = await extract_isolated(text_pdf(EPC), LIMITS)
    assert "EPC-label" in result.pages[0].text
    with pytest.raises(ExtractionFailure, match="malformed_pdf"):
        await extract_isolated(b"bad PDF private bytes", LIMITS)
    with pytest.raises(ExtractionFailure, match="parser_timeout"):
        await extract_isolated(text_pdf(EPC), replace(LIMITS, timeout=0.0001))


@pytest.mark.parametrize("kind", list(SAMPLES))
def test_each_family_classifies_and_has_page_backed_fields(kind: AnalysisKind) -> None:
    text = SAMPLES[kind]
    classification = classify(pages(text))
    assert classification.predicted_kind == kind and classification.confidence == 1
    fields = extract_fields(pages(text), kind)
    assert fields and all(f.page == 1 and 0 <= f.start < f.end <= len(text) for f in fields)
    assert all(text[f.start : f.end].strip() for f in fields)


@pytest.mark.parametrize(
    "text",
    [
        "Energieprestatiecertificaat",
        "OVAM",
        "EPC-label: E",
        EPC + SOIL,
        "A property brochure mentioning asbestos and electricity",
        "Bodemattest\nKorte notitie",
    ],
)
def test_weak_or_mixed_classification_is_unknown(text: str) -> None:
    assert classify(pages(text)).predicted_kind == AnalysisKind.UNKNOWN


def test_epc_label_domain_and_invalid_values_are_conservative() -> None:
    for label in ("A+", "A", "B", "C", "D", "E", "F"):
        assert TypedValue(kind="epc_label", value=label).value == label
    with pytest.raises(ValueError):
        TypedValue(kind="epc_label", value="G")
    for label in ("G", "EF", "E (estimated)", ""):
        fields = extract_fields(
            pages(EPC.replace("EPC-label: E", "EPC-label: " + label)), AnalysisKind.EPC
        )
        assert not any(f.key.endswith(".label") for f in fields)
    conflict = extract_fields(pages(EPC + "EPC-label: F\n"), AnalysisKind.EPC)
    assert not any(f.key.endswith(".label") for f in conflict)
    assert extract_fields(pages(EPC), AnalysisKind.UNKNOWN) == []
    values = {f.key: f.value for f in extract_fields(pages(EPC), AnalysisKind.EPC)}
    assert values["document.epc.energy_score"] == 450
    assert values["document.epc.issue_date"] == "2026-01-12"


@pytest.mark.parametrize("date_text", ["31/02/2026", "2026-99-12", "yesterday"])
def test_invalid_dates_are_not_massaged(date_text: str) -> None:
    assert parse_date(date_text) is None


def test_soil_parcels_gir_risk_and_electrical_negation_remain_exact() -> None:
    soil = extract_fields(pages(SOIL), AnalysisKind.SOIL_CERTIFICATE)
    assert len([f for f in soil if f.key.endswith(".parcel.capakey")]) == 2
    assert next(f.value for f in soil if f.key.endswith(".gir_recorded")) is False
    assert not any("clean" in str(f.value) for f in soil)
    risk = SOIL.replace(
        "OVAM heeft geen aanwijzingen dat deze grond een risicogrond is.",
        "Deze grond is een risicogrond.",
    )
    assert (
        next(
            f.value
            for f in extract_fields(pages(risk), AnalysisKind.SOIL_CERTIFICATE)
            if f.key.endswith(".risk_ground")
        )
        is True
    )
    for conclusion, expected in [("conform", True), ("niet-conform", False)]:
        fields = extract_fields(
            pages(ELECTRICAL.replace("niet-conform", conclusion)),
            AnalysisKind.ELECTRICAL_INSPECTION,
        )
        assert next(f.value for f in fields if f.key.endswith(".conforming")) is expected
    for variant in ("gemene delen", "gemeenschappelijk gebruikte delen"):
        fields = extract_fields(
            pages(ASBESTOS.replace("privatieve delen", variant)), AnalysisKind.ASBESTOS_CERTIFICATE
        )
        assert next(f.value for f in fields if f.key.endswith(".variant")) != "PRIVATE_UNIT"


@pytest.mark.parametrize("unit", ["kWh/m²jaar", "kWh/(m².jaar)", "kWh/(m2 jaar)"])
def test_negative_energy_score_is_preserved_without_inventing_epc_label(unit: str) -> None:
    text = EPC.replace("EPC-label: E\n", "").replace("450 kWh/m²jaar", "-25,5 " + unit)
    fields = extract_fields(pages(text), AnalysisKind.EPC)
    assert next(f.value for f in fields if f.key.endswith(".energy_score")) == -25.5
    assert not any(f.key.endswith(".label") for f in fields)
