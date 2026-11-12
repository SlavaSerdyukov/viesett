# Buyer product architecture — Milestone 5

Viesett 0.5.0 composes the M1–M4 capabilities into a private buyer dossier. It assists review before a binding offer; there is no buy/no-buy decision, overall risk score, legal approval or new Belgian rule. Frontend: `web/`, React + TypeScript + Vite, React Router, TanStack Query, native fetch and local CSS. FastAPI remains the only application server. No BFF, GraphQL, Node server tier, UI framework, analytics, mailbox, OCR provider or live AI was added.

## Journey and API

| Surface | Authentication | Behavior |
| --- | --- | --- |
| `GET /api/v1/web-config` | Public | Small feature/size flags; no credentials or private state |
| `POST /api/v1/property-preview` | Public | Existing bounded official resolver; no account/workspace/history persistence |
| `POST /api/v1/development/session` | Opt-in local development | Random one-hour existing bearer credential, loopback peer and explicit allowed Origin, five bootstrap requests/minute |
| `POST /api/v1/dossiers` | Existing bearer | Creates a private workspace and independently revalidates supplied official choices |
| `GET /api/v1/workspaces/{id}/dossier` | Owner | Current typed product projection |
| `POST /api/v1/workspaces/{id}/document-intake` | Owner + existing upload attestation | Existing safety upload, then automatic analysis only for READY PDFs, then refreshed projection |
| `POST /api/v1/workspaces/{id}/refresh` | Owner | Deterministic requirements/co-ownership refresh; optional public heritage/manual-flood refresh |
| `POST /api/v1/development/demo-dossier` | Owner, demo instance only | Real deterministic pipelines with fictional property/documents and a persistent demo marker |

Existing resolution, classification correction, retry, private download, copyable requests, export and deletion endpoints remain authoritative. An unresolved property can be checked/selected again within its existing dossier through preview plus the existing private resolution endpoint. Refresh does not destructively reprocess every PDF or fabricate a flood score. Preview postpones heritage; an unqueried source is not reported as a negative match.

Preview returns RESOLVED, NEEDS_SELECTION, NOT_FOUND or UPSTREAM_UNAVAILABLE with a small official-data projection, choices, attribution and manual flood references. It uses existing provider host/path/timeout/retry/rate controls. It neither accepts private workspace fields nor calls private evidence/documents. Its separate per-network-peer limiter defaults to **5/minute**, bounded to 1,000 ephemeral hashed keys; forwarded headers are not read by route logic. Deployment must control trusted proxy configuration and use a shared limiter before multiple workers/public scale. Source failure does not mark the input address invalid.

No preview-result cache or persistent anonymous token is introduced. Creating a private dossier deliberately performs independent official relationship validation rather than trusting client-returned IDs. This costs a second lookup; secure signed/cached reuse is deferred. Unit labels use actual official box/address information where available. When unit-level box labels are missing, the UI identifies the limitation and does not invent a bus mapping.

## Projection and consistency

`domain/product.py` defines explicit response DTOs: dossier, property, document, finding, question, citation, evidence, co-ownership summary and completeness. This is a read model with `buyer-dossier:1.0.0`, not a new authority source. Official/DOCUMENTED/INFERRED states remain those of existing evidence; calculations remain inferred and responsibility undetermined.

The service coordinates idempotent M3/M4 evaluations. It takes a workspace-locked source signature before evaluation and checks it again under the final read lock, including current documents, latest analyses, current evidence, property resolution and source-run generation. A change retries up to three times, then returns a safe conflict instead of mixing generations. Property associations are recalculated against the current identity, not copied from a stale analysis. Analysis completion and source-attempt times contribute to `last_updated`.

Only current findings and current evidence are projected. Limits: 100 document rows, 200 current findings, 500 evidence facts, 100 per co-ownership list; truncation is explicit. Additional normalized citation metadata is fetched for visible claims whose inputs fall outside the evidence page (bounded at 5,000 extra references). No PDF bytes, page text, storage keys, source payload archive, evaluation inputs/hashes or full evaluation history is returned. Co-ownership summary omits histories and duplicate internal finding/question representations. Existing authenticated detail/export APIs retain historical information.

A fresh synthetic sample with five documents and 103 facts produced approximately **86 KB** of uncompressed JSON. This is a local sample measurement, not a performance SLA. No PDF is loaded at workspace startup. The create/intake responses populate the query cache directly; other mutations invalidate only the relevant dossier query. Polling is limited to recent active processing and stops at terminal states/two-minute age bound.

## Access and private documents

The browser uses Authorization headers and keeps credentials and query state in page memory. No bearer token is written to localStorage/sessionStorage, cookies, URLs or analytics. Connecting removes cached private queries; disconnect clears memory/cache. Reloading loses the in-page token. Existing-token entry supports operator-provisioned evaluation credentials; the optional local bootstrap is disabled by default and forbidden in production. It does not provide public signup, recovery, verification or final browser authentication architecture.

CORS uses explicit configured origins, never a wildcard, and does not enable cookie credentials. Cookie-authenticated mutations were not introduced; therefore this bridge does not depend on a new cookie/CSRF scheme. Any future cookie session requires CSRF design. API/private-download responses retain private/no-store and no-content logging. Frontend errors use controlled messages and discard provider/backend bodies. No external telemetry or replay is installed.

Document citations fetch the existing authorized content endpoint into a temporary local Blob URL. Only the selected document is fetched. Abort/revoke cleanup runs when the viewer closes; download remains an explicit user action. The browser's own viewer handles `#page=N`; the target page is also shown in text and download remains available if the browser ignores the jump. No public object URL, external document viewer or coordinate-highlighting claim exists.

## Demo and persistence

Only the additive revision `f51e9bf1a005` is new. It adds `demo_workspaces(workspace_id)` with a cascading workspace FK. M1–M4 migration bytes remain unchanged. This persistent label survives process restarts and is carried in dossier, workspace-list/read and export responses. A nonempty marker table blocks its downgrade; source/workspace/account deletion uses existing cascades. Production startup refuses a database containing demo markers in addition to existing safety/processor guards.

Demo mode requires explicit non-production opt-in and synthetic transports; it is never a fallback for a live provider failure. Use a separate database and private object root. The final local evaluation used `viesett_m5_demo_final` and `.local/m5-demo-final-objects`. Earlier debug artifacts were left untouched; a shared-storage move was rejected by automatic approval review and was unnecessary for the completed work.

## Deliberate limits

Supported extraction remains bounded NL/FR deterministic layouts from M3/M4. No real customer corpus, live registry result or production authentication deployment was verified in M5. The first web UI is English. Native mobile PDF behavior, missing official unit labels, many conditional requirements and token loss on reload are concrete private-evaluation usability topics. They should inform M6 rather than trigger another large backend subsystem automatically.
