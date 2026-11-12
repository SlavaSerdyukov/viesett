# Co-ownership intelligence — M4

Version 0.4.0, reviewed 2026-11-12. Backend only. This layer assists review of a Belgian apartment dossier; it does not audit accounts, certify decisions, decide payment responsibility or rank a purchase. M1–M3 authentication, READY-file safety, private storage, official identity and evidence authority remain prerequisites.

## Processing and association

Existing analysis endpoints run bounded isolated PDF text extraction, conservative classification, then the `co-ownership:1.0.0` adapter. Eleven explicit document families are supported in labeled Dutch/French layouts. `signals:2.0.0` considers document headings and supporting terms, never filenames. Competing recognized headings remain UNKNOWN; manual correction preserves the automated prediction. Earlier classifier versions can be reprocessed on request.

The adapter emits typed fields with document/page/character spans, exact monetary strings, currency, date, context and group. Language metadata records `co-language:1.0.0`, a conservative nl/fr/unknown result and heuristic confidence; this is not a calibrated accuracy measure. PARSED means supported useful fields were recovered, not that every clause was understood. PARTIALLY_PARSED, UNSUPPORTED_LAYOUT and UNPARSEABLE remain explicit; image-only PDFs retain M3 OCR_REQUIRED and do not invent facts.

The cross-document engine receives normalized evidence, not PDFs or page text. Exact street/house/postcode components establish building association against the current official property. An explicit conflicting box excludes a document. One matched enterprise-number anchor can strengthen an addressless organizational document; it cannot override another building, a future document date or stale official identity. Enterprise numbers are checksum-validated, not live KBO-verified. Association has MATCHED, POSSIBLE_MATCH, MISMATCH and UNVERIFIED states. Building association does not prove ownership of a private lot. The analysis DTO retains M3 association semantics; the co-ownership snapshot separately reports building/entity association and its scope. A unique matched basis-deed lot anchors private allocation; where the official address has a box, an explicit matching box is also required; seller arrears may be represented as an explicitly documented lot observation without a basis deed. Other-lot arrears/allocations are excluded when the purchased lot is established.

Identity holds VME/ACP name and optional enterprise number, building address, corporate syndic identity, documented lot designation, attached lots and rational shares. An enterprise conflict produces review and blocks current fund selection and exposure; source observations retain provenance. General common-parts ownership is distinct from an applicable expense key.

## Persistence and lifecycle

The additive revision `d64802d3610f` follows `192e0442ffc8`. It adds nullable analysis metadata, extends frozen enum CHECK vocabularies and creates three tables:

| Table | Purpose |
| --- | --- |
| `co_ownership_evaluations` | Immutable dated result and minimized normalized inputs; meetings, decisions, calls, estimates, checks and questions are typed snapshot structures |
| `co_ownership_identities` | Current queryable entity/lot/share projection, linked to its evaluation |
| `planned_works` | Queryable work candidates with successor/supersession history |

Compound evaluation/workspace foreign keys prevent cross-workspace references. Private text is not an evaluation input. Existing DOCUMENTED evidence remains document-derived; calculation results are INFERRED and never become OFFICIAL property facts.

Analysis and source deletion trigger recomputation when a co-ownership dossier exists. GET snapshot/findings/questions and explicit refresh also recompute against current official identity and normalized observations. M2 identity changes are consumed on the next dossier/read refresh. Workspace locking serializes evaluation mutations. Hashes include source observations, association inputs, date, catalog, evaluation/calculation/question versions. An unchanged current input reuses its evaluation; changed inputs preserve history and replace current identity/work projections and managed findings. Newer dated fund observations coexist with older observations; incomparable dates are not contradictions. Same-context conflicting latest values yield no arbitrary current amount.

Meetings reconcile by entity, normalized building address, date and type. Exact decisions merge with their citations. Project reference plus category permits reconciliation; ambiguous same-date decisions remain distinct candidates. Identical-content copies without a project reference deduplicate by meeting/content/group. A later explicit decision updates current work status while prior meetings/evaluations remain. Calls are separate structures linked through explicit project references; a linked call is not a second work. No free semantic merge exists.

Source deletion erases affected evaluation inputs/results and derived objects, resolves dependent findings, invalidates requests and recomputes from remaining sources. Workspace/account deletion cascades. Export includes caller-owned current and historical typed snapshots without storage keys or raw text. Migration downgrade refuses remaining M4 evaluations, kinds, extractor evidence or findings; authenticated deletion must clean private dependencies first.

## Minimal API

All endpoints require the existing authenticated owner; other owners and missing workspaces return the same 404.

| Method | Path below `/api/v1/workspaces/{workspace_id}` |
| --- | --- |
| POST | `/co-ownership/refresh` with optional `evaluation_date` |
| GET | `/co-ownership` with optional `evaluation_date` |
| GET | `/cross-document-findings` |
| GET | `/buyer-questions` |

Existing document-analysis, findings, export, deletion and copyable request APIs are extended. Requests support existing en/nl output and include missing component/period labels. No sending fields or communication integration exists.

## Minimisation and limits

No attendance-list, personal-contact, signature, individual bank-account or personal-party profile is extracted. Litigation retains a controlled property category, explicit pending status, amount and citations. A generic dispute mention alone leaves status uncertain; closed cases are not promoted to pending litigation. Decisions expose normalized category/status text rather than arbitrary personal prose. Organization identity requires an explicit entity label; corporate syndic names require a supported legal-form marker.

For recognized M4 kinds, the private derived artifact uses `co-ownership-facts:1.0.0`: normalized fields, locators, parser version and page count, without full page text. Character spans refer to the original isolated PDF parse; review uses the private source. M3 and UNKNOWN artifact formats/history remain unchanged and may contain incidental personal text. Original PDFs remain private and retain their existing source-deletion criterion. No raw text, artifact keys or excerpts are returned by M4 APIs or routine logs.

Supported labels and fictional examples are inspectable in `coownership/extraction.py` and `tests/coownership_fixtures.py`. Arbitrary column tables, free-form minutes, scanned documents, signatures, general deed interpretation, complex exclusive-use rights and contractor identification are unsupported. No live customer corpus, OCR, AI provider or semantic merger was used. Partial layouts require source review and explicit missing data, not optimistic completion.
