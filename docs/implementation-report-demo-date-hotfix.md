# Viesett hotfix — deterministic demo evaluation date

2026-11-13. Fix for the M5 CI failure `assert 60 == 80`. No feature work, README edit, commit or push. The entry worktree already contained uncommitted M6 work from the preceding task; it was preserved. This hotfix was independently tested on original M5 HEAD **9928d81e9e852e4d22ab58acfb8a3ac1e83e8613**, without M6.

1. **Exact root cause:** M5 seeded a fictional document package dated 2026-11-12, then invoked the existing M3/M4 evaluators without an explicit scenario date. Their defaults use today's Europe/Brussels date. Running on 2026-11-13 moved rolling Article 3.94 coverage one day beyond the supplied periods, changing 8/10 to 6/10. The original M5 tree reproduces `assert 60 == 80`; no migration/provider/association/seed-order difference was needed. The current entry tree's earlier M6 read-time date pin already made the original test pass, but left seed/analysis/deletion evaluations dependent on the clock; this hotfix closes those paths.
2. **Changed components:** `AGM_MINUTES_3Y` and `PERIODIC_CHARGES_2Y`: PRESENT → PARTIAL, each no longer complete. Both report exactly the gap **2026-11-13–2026-11-13**. Denominator remains ten. Soil MISSING and latest approved balance PARTIAL remain the two intentional gaps at the scenario date. All other components remain unchanged; full accounting below.
3. **Date/timezone involvement:** **calendar-date drift, not a host-TZ difference**. The production service explicitly uses ZoneInfo Europe/Brussels, so changing host TZ does not change its evaluation day. Controlled 2026-11-12 evaluation passes at 80%; 2026-11-13 fails at 60% on otherwise identical M5 data. Three actual TZ process runs reproduce the same failure.
4. **UTC before fix:** original M5 isolated test **failed, `assert 60 == 80`**. Log `.local/demo-date-hotfix/m5-before-UTC.log`.
5. **Europe/Brussels before fix:** original M5 isolated test **failed, `assert 60 == 80`**. Also reproduced in America/Los_Angeles. Logs `m5-before-Europe-Brussels.log`, `m5-before-America-Los_Angeles.log` in the same directory. The initial archive needed its normal `.local` pytest directory created; only the subsequent actual test results are counted.
6. **Code changed:** named fixed scenario constant in `demo_data.py`; both `refresh_due_diligence` and `refresh_coownership` resolve an omitted evaluation date from the persistent DemoWorkspace marker before falling back to the existing production clock. Thus seed, new/cached analysis, manual correction, dossier reads/refresh, direct requirements/co-ownership reads, findings/drafts and automatic source-deletion recomputation share the scenario date. Removed the narrower duplicate date pin from the pre-existing M6 dossier reader. No clock framework, new schema, migration, API field or feature added.
7. **Explicit demo date:** `DEMO_EVALUATION_DATE = date(2026, 11, 12)`. The existing explicit `evaluation_date` API/service argument is still respected. An omitted date on a normal unmarked workspace still uses current Europe/Brussels time; no global freeze. Callers deliberately asking for a different historical evaluation date keep that existing capability.
8. **Synthetic dates/data:** **unchanged by this hotfix**. Source PDFs/text and date ranges are byte-identical to M5 HEAD: EPC issued 2026-01-12 / valid until 2036-01-12; electrical inspection 2026-01-11; AGM/budget approval 2026-03-01; syndic request 2026-11-01 / response and financial context 2026-11-12; three/two-year coverage ends 2026-11-12; planned roof execution 2027-01-10 is intentionally future. Optional balance/capital-call fixtures remain as authored. No arbitrary range extension or balance/soil document added. Earlier M6 fictional transaction flags were already present at entry and remain untouched.
9. **Product completeness logic:** **unchanged**. REQUIRED usable/present information and PRESENT/EXPLICIT_NONE co-package components count; conditional/not-yet-effective checks remain outside the denominator. Findings and adverse conclusions do not subtract points. The usable non-conforming electrical certificate remains PRESENT; its applicability is CONDITIONAL in this sample, so it contributes neither an extra incomplete item nor denominator point. Co-ownership coverage algorithms and regulatory rules/versions are unchanged.
10. **Why 80% is correct:** one complete required EPC plus seven complete co-package items = **8 completed / 10 applicable**. Required soil information is missing; the latest approved balance has a reference but no approved copy and stays PARTIAL. Electrical non-conformity and EPC E remain findings rather than missing information. Roof work, €6,000 proportional estimate and buyer/notary questions remain exercised by the unchanged original test. Its `== 80` assertion is preserved byte-for-byte.
11. **Regression added:** `tests/test_demo_dates.py`, five cases: four wall dates (scenario day, next day, leap day 2028-02-29, after EPC expiry 2036-01-13) and a normal-workspace current/explicit-date control. Checks all persisted M3/M4 evaluation dates during seeding, cached and manual re-analysis, direct reads, refresh and automatic source-deletion recomputation, not only the final DTO. Before service fix: **three failed, two passed** on the existing read-pinned worktree; after fix all five pass. No xfail, assertion weakening or original-test deletion.
12. **Isolated result after fix:** original failing test **passes in UTC, Europe/Brussels and America/Los_Angeles**. New focused regression **five passed, 6.00s** before final typing-only clarification; both final full suites include those same five cases. Isolated runs disable coverage collection only for focused execution; full suites retain the project threshold/branch configuration.
13. **Full backend count:** independent **M5-only: 414 passed, 64.59s** (409 original + five regression cases); preserved current worktree **474 passed, 78.88s** (469 prior + five). Both real local PostgreSQL suites, no skipped/removed original tests or live-provider calls.
14. **Branch-aware coverage:** M5-only **93.88%**; current worktree **92.60%**. Threshold remains **85%**, branches and SQLAlchemy thread/greenlet collection retained, no exclusion/omission added.
15. **Quality gates:** both trees pass all seven: frozen offline sync, Ruff check/format, mypy (M5 121 / current 136 files), head migration, `alembic check`, full pytest. M5 uses its unchanged lockfile, own 0.5.0 virtual environment and M5 schema; current uses its existing 0.6.0 environment/head. Python 3.12.14, local PostgreSQL 15.15; CI specifies Python 3.12/PostgreSQL 16. No TZ setting in CI; evaluator explicitly selects Brussels. No frontend change/test required for this server-only hotfix. `gh` unavailable; connected GitHub wrapper returned no PR-triggered runs for HEAD and does not enumerate push runs. Hosted logs were not retrieved; the user-supplied failure plus direct source reproduction are the evidence. No hosted-green claim or workflow rerun.
16. **README:** **unchanged**, byte-identical to entry and HEAD; SHA-256 `3b7508969c50367fa3477b0685b051b241530cf8ec0a14ccec40b0b4edd0bdac`. Original `tests/test_product.py`, document fixtures, rule/coverage engines and all old migrations remain unchanged. No commit/push/deploy.
17. **Files changed by this turn:** `src/viesett/demo_data.py`, `src/viesett/services/due_diligence.py`, `src/viesett/services/coownership.py`, `src/viesett/services/dossier.py` (remove pre-existing local read-only workaround), new `tests/test_demo_dates.py` and this report. All other entry worktree files, including frontend/M6 files, were preserved. Independently applicable M5-only patch: `.local/demo-date-hotfix/m5-hotfix.patch` — three source files plus the regression test, **no M6 content**, verified with `git apply --check` against the clean HEAD extract.

## Completeness accounting

Evaluation dates: **2026-11-12 → 2026-11-13**. The same source package/requirements are used. Each complete item has weight one; a finding's severity is not a weight. `0 → 0` outside the denominator is excluded, not an incomplete point.

| Code | Applicability | Presence/component status, Nov 12 → 13 | In denominator | Complete count, Nov 12 → 13 | Reason from current M5 result |
| --- | --- | --- | --- | --- | --- |
| FL_EPC_REQUIRED | REQUIRED | PRESENT → PRESENT | Yes | 1 → 1 | Residential transfer evidence, EPC Bouw availability and statutory exceptions must be established; presence is not signature/registry authentication. |
| FL_ASBESTOS_REQUIRED | CONDITIONAL | MISSING → MISSING | No | 0 → 0 | Confirm reference construction year, accessibility, aggregated area/larger-construction exception and qualifying transfer. |
| FL_ASBESTOS_COMMON_PARTS | NOT_YET_EFFECTIVE | MISSING → MISSING | No | 0 → 0 | Ownership configuration and pre-2001 accessible-construction conditions require evidence; an existing common-parts certificate may already need disclosure. |
| FL_ASBESTOS_COMMONLY_USED | CONDITIONAL | MISSING → MISSING | No | 0 → 0 | Ownership configuration and pre-2001 accessible-construction conditions require evidence; an existing common-parts certificate may already need disclosure. |
| BE_ELECTRICAL_REQUIRED | CONDITIONAL | PRESENT → PRESENT | No | 0 → 0 | Installation history, complete prior inspection, 25-year report period, significant modifications and documented demolition/renewal exception need review; a new report is not universally required. |
| FL_SOIL_REQUIRED | REQUIRED | MISSING → MISSING | Yes | 0 → 0 | An applicable bodemattest is needed before a qualifying ground transfer agreement, including non-risk ground; inheritance and statutory transfer definitions must be checked. |
| WORKING_CAPITAL | CO_PACKAGE | PRESENT → PRESENT | Yes | 1 → 1 | Explicit documentary information; absence is never zero/none. |
| RESERVE_CAPITAL | CO_PACKAGE | PRESENT → PRESENT | Yes | 1 → 1 | Explicit documentary information; absence is never zero/none. |
| SELLER_ARREARS | CO_PACKAGE | EXPLICIT_NONE → EXPLICIT_NONE | Yes | 1 → 1 | Explicit documentary information; absence is never zero/none. |
| RESERVE_CAPITAL_CALLS | CO_PACKAGE | EXPLICIT_NONE → EXPLICIT_NONE | Yes | 1 → 1 | Explicit documentary information; absence is never zero/none. |
| PENDING_LITIGATION | CO_PACKAGE | EXPLICIT_NONE → EXPLICIT_NONE | Yes | 1 → 1 | Explicit documentary information; absence is never zero/none. |
| AGM_MINUTES_3Y | CO_PACKAGE | PRESENT → PARTIAL | Yes | 1 → 0 | Rolling explicit coverage of all relevant documents; a meeting date alone does not prove completeness. |
| PERIODIC_CHARGES_2Y | CO_PACKAGE | PRESENT → PARTIAL | Yes | 1 → 0 | Rolling explicit coverage of all relevant documents; a meeting date alone does not prove completeness. |
| LATEST_APPROVED_BALANCE_SHEET | CO_PACKAGE | PARTIAL → PARTIAL | Yes | 0 → 0 | An explicit reference alone is partial; an available balance copy with documented AGM approval is required for presence. Latestness remains documentary. |

Three-year window changes from **2023-11-12…2026-11-12** to **2023-11-13…2026-11-13**, but supplied coverage ends November 12. The two-year window changes analogously from **2024-11-12…2026-11-12** to **2024-11-13…2026-11-13**. Both gain the same one-day end gap. Totals: applicable **10 → 10**, completed **8 → 6**, percentage **80 → 60**, conditional **3 → 3**. At the fixed scenario date the end gaps are empty.

## Commands and local evidence

Original M5 was extracted with `git archive HEAD` to ignored `.local/demo-date-hotfix/m5-head`; no checkout/reset/clean. A separate `m5-fixed` extract contains only the independent patch, with its own frozen environment. Worktree fingerprints were captured before changes. No real/customer documents used. Temporary diagnostic hooks/output containing per-observation IDs were removed after transferring this content-free accounting into the report.

Actual isolated commands, from original M5 and then the fixed current tree:

```sh
TZ=UTC uv run pytest tests/test_product.py::test_demo_uses_real_pipelines_and_is_persistently_labelled -vv
TZ=Europe/Brussels uv run pytest tests/test_product.py::test_demo_uses_real_pipelines_and_is_persistently_labelled -vv
TZ=America/Los_Angeles uv run pytest tests/test_product.py::test_demo_uses_real_pipelines_and_is_persistently_labelled -vv
uv run pytest tests/test_demo_dates.py -vv
```

The focused runner sets `PYTEST_ADDOPTS=--no-cov`, `UV_NO_SYNC=1` and an explicit local environment/PYTHONPATH to share installed dependencies for reproduction. Full-gate runners unset these overrides and use each tree's frozen environment:

```sh
uv sync --frozen --offline
uv run --no-sync ruff check .
uv run --no-sync ruff format --check .
uv run --no-sync mypy
uv run --no-sync alembic upgrade head
uv run --no-sync alembic check
uv run --no-sync pytest
```

Local Unix socket `.local`, port 55483; separate synthetic `viesett_hotfix_m5` / `viesett_hotfix_current` databases. Logs/results: `.local/demo-date-hotfix/{m5-only,current}-gates/{1..7}.log`, `results.json`; `reproduction-results.json`, `targeted-results.json`, `regression-before.log`, `regression-after.log`. Evidence is local automated testing, not hosted CI.

Clock audit: existing relative auth-expiry/retention/deletion timestamps intentionally track real time; rules/coverage already accept explicit dates. The Retry-After transport test uses a bounded UTC-relative header and accepts an elapsed delay; no second reproducible business-date instability was found. No broad refactor was made.

The task-owned temporary PostgreSQL is stopped after verification; synthetic databases/logs/patch remain private under `.local`. Cleanup/integrity metadata is recorded there. No application server, frontend or external provider was started by this hotfix. No further milestone work began.
