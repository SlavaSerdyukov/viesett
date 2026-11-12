# Milestone 3 document intelligence

Local deterministic processing of four standardized Dutch-language Flemish document families. No LLM, OCR service, new external processor, questionnaire, final dossier UI or overall risk score. M2 official-source integration is unchanged. Root README is intentionally frozen during M3.

## API

All operations retain bearer authentication, workspace ownership, uniform foreign/absent 404 responses and private/no-store responses.

```text
POST /api/v1/workspaces/{workspace}/documents/{document}/analyze
GET  /api/v1/workspaces/{workspace}/documents/{document}/analysis?include_history=true
POST /api/v1/workspaces/{workspace}/due-diligence/refresh
GET  /api/v1/workspaces/{workspace}/document-requirements?evaluation_date=2026-11-12
```

POST analyze accepts `{ "evaluation_date": "2026-11-12" }`. Optional `manual_kind` is one of EPC, ASBESTOS_CERTIFICATE, ELECTRICAL_INSPECTION, SOIL_CERTIFICATE or UNKNOWN. This is an explicit correction, independent of the upload's type hint. Refresh accepts `{ "evaluation_date": "2026-11-12" }`. Both request bodies may be `{}`. Default evaluation date uses Europe/Brussels at the API/service boundary; pure rules receive a date explicitly. GET findings also accepts `evaluation_date` and refreshes an existing M3 evaluation. Historical findings remain visible with `resolved_at`; current findings have null `resolved_at`.

Analyze: owner/READY/active check → durable processing generation and object reservation → revalidate under workspace/account lock → isolated text extraction → classify → adapter → associate → private artifact and DOCUMENTED evidence → requirements/findings. Repeated unchanged successful requests return the same analysis/evaluation, without new artifacts/evidence/findings. Manual correction or a changed adapter version creates a new generation. Earlier automated predictions, decisions and observations remain in history. A new material rule input resolves previous managed findings and creates a traceable evaluation. M1 manual findings are untouched by refresh.

## Extraction and private artifacts

`document_safety` remains the first gate. QUARANTINED, REJECTED, DELETED and non-READY sources cannot enter analysis. A READY source may still be malformed, encrypted, unrelated or scanned. Safety and association/extraction states are separate.

`pypdf` runs in a disposable Python child with a fixed executable/module, a minimal environment, no shell, no network operations and stderr suppressed. Defaults: 10 MiB source limit inherited from uploads; 150 pages; 500,000 characters; 4 MiB decoded stream limit; 8-second parent wall timeout; 12-second child CPU cap and 768 MiB address-space cap where enforced by the OS. pypdf's public configuration also bounds decompression, declared and array streams and decoding work. These limits are practical containment, not a claim of a complete OS security sandbox. Unix is the supported runtime. Existing owner/workspace locks serialize analysis for one account; a shared multi-worker parser queue is deferred.

NFC and newline normalization preserve a separate text value for each one-based page. Minimal/no text or a page with only a tiny header is OCR_REQUIRED. Mixed scans are conservatively rejected as incomplete text extraction. Blank/sparse pages may therefore require review/OCR. No optical recognition is performed. Encrypted, malformed, oversized and timed-out files have safe typed codes; original safety status and source bytes remain. Timeout/storage failures are retryable; an unchanged encrypted/oversized/scanned document requires a suitable new source or future OCR, not blind automatic retry.

`DocumentAnalysis` records generations/status, prediction/manual/effective kind, association at processing time, normalized fields, evidence IDs and versions. Complete text is never a relational domain field. `DocumentTextArtifact` records parser/version, page count/hash and a private opaque object key. Artifact content is page-structured JSON in the existing private storage (0700 directory, 0600 files); no key/path or full-text field appears in ordinary API/export DTOs. Source PDFs remain downloadable through the existing authorized attachment endpoint. A dedicated derived-text download API is deferred.

The artifact key is reserved on the analysis before bytes can be written. This also makes partial writes/crashes discoverable by source deletion. The existing durable outbox schedules cleanup; deleting a source/workspace/account queues successful and reserved derived keys, advances their cleanup lease and verifies physical deletion. Storage failures produce 503 pending cleanup. Source deletion removes its analyses/evidence, dependent findings and workspace evaluation input snapshots, rather than retaining extracted private facts in a historical result. Schema downgrade refuses nonempty M3 state to avoid orphaned private artifacts or incompatible evidence.

## Evidence, association and currentness

Removing one source resolves current managed rule findings that may depend on it indirectly. Findings/requirements reads recompute from remaining sources even after old input snapshots were erased. Manual M1 findings keep their original lifecycle. This prevents an unsupported shared conclusion surviving as current.

Fields use `document.epc.*`, `document.asbestos.*`, `document.electrical.*`, `document.soil.*`. Values are DOCUMENTED/DOCUMENT, with document UUID, one-based page, half-open offsets into that page's normalized text, confidence and adapter version. EPC labels use `TypedValue(kind="epc_label")`, validated against A+, A, B, C, D, E, F. Parser confidence never raises authority. A PostgreSQL constraint prevents extractor-tagged rows becoming OFFICIAL or losing source/page/parser provenance. Reprocessing expires previous current document observations and links successors; unchanged retries do not reprocess.

Association compares normalized full street, house number, postal code and box, or exact CaPaKeys. No arbitrary substrings, edit-distance guessing or filename identity. Missing private-unit precision is POSSIBLE_MATCH; conflicting supplied box/parcel/address is MISMATCH. An exact parcel cannot erase a conflicting unit/address. Multiple parcels stay separate; a matching subset does not demonstrate full soil-certificate coverage. Current official identity must be selected and non-stale. MATCHED is an identifier comparison, not signature, authenticity, ownership or legal-validity verification.

MISMATCH, POSSIBLE_MATCH and UNVERIFIED document facts remain in document-level evidence and export, but are excluded from substantive property rules. Association review findings remain visible. Rule refresh recomputes association from stored fields against the current M2 snapshot; the original analysis records its historical identity revision. Requirements and findings reads cannot silently retain an old property's substantive result after an identity/safety/evidence change.

Only explicit current OFFICIAL facts or DOCUMENTED facts from current matched READY documents can supply additional rule predicates. INFERRED/manual guesses are excluded. Deed-date predicates must be date-typed. Current source evidence and normalized evaluation inputs, rule metadata, date and input hash make findings reproducible. An official identity does not establish residential use, construction year, qualifying transfer or deed date; these often correctly remain unknown in M3.
