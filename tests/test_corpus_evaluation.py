import json
from pathlib import Path

import pytest

from viesett.demo_documents import EPC, SYNDIC_NL, text_pdf
from viesett.tools.evaluate_corpus import evaluate_corpus


def manifest(root: Path, files: list[dict[str, object]]) -> None:
    (root / "manifest.json").write_text(
        json.dumps({"material": "SYNTHETIC", "evaluation_date": "2026-11-12", "documents": files})
    )


def entry(identifier: str, filename: str, family: str = "EPC") -> dict[str, object]:
    return {
        "document_id": identifier,
        "file": filename,
        "expected_family": family,
        "language": "nl",
        "expected_layout_class": "LABELED_TEXT",
        "expected_key_fields": ["document.epc.label", "document.epc.address"],
    }


async def test_absent_real_corpus_is_reported_honestly(tmp_path: Path) -> None:
    assert await evaluate_corpus(tmp_path) == {
        "status": "NO_CORPUS",
        "real_corpus_evaluation": "NOT_PERFORMED",
        "documents": 0,
    }


async def test_synthetic_evaluation_is_aggregate_only_and_measures_ocr(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    (tmp_path / "private-person-name.pdf").write_bytes(
        text_pdf(EPC + "\nPRIVATE_PERSONAL_SENTINEL\n")
    )
    (tmp_path / "scan.pdf").write_bytes(text_pdf("x"))
    (tmp_path / "unsupported.pdf").write_bytes(
        text_pdf(
            "Unrelated correspondence with enough text but no supported "
            "document headings or labeled fields."
        )
    )
    (tmp_path / "syndic.pdf").write_bytes(text_pdf(SYNDIC_NL))
    manifest(
        tmp_path,
        [
            entry("opaque1", "private-person-name.pdf"),
            entry("opaque2", "scan.pdf"),
            entry("opaque3", "unsupported.pdf"),
            entry("opaque4", "syndic.pdf", "SYNDIC_INFORMATION"),
        ],
    )
    result = await evaluate_corpus(tmp_path)
    assert (
        result["documents"] == 4 and result["OCR_REQUIRED"] == 1 and result["ocr_frequency"] == 0.25
    )
    assert result["real_corpus_evaluation"] == "NOT_PERFORMED"
    serialized = json.dumps(result)
    assert "PRIVATE_PERSONAL_SENTINEL" not in serialized + caplog.text
    assert "private-person-name" not in serialized and "opaque1" not in serialized
    assert result["rule_impact"] == "NOT_EVALUATED"
    families = result["families"]
    assert isinstance(families, dict)
    epc = families["EPC"]
    assert isinstance(epc, dict) and epc["classification_success"] == 1


@pytest.mark.parametrize("filename", ["../outside.pdf", "/private/tmp/source.pdf", "input.txt"])
async def test_corpus_cannot_escape_private_root(tmp_path: Path, filename: str) -> None:
    manifest(tmp_path, [entry("opaque1", filename)])
    with pytest.raises(ValueError):
        await evaluate_corpus(tmp_path)


async def test_authorized_real_requires_explicit_operator_acknowledgement(tmp_path: Path) -> None:
    manifest(tmp_path, [])
    p = tmp_path / "manifest.json"
    data = json.loads(p.read_text())
    data["material"] = "AUTHORIZED_REAL"
    p.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        await evaluate_corpus(tmp_path)


async def test_symlink_outside_root_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "source.pdf").symlink_to(tmp_path.parent / "elsewhere.pdf")
    manifest(tmp_path, [entry("opaque1", "source.pdf")])
    with pytest.raises(ValueError):
        await evaluate_corpus(tmp_path)
