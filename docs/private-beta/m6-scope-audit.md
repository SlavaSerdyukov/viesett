# M6 scope audit

2026-11-14. Audited the original **Private Beta Hardening + Live Source Verification** scope against clean entry `1928f9e`, the completed hotfix and existing verification artifacts. No application implementation was missing. This continuation closes verification/documentation gaps; it does not recreate features.

Status describes the named deliverable. COMPLETE does not certify deployment, legal compliance or compatibility with documents that were not supplied. PARTIAL means additional evidence/documentation was needed; NOT_STARTED identifies an actual future operator/research activity; NOT_APPLICABLE identifies an activity outside the supplied-material or authorized delivery scope; BLOCKED_BY_ENVIRONMENT is specific to the named host.

| Major requirement / original sections | Entry status | Final status | Evidence / boundary |
| --- | --- | --- | --- |
| Preserve M1–M5, inspect worktree, freeze README (1–3) | COMPLETE | COMPLETE | Entry diff/index empty; M5/hotfix/M6 already committed together; byte checks against entry and M5 |
| Current GRAR request and provider contracts (4–5, 8) | COMPLETE | COMPLETE | Current adapter/fixtures inspected; official reference and live OpenAPI rechecked November 14 |
| Safe opt-in live smoke and diagnostics (6–7, 56) | PARTIAL | COMPLETE | Existing tool retained; new LIVE_SUCCESS including one safely retried HTTP_429; no customer query/key/body output |
| Contract drift check (9) | COMPLETE | COMPLETE | Live SUCCESS, no failed expectations; CI stays offline, no automatic mutation |
| Browser session/exchange/reload (10–12, 14) | COMPLETE | COMPLETE | Existing server session/cookie implementation; local tests plus exact-commit hosted critical journeys |
| Session isolation/expiry/rotation/revocation (13, 52–54) | COMPLETE | COMPLETE | Backend/frontend tests and cookie/reload/logout browser checks; parent authority retained |
| CSRF and Origin (12–13) | COMPLETE | COMPLETE | Per-session header + exact Origin + SameSite; fail-closed production settings; tested |
| Conditional requirements and explanation (15–16) | COMPLETE | COMPLETE | Required now / May apply / Received / deferred grouping; meaningful gaps; same print grouping |
| Minimal structured context and source preference (17–19) | COMPLETE | COMPLETE | One optional known-deed-date need, trusted sources first, MANUAL/UNVERIFIED evidence and qualified EPC timeline |
| Private aggregate-only corpus harness/manifest (20–24) | COMPLETE | COMPLETE | Local-only bounded evaluator, synthetic tests, no text/value/filename output; full M4 impact explicitly requires dossier workflow |
| Authorized real corpus evaluation (23–25, 49) | NOT_APPLICABLE | NOT_APPLICABLE | No authorized corpus supplied; actual NO_CORPUS / NOT_PERFORMED; real accuracy/OCR frequency unknown |
| OCR implementation (25) | NOT_APPLICABLE | NOT_APPLICABLE | Deliberately not in M6; future decision requires measured real blocking frequency |
| Chromium and WebKit critical workflow (26–27) | COMPLETE | COMPLETE | Local supported matrix plus hosted exact-commit run |
| Firefox critical workflow on a supported host (26–27) | PARTIAL | COMPLETE | Hosted Linux Firefox journey passes; eight configured browser tests pass overall |
| Firefox launch on this local macOS host (26–27) | BLOCKED_BY_ENVIRONMENT | BLOCKED_BY_ENVIRONMENT | Previously reproduced pre-page profile-folder failure; no bypass/retry asserted; hosted success is separate evidence |
| Mobile/tablet workflow (28) | COMPLETE | COMPLETE | Chromium emulated dimensions, keyboard/unit/upload/copy/viewer/notary; no physical-device certification |
| Private PDF viewer/fallback/lifecycle (29) | COMPLETE | COMPLETE | Unit Blob revoke/abort and supported browser surrounding-viewer flows, now including hosted Firefox; native PDF pixels not certified |
| Print pagination, source details and controls (30–31) | COMPLETE | COMPLETE | Ten-page synthetic raster QA from November 13 retained; hosted print checks pass; no server PDF renderer |
| Accessibility/keyboard/focus/semantics (32–34) | COMPLETE | COMPLETE | Eight major desktop pages plus responsive Overview axe checks and keyboard/focus tests; no human AT claim |
| Comprehension, vocabulary, partial/source states (35–38) | COMPLETE | COMPLETE | Completeness ≠ safety, estimate ≠ debt, gap ≠ blocked sale visible at point of use; source errors remain distinct |
| Current performance/payload baseline (39–40) | PARTIAL | COMPLETE | Post-hotfix measurements on November 14; five docs / 105 facts / 89,872 bytes; actual bounded observations, no SLA |
| Processing polling/request review (41) | COMPLETE | COMPLETE | Shared dossier query, active-only bounded polling/backoff, hidden/unmounted observers stop, PDFs on demand |
| One-worker beta configuration and demo separation (42–44) | COMPLETE | COMPLETE | Existing fail-closed factory/config/DB startup guard tested; no additional infrastructure/migration |
| Checklist, authorized-property procedure, evaluation guide (45–49) | COMPLETE | COMPLETE | Existing focused docs reviewed and retained; human observation outside product; no analytics/research DB |
| Privacy/security and no new rules (50–51) | COMPLETE | COMPLETE | Focused session/corpus draft additions only; no changes to legal bases, statutory periods or the hotfix |
| Backend/frontend/E2E/CI regression (52–55, 57) | PARTIAL | COMPLETE | Local hash-matched 474/92.60%, 41 frontend, seven local supported journeys; inspected hosted run adds all eight engines/projects |
| Migrations (58) | COMPLETE | COMPLETE | Retained c82e16a7b603; prior 41 local commands plus hosted chain/guards pass; fresh empty head/check also pass November 14 |
| Consolidated current report and verification (59–60; continuation report) | PARTIAL | COMPLETE | Single updated implementation report with 39 requested topics; old date-specific evidence distinguished from new checks |
| Actual production-like real-data deployment | NOT_STARTED | NOT_STARTED | No deployment requested/performed; safety/processor/privacy/TLS/storage/backup/incident gates remain operator blockers |
| Real buyer study / physical devices / human assistive technology | NOT_STARTED | NOT_STARTED | No participants/material available; guide defines the next controlled evaluation; no invented findings |

The implementation/verification deliverables of M6 are complete. Operational rollout and real-material evaluation remain explicit prerequisites for using real buyer documents. Choose subsequent work from those observations; no M7 or assumed feature roadmap follows this audit.
