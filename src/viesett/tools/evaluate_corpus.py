"""Local-only bounded extraction evaluation; reports contain counters, not content."""

import argparse
import asyncio
import json
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Literal
from uuid import NAMESPACE_URL, uuid5

from pydantic import Field, JsonValue

from viesett.coownership.extraction import extract_co
from viesett.core.config import PROJECT_ROOT
from viesett.document_intelligence.association import associate
from viesett.document_intelligence.classification import classify
from viesett.document_intelligence.extractors import extract_fields
from viesett.document_intelligence.pdf import ExtractionFailure, PdfLimits, extract_isolated
from viesett.domain.base import Schema
from viesett.domain.coownership import CO_KINDS
from viesett.domain.intelligence import AnalysisKind, AssociationStatus, ExtractionStatus
from viesett.domain.property import PropertySnapshot
from viesett.rules.engine import DocumentInput, Fact, RuleContext, evaluate


class CorpusEntry(Schema):
    document_id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,60}$")
    file: str = Field(max_length=240)
    expected_family: AnalysisKind
    language: Literal["nl", "fr", "unknown"]
    expected_layout_class: Literal["LABELED_TEXT", "SCAN", "COMPLEX_TABLE", "UNSUPPORTED"]
    expected_key_fields: list[str] = Field(default_factory=list, max_length=100)


class CorpusManifest(Schema):
    version: Literal["corpus:1.0.0"] = "corpus:1.0.0"
    material: Literal["SYNTHETIC", "AUTHORIZED_REAL"]
    evaluation_date: date
    property_snapshot: str | None = None
    documents: list[CorpusEntry] = Field(max_length=100)


def local_file(root: Path, name: str, suffix: str) -> Path:
    path = (root / name).resolve()
    if (
        Path(name).is_absolute()
        or not path.is_relative_to(root.resolve())
        or path.suffix.lower() != suffix
    ):
        raise ValueError("Invalid corpus input")
    return path


def read_bounded(path: Path, maximum: int) -> bytes:
    with path.open("rb") as stream:
        content = stream.read(maximum + 1)
    if len(content) > maximum:
        raise ValueError("Corpus input exceeds limit")
    return content


async def evaluate_corpus(root: Path, *, authorized: bool = False) -> dict[str, JsonValue]:
    root = await asyncio.to_thread(root.resolve)
    local_root = await asyncio.to_thread((PROJECT_ROOT / ".local").resolve)
    if not root.is_relative_to(local_root):
        raise ValueError("Corpus must remain under the private project-local directory")
    manifest_path = root / "manifest.json"
    try:
        raw_manifest = await asyncio.to_thread(read_bounded, manifest_path, 256 * 1024)
    except FileNotFoundError:
        return {"status": "NO_CORPUS", "real_corpus_evaluation": "NOT_PERFORMED", "documents": 0}
    manifest = CorpusManifest.model_validate_json(raw_manifest)
    if manifest.material == "AUTHORIZED_REAL" and not authorized:
        raise ValueError("Authorized material requires explicit operator acknowledgement")
    if len({d.document_id for d in manifest.documents}) != len(manifest.documents):
        raise ValueError("Duplicate corpus identifiers")
    anchor = None
    if manifest.property_snapshot:
        path = local_file(root, manifest.property_snapshot, ".json")
        anchor = PropertySnapshot.model_validate_json(
            await asyncio.to_thread(read_bounded, path, 1024 * 1024)
        )
    limits = PdfLimits(10 * 1024 * 1024, 150, 500_000, 4 * 1024 * 1024)
    # No runtime provider/account/database is constructed. Text remains transient
    # inside the existing isolated parser and this process, never in a report.
    groups: dict[str, Counter[str]] = {}
    rule_counts: Counter[str] = Counter()
    inputs: list[DocumentInput] = []
    attempted = 0
    for entry in manifest.documents:
        counts = groups.setdefault(entry.expected_family.value, Counter())
        counts["documents"] += 1
        counts["expected_layout_" + entry.expected_layout_class] += 1
        counts["expected_fields"] += len(set(entry.expected_key_fields))
        path = local_file(root, entry.file, ".pdf")
        try:
            content = await asyncio.to_thread(read_bounded, path, limits.max_bytes)
        except (OSError, ValueError):
            counts["input_unavailable"] += 1
            continue
        try:
            attempted += 1
            pages = await extract_isolated(content, limits)
            prediction = classify(pages)
            kind = prediction.predicted_kind
            counts["classification_success"] += kind == entry.expected_family
            status = "PARSED"
            if kind in CO_KINDS:
                fields, metadata = extract_co(pages, kind)
                status = metadata.parse_status
                counts["observed_language_" + metadata.detected_language] += 1
            else:
                fields = extract_fields(pages, kind)
                if not fields:
                    status = "UNSUPPORTED_LAYOUT" if kind == AnalysisKind.UNKNOWN else "UNPARSEABLE"
            found = {f.key for f in fields}
            counts["covered_fields"] += len(found & set(entry.expected_key_fields))
            counts["parsing_success"] += status == "PARSED" and bool(fields)
            counts["partial_extraction"] += status == "PARTIALLY_PARSED"
            counts["unsupported_layout"] += status == "UNSUPPORTED_LAYOUT"
            counts["unparseable"] += status == "UNPARSEABLE"
            association = associate(fields, anchor).status if anchor else None
            counts["association_" + (association.value if association else "NOT_EVALUATED")] += 1
            if anchor and kind not in CO_KINDS:
                grouped: dict[str, list[Fact]] = {}
                for field in fields:
                    grouped.setdefault(field.key.split(".", 2)[2], []).append(Fact(field.value, ()))
                inputs.append(
                    DocumentInput(
                        uuid5(NAMESPACE_URL, "private-corpus:" + entry.document_id),
                        kind,
                        ExtractionStatus.READY,
                        association or AssociationStatus.UNVERIFIED,
                        {k: tuple(v) for k, v in grouped.items()},
                    )
                )
        except ExtractionFailure as failure:
            counts["OCR_REQUIRED" if failure.code == "ocr_required" else "parsing_failed"] += 1
    if anchor:
        parcels = frozenset(p.capakey for p in anchor.parcels) if not anchor.stale else frozenset()
        baseline = {
            f.code for f in evaluate(RuleContext(manifest.evaluation_date, (), parcels)).findings
        }
        for finding in evaluate(
            RuleContext(manifest.evaluation_date, tuple(inputs), parcels)
        ).findings:
            if finding.code not in baseline:
                rule_counts[finding.code] += 1
    total = sum(g["documents"] for g in groups.values())
    ocr = sum(g["OCR_REQUIRED"] for g in groups.values())
    report_groups: dict[str, JsonValue] = {}
    for family, counters in groups.items():
        values: dict[str, JsonValue] = {key: value for key, value in counters.items()}
        denominator = counters["expected_fields"]
        values["field_presence_coverage"] = (
            counters["covered_fields"] / denominator if denominator else None
        )
        report_groups[family] = values
    return {
        "status": "EVALUATED",
        "material": manifest.material,
        "real_corpus_evaluation": "PERFORMED"
        if manifest.material == "AUTHORIZED_REAL" and attempted > 0
        else "NOT_PERFORMED",
        "documents": total,
        "evaluated_documents": attempted,
        "OCR_REQUIRED": ocr,
        "ocr_frequency": ocr / total if total else None,
        "families": report_groups,
        "rule_impact": {key: value for key, value in sorted(rule_counts.items())}
        if anchor
        else "NOT_EVALUATED",
        "rule_impact_scope": (
            "Existing M3 rules only; M4 cross-document impact requires a private dossier evaluation"
        ),
        "evaluation_date": manifest.evaluation_date.isoformat(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT / ".local/evaluation-corpus")
    parser.add_argument("--authorized", action="store_true")
    args = parser.parse_args()
    try:
        result = asyncio.run(evaluate_corpus(args.root, authorized=args.authorized))
        print(json.dumps(result, sort_keys=True))
    except Exception:
        # Validation/parser/filesystem errors may contain filenames or content.
        print(json.dumps({"status": "INVALID_OR_UNAVAILABLE_LOCAL_CORPUS"}))
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
