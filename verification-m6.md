# Viesett Milestone 6 verification

2026-11-13, Europe/Brussels. Scope: **0.6.0 — Private Beta Hardening + Live Source Verification**. [Implementation report: all 40 requested topics](docs/implementation-report-m6.md). README unchanged; no commit/push/deploy or next feature milestone.

| Evidence class | Actual result |
| --- | --- |
| Automated backend | Seven gates pass; **469 tests, 92.57% combined branch-aware coverage, 59.23s** |
| Automated frontend | Frozen install/type/lint/format/contract/build pass; **41 tests, three files, 4.56s** |
| Automated supported browsers | **Seven passed, 19.4s**; Chromium desktop/tablet/mobile and WebKit critical flow |
| Local Firefox | **LAUNCH_BLOCKED** before page creation; no Firefox product-success claim |
| Migrations | All **41** chain/sentinel/guard/downgrade/empty-head/check commands pass |
| Live official source | GRAR **LIVE_SUCCESS / RESOLVED**; official OpenAPI expectation check **SUCCESS** |
| Manual review | Current official contract/code, payload/configuration and all ten rasterized synthetic print pages |
| Required real material unavailable | **Real corpus evaluation not performed**; no buyer study, real-device/printer or human screen-reader test |
| Deployment / hosted CI | Not performed; production/privacy/processor and actual environment gates remain |

## Entry state and baseline

Entry `git status --short` and full diff were empty. Branch `main`, HEAD `9928d81` (`M5 product API + wed ux`); recent `d9c75c2`, `531a042`. M5 verification, M2 adapter, preview/authentication, existing tests and Playwright configuration inspected before application changes. No destructive Git command was used.

Before M6, six of seven backend gates passed. Pytest: **408 passed, one failed, 93.85%, 46.14s**. `test_demo_uses_real_pipelines_and_is_persistently_labelled` expected 80% but got 60% after the synthetic sample's rolling date advanced. M6 gives marked demos an explicit 2026-11-12 evaluation date; the existing assertion remains and passes. Actual real dossiers keep their current evaluation date. Baseline logs: `.local/verification-m6-baseline/{1..7}.log`, `results.json`.

Baseline frontend frozen install/type/lint/format/generated contract/build pass, **30 tests, 3.51s**, build 941ms. Unchanged baseline Chromium desktop/tablet/mobile E2E: **six passed, 15.5s**. The initial launch environment needed absolute PYTHONPATH, not an application test bypass. Logs: `.local/verification-m6-web-baseline/`.

## Environment and command conventions

Python **3.12.14**, local PostgreSQL **15.15**, project uv environment and Node/npm; hosted CI targets Python 3.12, PostgreSQL 16 and Node 24. Local task PostgreSQL used Unix socket `.local`, port 55483, no TCP listener. Distinct synthetic databases: `viesett_m6_baseline`, `viesett_m6_web`, `viesett_m6_migrations`, `viesett_m6_performance`. No other project's `.env`, customer data or AI credential used.

Shell login disabled. Project-local caches/bootstrap were used because the initial sandbox had cache/network restrictions. Initial npm offline/cache attempt failed; the authorized install populated `.local/npm-cache`, and the final frozen install succeeds offline. No install-script approval was bypassed. Loopback/browser/official network checks used the environment's approved execution path.

Backend runner `.local/verification/run_m6_gates.py` executes the following commands with project `.venv/bin`/`.bootstrap/bin` on PATH, `PYTHONPATH` set to absolute `src`, `UV_CACHE_DIR=.uv-cache`, `UV_PYTHON_DOWNLOADS=never`, and both database variables pointing to the isolated baseline database:

```sh
uv sync --frozen
ruff check .
ruff format --check .
mypy
alembic upgrade head
alembic check
pytest
```

All exit **0**. Logs `.local/verification-m6/{1..7}.log`, `results.json`, `runner.log`. Mypy: **135 source files**. The 409 previous cases remain plus 60 M6 cases. Threshold **85%**, branch collection and SQLAlchemy thread/greenlet remain; no production omissions/exclusions or threshold reductions. CLI-only networking/reporting paths remain partly uncovered, reflected in the honest total.

Additional explicit CI/offline diagnostic/contract check:

```sh
CI=true .venv/bin/pytest tests/test_grar_m6.py --no-cov -q
```

**16 passed, 0.08s**, `.local/m6-ci-offline-contract-tests.log`. MockTransport only; synthetic success is never labeled LIVE_SUCCESS. Normal tests reject live HTTP; live CLIs refuse CI. Dependency/browser installation may download packages; test execution does not require provider HTTP, credentials, paid models or external OCR.

## Frontend gates and bundle

From `web`, with `npm_config_cache=../.local/npm-cache` for installation:

```sh
npm ci --offline --no-audit --no-fund
npm run typecheck
npm run lint
npm run format:check
npm test
npm run build
```

From repository root:

```sh
.venv/bin/python scripts/generate_web_contract.py --check
```

All pass; final **41 tests, three files, 4.56s**. Logs `.local/verification-m6-web/{install,typecheck,lint,format,tests,build}.log` and final contract log. Final Vite build **929ms**, 1,817 modules:

| Asset | Uncompressed | gzip |
| --- | --- | --- |
| HTML | 0.59KB | 0.36KB |
| CSS | 20.67KB | 5.32KB |
| JS | 356.13KB | 111.23KB |

Runtime `npm audit --omit=dev --json`: **zero vulnerabilities**, `.local/m6-runtime-audit.json`. Installation reported **nine moderate development advisories**; no force upgrade or all-dependency-clean claim. No test-fixture account/access constants are included in production entry imports/bundle.

## Browser, accessibility and PDF checks

Actual final command from `web`:

```sh
VIESETT_DATABASE_URL='postgresql+asyncpg:///viesett_m6_web?host=/Users/slavaserdukov/Desktop/dev/viesett/.local&port=55483' PLAYWRIGHT_BROWSERS_PATH=../.local/playwright npm run e2e -- --project desktop --project tablet --project mobile --project webkit
```

**Seven passed, 19.4s**, `.local/verification-m6-web/e2e-supported.log`: two each Chromium desktop (1440px), tablet (900px touch), mobile (Pixel 7 emulation), one WebKit critical journey. Private token exchange/HttpOnly cookie/reload, address/choice, dossier, optional context, upload, finding, question/copy, page citation, authorized Blob viewer/fallback/reload, notary/print, logout and server 401 covered. Traces/retries/forced clicks disabled. Unit tests additionally assert Blob revocation and session expiry/reconnect/CSRF/cache behavior.

All eight configured tests were attempted during M6. Product focus/copy failures discovered in the expanded run were corrected and rerun. Firefox exits before creating a page with **“Could not find profile folder.”** Default/project-local/canonical `/private/tmp` roots reproduce it. Logs `.local/m6-e2e-first.log`, `.local/m6-firefox.log`, `.local/m6-firefox-private-tmp.log`. It remains enabled in CI; full local default matrix is **not all green**. Repeat Firefox on a supported host. No native Firefox PDF verification or security-option bypass is claimed.

Axe WCAG2 A/AA-tag checks pass on desktop Start, Overview, Documents, Findings, Co-ownership, Questions, Evidence, Print, plus sample Overview tablet/mobile. Explicit keyboard/focus coverage includes dialogs, selection, upload/classification, citation/copy/delete, session reconnect and logout. Automated checks and emulated dimensions are not physical-device testing or human assistive-technology certification.

The final desktop sample produced:

```text
web/test-results/journey-sample-co-ownershi-a6ad5-s-and-responsive-navigation-desktop/sample-notary.pdf
```

Copied to private `.local/verification-m6-print/sample-notary.pdf`, **ten A4 pages**. Poppler unavailable; local macOS CoreGraphics renders were used:

```sh
swift -module-cache-path .local/swift-cache .local/render_m6_pdf.swift .local/verification-m6-print/sample-notary.pdf .local/verification-m6-print/pages-final
```

All ten PNGs were visually inspected after the final change; text assertions confirm source/check/version details, provisional unverified deadline, assumptions/responsibility, one professional-review footer and no print controls. Fixed disclosure contents missing from print, focus outline leakage, source spacing, long Article 3.94 pagination and hidden deferred-check heading. Cards/rows/readable references retained. Some whitespace follows indivisible cards; no pixel-identical output, real printer/native PDF pixel or server-rendering claim. Aggregate results: `.local/verification-m6-print/results.json`, `render-final.log`. [Browser/print limits](docs/frontend/m6-browser-print.md).

## Actual official-source checks

Reviewed [official API documentation](https://docs.basisregisters.vlaanderen.be/docs/api-documentation.html) (2026-10-29, shell 8.17.4) and its [OpenAPI 3.0.4](https://docs.basisregisters.vlaanderen.be/docs/v2/docs.json?culture=en-GB), retrieved **2026-11-13**. [Pinned source review](docs/integrations/source-review-2026-11-12-m6.md) explains the requested filename/date difference.

The obsolete entry request was actually present: `query`, `resultType=Address`. Now:

```text
GET /v2/adressen/zoeken?q=…&resultaatType=adressen&status=inGebruik&limit=6
```

Current optional key header, result field and detail/navigation metadata are regression-tested independently of domain normalization. Historical M2 reports remain unchanged. No other source/legal coverage is implied.

Actual opt-in commands, run outside CI without printing a key or provider body:

```sh
VIESETT_RUN_LIVE_SOURCE_TESTS=1 uv run python -m viesett.tools.verify_grar
uv run python -m viesett.tools.check_grar_contract --live
```

Live smoke: **LIVE_SUCCESS / RESOLVED**, fixed harmless existing public example `Dahliastraat 97, 9000 Gent`. DNS/TLS/search/address detail/unit list/detail/building/parcel list/detail/normalization succeeded, one selected unit, one parcel, no missing relations. Final `.local/m6-live-grar.json` contains only categories/counts/booleans; stderr empty. Query text/IDs are stripped from stage labels. No customer address or history is used. One chain is not a reliability/heritage/accuracy/quota guarantee.

Drift: **SUCCESS**, no failed expectations; `.local/m6-live-contract.json`, stderr empty. Retrieved whole-schema SHA-256 `98addb524772085552877c7c4255c2e0f14b48a01898b19bfd4e4c5ee2b01a35`. Provider-generated example timestamps can change it without semantic drift; committed selected metadata excludes those examples. Tool checks expectations and never rewrites behavior. Offline usage: `python -m viesett.tools.check_grar_contract --schema /private/local/schema.json`.

## Corpus and performance

Actual `uv run python -m viesett.tools.evaluate_corpus`: **NO_CORPUS, documents=0, real_corpus_evaluation=NOT_PERFORMED**, `.local/m6-corpus-status.json`. **Real corpus evaluation not performed.** Synthetic four-input tests validate reporting; OCR_REQUIRED 1/4 is not a real frequency. Real classification/value accuracy, layout coverage, association and OCR frequency are unknown. Harness has aggregate-only output and no network/provider/AI/database access; optional private normalized anchor permits bounded association/M3 rule-impact evaluation. Full M4 impact remains a dossier-workflow exercise. [Compatibility/manifest/privacy limits](docs/private-beta/document-compatibility.md).

Actual local HTTP/production-assets measurements, Python 3.12/PG15/loopback/one worker/synthetic providers with artificial gap disabled:

| Measurement | Samples | Result | Range |
| --- | --- | --- | --- |
| Five-document dossier GET | 5 | Median 18.38ms | 17.89–39.78ms |
| Production-assets Start ready | 3 | Median 73.97ms | 73.22–136.21ms |
| Authenticated reload→Overview | 3 | Median 102.35ms | 94.80–102.78ms |
| Synthetic 1,004-byte text PDF upload→analyzed | 1 | 204.79ms | Single observation |
| Deterministic cross-document refresh, no public refresh | 1 | 17.90ms | Single observation |
| Seed five synthetic pipeline documents | 1 | 977.92ms | Single observation |

Dossier **89,872 bytes**, five documents, 105 current facts. Normal DTO excludes histories, raw text/upstream/PDF/evaluation archives and duplicate finding/question collections. Helpers `.local/verification/measure_m6.py`, `measure_m6_ui.mjs`; results `.local/verification-m6-performance/{backend,frontend}.json`. Browser performance used production assets before the final small print-only heading fix; final bundle sizes above reflect that fix. Not an SLA, live-source latency distribution or real-corpus performance claim. [Method](docs/private-beta/performance.md).

Polling reviewed: shared query key, active-operation intervals only, bounded backoff/failure/time stop and no background/unmounted interval storm. Existing Query lifecycle owns observers; no WebSocket added.

## Additive migration verification

New `c82e16a7b603` follows unchanged `f51e9bf1a005`. Session table/compound owner-parent FK, authority CHECK and MANUAL-only UNVERIFIED constraint. No old notice/ack rewrite. Original README and M1–M5 migration bytes compared against HEAD, not inferred from tests.

All **41 commands below exit 0**, using isolated `viesett_m6_migrations`; runner `.local/verification/run_m6_migrations.py`, logs `.local/verification-m6-migrations/{1..41}.log`, `results.json`, `.local/m6-migrations-runner.log`. Guard commands deliberately provoke and assert expected downgrade refusals; they succeed only when data is protected. Cleanup commands remove only the scripts' synthetic sentinels. Older milestone metadata checks are superseded by current-head `alembic check`, while all prior chain/data checks remain.

```sh
alembic upgrade 5e1e917449ce
python scripts/verify_milestone_upgrade.py seed
alembic upgrade da321bc669fb
python scripts/verify_milestone_upgrade.py verify
python scripts/verify_m3_upgrade.py seed
alembic upgrade 192e0442ffc8
python scripts/verify_m3_upgrade.py verify
python scripts/verify_m3_upgrade.py guard
python scripts/verify_m4_upgrade.py seed
alembic upgrade d64802d3610f
python scripts/verify_m4_upgrade.py verify
python scripts/verify_m4_upgrade.py guard
alembic downgrade 192e0442ffc8
python scripts/verify_m4_upgrade.py verify-m3
alembic upgrade d64802d3610f
python scripts/verify_m4_upgrade.py verify
python scripts/verify_m4_upgrade.py cleanup
python scripts/verify_m5_upgrade.py seed
alembic upgrade f51e9bf1a005
python scripts/verify_m5_upgrade.py verify
python scripts/verify_m5_upgrade.py guard
alembic downgrade d64802d3610f
python scripts/verify_m5_upgrade.py verify
alembic upgrade f51e9bf1a005
python scripts/verify_m5_upgrade.py verify
python scripts/verify_m5_upgrade.py cleanup
python scripts/verify_m6_upgrade.py seed
alembic upgrade head
python scripts/verify_m6_upgrade.py verify
python scripts/verify_m6_upgrade.py guard
alembic check
alembic downgrade f51e9bf1a005
python scripts/verify_m6_upgrade.py verify
alembic upgrade head
python scripts/verify_m6_upgrade.py verify
python scripts/verify_m6_upgrade.py cleanup
alembic downgrade da321bc669fb
alembic upgrade head
alembic downgrade base
alembic upgrade head
alembic check
```

This includes empty→head, M1→M6, M5 data/notices/ack preservation, each M6 guard, M6→M5 preservation after synthetic cleanup, full downgrade and final empty upgrade/check. Real session/context history must be intentionally handled before downgrade.

## Integrity, operations and remaining gates

Final `git diff --check`, generated-contract check, report-topic/link validation and README/old-migration byte checks pass. Final source hashes and aggregate integrity results live under `.local/verification-m6/`. Task-local corpus/cache/build/test files remain gitignored; no new real PDF, credential, `.local`, `node_modules` or `dist` file is a Git candidate. The checked-in metadata fixture is selected public provider schema; the frontend fixture remains synthetic.

The beta profile is implemented/tested, not deployed. It rejects demo/dev/unsafe flags, requires Secure cookies/exact HTTPS origins/private absolute storage and one worker. DB advisory lock is a session-affine startup guard; process manager remains one worker and DB recovery requires worker restart. Existing production malware/sensitive-content adapter and processor/legal gates are intentionally retained. Operator TLS/backups/retention/incident/revocation and notice/cookie review remain open. [Deployment](docs/private-beta/deployment.md), [checklist](docs/private-beta/checklist.md), [evaluation guide](docs/private-beta/evaluation-guide.md).

Temporary task-owned backend/frontend/performance services were stopped after use; the task PostgreSQL instance is stopped at final cleanup with its synthetic files retained. Cleanup outcome is recorded in `.local/verification-m6/cleanup.json`. No shared/user service was terminated or data discarded.

M6 is local/uncommitted; no M6 hosted CI was triggered/claimed. CI installs all three browsers and retains deterministic, credential-free tests; no live source tool in CI. Firefox supported-host run, real authorized corpus, buyer observations and deployment/privacy/production gates remain explicit. No live AI/OCR SaaS/email/analytics/new rules or automatic M7 begun.
