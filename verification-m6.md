# Viesett Milestone 6 verification

**Consolidated 2026-11-14**, 0.6.0 — Private Beta Hardening + Live Source Verification. [Single implementation report, 39 continuation topics](docs/implementation-report-m6.md) · [Original-scope audit/statuses](docs/private-beta/m6-scope-audit.md).

## Final evidence and chronology

| Evidence | Actual result / date |
| --- | --- |
| Entry | Clean main at `1928f9eeac8c9c281ac7e8723450a724362c0169`; full diff/index empty; application files exactly match completed hotfix fingerprints |
| Local backend baseline retained | **474 passed, 92.60% combined branch-aware coverage, 78.88s**, completed hotfix November 13; no source/test/config changes since |
| Local frontend retained | **41 tests / three files, 4.56s**; frozen/type/lint/format/contract/build pass |
| Local supported browser matrix retained | **Seven passed, 19.4s**, Chromium desktop/tablet/mobile and WebKit; local Firefox cannot launch before page creation |
| Hosted exact-commit verification inspected November 14 | **SUCCESS**: 474 / 92.60% / 99.71s; 41 frontend; **eight browser tests, 47.1s**, including Linux Firefox/WebKit; migration/quality chain all successful |
| Actual live checks November 14 | GRAR **LIVE_SUCCESS / RESOLVED**, one safely retried HTTP_429; official OpenAPI expectations **SUCCESS**, final stderr empty |
| Fresh local checks November 14 | Production build, empty-head migration/check, post-hotfix HTTP/UI measurements, NO_CORPUS invocation, scope/integrity review |
| Manual evidence retained | Official contract/code/config/payload review; ten synthetic print pages rasterized/inspected November 13 |
| Not evaluated / operator gates | No real authorized corpus, buyer study, physical-device/printer/human AT or deployed real-data environment |

The original pre-M6 M5 baseline was **408 passed, one failed, 93.85%, 46.14s** (`60 != 80` date drift). The first M6 run was 469 / 92.57%; the later completed hotfix added five tests and is the baseline above. Standalone M5-only hotfix: **414 / 93.88%, 64.59s**. These dated results are retained, not presented as current failures or new continuation work. [Historical hotfix explanation](docs/implementation-report-demo-date-hotfix.md).

No new application feature was missing in the scope audit. This continuation updates verification/documentation and closes supported-host browser/performance evidence gaps. No hotfix replacement, duplicated date handling, new migration, README edit, commit/push/deploy or M7. The original `== 80` test and `tests/test_demo_dates.py` remain unchanged. Existing marker-based service defaults preserve the fixed fictional date/current normal date/explicit override policy.

## Genuine hosted CI

[GitHub Actions run 43530283363](https://github.com/SlavaSerdyukov/viesett/actions/runs/43530283363), event **push**, branch main, exact SHA **1928f9eeac8c9c281ac7e8723450a724362c0169**, job **verify / 132245976014**, conclusion **success**. Started 2026-11-13 23:52:24 UTC, finished 23:58:18 UTC: **2026-11-14 00:52–00:58 Europe/Brussels**.

Run metadata, every job step and decoded logs were read through the connected GitHub GET tools. Selected content-free log evidence is saved in `.local/m6-continuation-2026-11-14/hosted-evidence.json`. The generic workflow-run collection was used; unlike the old commit wrapper it includes push runs. No inference from an empty PR-only result, badge or local green.

```text
Required test coverage of 85% reached. Total coverage: 92.60%
474 passed in 99.71s
Test Files 3 passed (3)
Tests 41 passed (41)
[7/8] [firefox] ... address → private dossier → PDF → finding → question → source → print
[8/8] [webkit] ... address → private dossier → PDF → finding → question → source → print
8 passed (47.1s)
```

All quality/migration/install/frontend/browser steps succeed. Python 3.12, PostgreSQL 16, Node 24, hosted Ubuntu. Tests use synthetic data/transports; live tools remain excluded/refuse CI. Dependency/browser installation uses network normally; test execution requires no government API, AI credential or external OCR. This is an existing run; no rerun/commit/push was performed. Local documentation changes from this continuation have not triggered hosted CI; application/tests/config match the successful commit.

## Retained local gates and environment

Python **3.12.14**, PostgreSQL **15.15**; task-local Unix socket `.local`, port 55483 with no TCP listener. Existing source fingerprints, including frontend and migrations, exactly match the final hotfix snapshot. Consequently no redundant full local suite was run after inspecting the current exact-commit hosted run. Existing local commands/results remain applicable:

```sh
uv sync --frozen --offline
uv run --no-sync ruff check .
uv run --no-sync ruff format --check .
uv run --no-sync mypy
uv run --no-sync alembic upgrade head
uv run --no-sync alembic check
uv run --no-sync pytest
```

All seven exit zero, mypy **136 files**, **474 passed / 92.60%**, `.local/demo-date-hotfix/current-gates/{1..7}.log`, `results.json`. Threshold **85%**, branches/thread/greenlet unchanged, no exclusions/test removal/xfail. Original 409 cases + 60 M6 + five date regressions retained. The scoped M5-only environment/patch is historical reference, not a new branch or duplicate implementation.

Frontend local commands/results preserved at `.local/verification-m6-web/`:

```sh
# web; project-local cache used for frozen install
npm ci --offline --no-audit --no-fund
npm run typecheck
npm run lint
npm run format:check
npm test
npm run build
# repository root
.venv/bin/python scripts/generate_web_contract.py --check
```

Type/lint/format/contract pass; **41 tests / three files, 4.56s**. Current source unchanged and hosted steps independently pass. Runtime npm audit at first M6 verification: zero advisories; install reported nine moderate development advisories. No force upgrade or all-dependency-clean claim, and no new audit was inferred.

Fresh local `npm run build` on November 14 passes in **7.30s**, 1,817 modules; hosted build 1.50s. Actual unchanged assets: HTML **0.59KB / 0.36KB gzip**, CSS **20.67KB / 5.32KB gzip**, JS **356.13KB / 111.23KB gzip**. Current build log `.local/m6-continuation-2026-11-14/build.log`. Test-fixture IDs/tokens remain excluded from production imports/bundle.

## Browser, PDF, print and accessibility

Earlier local supported command, from web:

```sh
VIESETT_DATABASE_URL='postgresql+asyncpg:///viesett_m6_web?host=/Users/slavaserdukov/Desktop/dev/viesett/.local&port=55483' PLAYWRIGHT_BROWSERS_PATH=../.local/playwright npm run e2e -- --project desktop --project tablet --project mobile --project webkit
```

**Seven passed, 19.4s**, `.local/verification-m6-web/e2e-supported.log`. Local Firefox previously failed before page creation with “Could not find profile folder,” under default/repo-local/canonical `/private/tmp` roots. Logs `.local/m6-e2e-first.log`, `.local/m6-firefox.log`, `.local/m6-firefox-private-tmp.log`; no bypass/forced click. That host-specific result is preserved. **Hosted Linux now passes all eight configured projects/tests including Firefox**; the supported-host requirement is closed without pretending local macOS worked.

Actual journeys verify private exchange/cookie flags/reload, address/choice, dossier, optional context, upload/focus, finding/question/copy, page citation, private Blob viewer/fallback/reload, print/notary and server logout/401. Two Chromium journeys each at desktop/tablet/mobile, plus Firefox/WebKit critical flow. Unit tests assert revoke/abort/session expiry/CSRF/cache behavior. No retries/traces. Surrounding viewer behavior is tested, not native PDF pixels/coordinate highlighting or physical mobile rendering.

Axe A/AA-tag checks cover Start, Overview, Documents, Findings, Co-ownership, Questions, Evidence, Print on desktop plus responsive sample Overview. Keyboard/focus tests cover dialogs/navigation/selection/upload/classification/delete/citation/copy/reconnect/logout. No human assistive-technology certification or real buyer comprehension claim.

Retained manual print QA from **November 13**: ten-page synthetic A4 PDF at `.local/verification-m6-print/sample-notary.pdf`, generated by the desktop Playwright sample. Poppler was unavailable, so CoreGraphics rasterization was used:

```sh
swift -module-cache-path .local/swift-cache .local/render_m6_pdf.swift .local/verification-m6-print/sample-notary.pdf .local/verification-m6-print/pages-final
```

All ten raster pages inspected; aggregate assertions in `results.json`: source/check/version details, provisional unverified date, responsibility/assumptions, visible deferred heading, one professional footer, controls omitted. Existing print fixes retained; current hosted test regenerates the sample and tests print media. No new manual raster inspection, real printer study or server PDF feature is claimed in this continuation. [Browser/print limits](docs/frontend/m6-browser-print.md).

## Renewed official-source verification — November 14

Inspected actual adapter and current [official v2 reference](https://docs.basisregisters.vlaanderen.be/docs/api-documentation.html), API 2026-10-29 / shell 8.17.4, plus its linked OpenAPI 3.0.4 through the live checker. [Dated review](docs/integrations/source-review-2026-11-12-m6.md) retains both retrieval dates; filename follows the original requested name.

```text
GET https://api.basisregisters.vlaanderen.be/v2/adressen/zoeken?q=…&resultaatType=adressen&status=inGebruik&limit=6
```

M5 entry actually used `query`/`resultType=Address`; both old code and M2 report were stale. Existing M6 corrected code/fixtures; historical M2 report remains unchanged. Generated provider requests, optional key/header and current `resultaten` shape are tested independently of domain normalization; validation/SSRF/ambiguity bounds retained.

Actual renewed opt-in commands (correct src-layout environment):

```sh
PYTHONPATH=src VIESETT_RUN_LIVE_SOURCE_TESTS=1 .venv/bin/python -m viesett.tools.verify_grar
PYTHONPATH=src .venv/bin/python -m viesett.tools.check_grar_contract --live
```

Smoke **LIVE_SUCCESS / RESOLVED**, harmless fixed existing public example `Dahliastraat 97, 9000 Gent`. DNS/verified TLS/search/detail/unit/building/parcel/normalization succeed: selected unit, one parcel, no missing relations. One parcel detail HTTP_429 safely retried to success. Drift **SUCCESS**, no failed expectations; schema SHA-256 **4a0970d12e9d7dc89131adcfb3d71d5b01f35b0dc41fafa82edf5e5c8e2e012c**. Whole hash differs from November 13; provider examples are volatile, and a whole-hash difference alone does not establish semantic drift. Selected expectations remain unchanged and never auto-edit code.

Current content-free `.local/m6-continuation-2026-11-14/{live-grar,live-contract}.json`, final stderr empty. Initial raw-venv invocation lacked PYTHONPATH and failed before networking; initial environment logs are saved separately, not classified as provider failure. No customer address/history/key/body output or third-party paid service. Earlier November-13 live successes remain historical. A successful chain/retry is not uptime, load/quota, heritage or general compatibility verification.

## Corpus and post-hotfix performance

Actual November-14 `PYTHONPATH=src .venv/bin/python -m viesett.tools.evaluate_corpus`: **NO_CORPUS**, documents=0, `real_corpus_evaluation=NOT_PERFORMED`, final stderr empty. **Real corpus evaluation not performed**; real classification/value accuracy/association/OCR frequency unknown. Synthetic four-input OCR_REQUIRED 1/4 tests the counter, not real compatibility. [Manifest/privacy/impact limits](docs/private-beta/document-compatibility.md).

Fresh synthetic `viesett_m6_continuation` database/private object root, one local demo backend, production-assets Vite preview and Chromium. All outbound providers are synthetic, artificial gap disabled. Actual HTTP/session/upload/parser/evaluation pipeline measured after the completed hotfix:

| Measurement | Samples | Result | Range |
| --- | --- | --- | --- |
| Five-document dossier GET | 5 | Median **118.12ms** | 93.67–753.21ms |
| Production-assets Start ready | 3 | Median **544.51ms** | 277.01–962.49ms |
| Authenticated reload→Overview | 3 | Median **476.54ms** | 425.93–491.17ms |
| 1,004-byte text PDF upload→analyzed | 1 | **1,287.69ms** | Single observation |
| Deterministic refresh, public_sources=false | 1 | **93.02ms** | Single observation |
| Seed five synthetic documents | 1 | **5,005.48ms** | Single observation |

Payload **89,872 bytes**, five documents, 105 facts, unchanged. Normal DTO excludes raw text/PDF/provider/evaluation archives/history/duplicate result collections. New measurement helpers write aggregate-only logs and do not modify the checked-in DTO fixture. `.local/m6-continuation-2026-11-14/{backend,frontend}.json`, `measure_backend.py`, `measure_ui.mjs`. Earlier timing observations under `.local/verification-m6-performance/` predate the hotfix and are not a controlled comparison. No cause/SLA/optimization need is inferred from these small samples. [Detailed method](docs/private-beta/performance.md).

Polling code/tests reviewed without changes: shared query key, active-only bounded interval/backoff/failure/time cutoff, analysis-start anchor, hidden/unmounted observer behavior, on-demand PDFs, no WebSocket.

## Migration history retained

**c82e16a7b603** remains the sole M6 migration after **f51e9bf1a005**. Sessions/compound ownership/UNVERIFIED constraints and downgrade guards reviewed; no migration/history edit. November-14 fresh empty database `alembic upgrade head` and `alembic check` pass (logs `migration.log`, `alembic-check.log` in continuation folder).

Prior **41 local commands all exit zero**, `.local/verification-m6-migrations/{1..41}.log`, `results.json`, with synthetic-only sentinels. Current exact-commit hosted step metadata/logs independently confirm the full chain/guards, including empty-head/check and preservation. No repeated destructive schema exercise was necessary on the same unchanged source:

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

Guard helpers intentionally assert downgrade refusal when protected M4/M5/M6 data exists. Cleanup removes only synthetic sentinel data; live session/context history must be deliberately handled before a real downgrade. Original README and five old migrations are byte-compared against M5; M6 migration/hotfix application files match entry.

## Integrity, scope, operations and cleanup

[Scope audit](docs/private-beta/m6-scope-audit.md) maps every major original requirement to COMPLETE / PARTIAL / NOT_STARTED / NOT_APPLICABLE / BLOCKED_BY_ENVIRONMENT at entry and completion. All requested implementation/verification deliverables are COMPLETE. Actual deployment/buyer study remain NOT_STARTED and real-material metrics are unavailable; local Firefox launch is BLOCKED_BY_ENVIRONMENT while hosted engine coverage passes.

Final hashes/integrity/cleanup results are under `.local/m6-continuation-2026-11-14/`. No source/test/frontend/config/schema change, new customer PDF/secret/build/private file Git candidate, README edit, commit/push/deploy. `git diff --check`, report numbering/link validation, unchanged hotfix/migration/source checks and production-bundle test-constant exclusions pass. Docs are the only final changes.

Task-owned local backend/frontend/PostgreSQL stopped after measurement; synthetic files/databases retained, no shared/user service terminated. No other project's .env or credential used. No new PDF generation/research database/analytics/AI/OCR/email/new legal rules.

M6 prepares controlled evaluation infrastructure; it does not launch a real-data service. Production safety adapters/processors/TLS/storage/backups/retention/privacy/legal/incident gates and intended-network smoke remain before real documents. [Deployment](docs/private-beta/deployment.md), [checklist](docs/private-beta/checklist.md), [evaluation guide](docs/private-beta/evaluation-guide.md). Choose subsequent changes from actual buyers, entitled documents and source reliability, not an automatic next milestone.
