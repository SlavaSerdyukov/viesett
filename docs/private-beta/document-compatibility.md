# Document compatibility and local corpus evaluation

**Real corpus evaluation not performed.** No authorized real/anonymized corpus was supplied in this environment. The actual default evaluator returned `NO_CORPUS`, `documents=0`, `real_corpus_evaluation=NOT_PERFORMED`. Consequently real classification accuracy, extraction coverage and OCR frequency are **unknown**, not zero.

| Class | Observation |
| --- | --- |
| Synthetic verified | Existing bounded NL/FR M3/M4 fixtures; M6 aggregate evaluator and browser upload scenarios |
| Real authorized verified | No material available; not evaluated |
| OCR required | Synthetic short/unusable-layer fixture recognized; real frequency not measured |
| Unsupported layout | Explicit unknown/unsupported outcome; no broad table/prose capability claim |
| Partial extraction | Existing M4 parse states preserved and counted; no full-document understanding claim |

Keep documents and manifests under the gitignored `.local/evaluation-corpus/` (or another subdirectory of repository `.local/`). The evaluator has no account/database/provider client and never uploads files. It uses the existing bounded isolated PDF parser/classifier/extractors; transient page text is not written to reports/logs. Inputs must be entitled/authorized, locally vetted material as described in [the evaluation guide](evaluation-guide.md). This tool is not a replacement for production upload safety.

`manifest.json` example, containing only local opaque IDs and expected field **names**, never expected personal values:

```json
{
  "version": "corpus:1.0.0",
  "material": "AUTHORIZED_REAL",
  "evaluation_date": "2026-11-13",
  "documents": [{
    "document_id": "sample-001",
    "file": "sample-001.pdf",
    "expected_family": "EPC",
    "language": "nl",
    "expected_layout_class": "LABELED_TEXT",
    "expected_key_fields": ["document.epc.label", "document.epc.issue_date"]
  }]
}
```

Families use the supported AnalysisKind vocabulary. Layout expectation: LABELED_TEXT / SCAN / COMPLEX_TABLE / UNSUPPORTED. Language: nl / fr / unknown. Maximum 100 entries; bounded manifest/anchor/PDF sizes. Absolute paths, escapes and out-of-root symlinks are rejected. Do not put names, addresses, dispute details or free interview notes into metadata. Duplicate opaque IDs are rejected.

```sh
uv run python -m viesett.tools.evaluate_corpus
uv run python -m viesett.tools.evaluate_corpus --authorized
```

Real material requires explicit operator acknowledgement; this flag is not third-party consent or legal approval. An optional local `property_snapshot` JSON filename can reference a normalized PropertySnapshot for association and bounded M3 rule-impact counts. Without it, those results are NOT_EVALUATED. The anchor is not fetched or independently verified live. Full M4 cross-document impact must be evaluated inside the private dossier workflow; the offline report states that limit.

Output aggregates by family: document/classification/parsing counts, partial/unsupported/unparseable/OCR outcomes, expected/covered field counts, association counts, and available rule-code impact counts. Field **presence** coverage includes expected fields on failed/OCR inputs in its denominator; it does not certify extracted-value accuracy. Only co-ownership extraction supplies observed language; declared language/layout remain expectations. No per-file name/ID, source text, values or notes are serialized.

Synthetic harness regression: four inputs exercise EPC, an unusable layer, unknown layout and syndic data; OCR count 1/4 is a test result, **not an estimate for Belgian PDFs**. Decide any OCR milestone only after an authorized sample establishes its actual blocking frequency. No OCR SaaS, paid AI, corpus download or model training was added.
