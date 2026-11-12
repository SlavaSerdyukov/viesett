# Milestone 5 verification — 2026-11-12

Viesett **0.5.0**, Buyer Dossier + Product API + First Web UX. [Implementation report](docs/implementation-report-m5.md), [architecture](docs/product/architecture.md), [local development](docs/frontend/development.md). README and M1–M4 migration bytes are unchanged. No M6, commit, push or deployment.

## Verification boundaries

| Class | Actual result |
| --- | --- |
| Automated backend | **409 passing cases, 93.85% combined branch-aware coverage**, 44.71s; all 379 earlier cases retained |
| Automated frontend | **30 tests** across two files, 3.46s; typecheck/lint/format/build pass |
| Automated local browser | **6 Playwright passes**, 14.3s: two journeys × desktop/tablet/mobile; local backend and fictional PDFs/providers |
| Accessibility | Selected sample Overview scenarios: axe WCAG A/AA tags, zero violations at the three tested viewports; not a full accessibility certification |
| Manual visual inspection | Inspected automated desktop/mobile Overview and notary-handoff screenshots; no manual in-app browser interaction claimed |
| Live external-source verification | None in M5. No government API, real private PDF, live AI, paid service or external OCR used |
| Implemented, not live-verified | Real GRAR/heritage compatibility remains subject to prior M2 limits; real-world document layouts and native PDF behavior across browsers remain unverified |
| Deferred | Public authentication, reviewed public-beta operation, arbitrary PDF/OCR/AI, external sharing/sending and M6 |

The in-app Browser runtime returned no available browsers after bootstrap/troubleshooting. The requested Playwright E2E suite supplied automated local browser verification. Screenshots are fictional and gitignored under `web/test-results/`; this is not evidence of live official property information.

## Preflight and backend gates

Entry tree was clean at `d9c75c2` (`m4 deep check docs`). Inspected the existing diff, M1–M4 migrations/reports, domain/services/routes and export/deletion/auth before edits. Seven baseline gates passed before application changes: **379 cases, 94.00% branch-aware coverage**, 37.71s. Logs: `.local/verification-m5-baseline/`.

All final backend commands returned exit 0:

| Command | Result |
| --- | --- |
| `uv sync --frozen` | PASS; project rebuilt as 0.5.0, runtime dependencies unchanged |
| `ruff check .` | PASS |
| `ruff format --check .` | PASS |
| `mypy` | PASS, strict; 120 files |
| `alembic upgrade head` | PASS, `f51e9bf1a005` |
| `alembic check` | PASS; no new upgrade operations |
| `pytest` | **409 passed, 93.85%, 44.71s** |

Exact local environment/commands, from repository root with the dedicated synthetic test PostgreSQL instance already running:

```sh
export PATH="$PWD/.bootstrap/bin:$PWD/.venv/bin:$PATH"
export UV_CACHE_DIR="$PWD/.uv-cache"
export UV_PYTHON_DOWNLOADS=never
export PYTHONPATH="$PWD/src"
export VIESETT_DATABASE_URL="postgresql+asyncpg:///viesett_m4_migrations?host=$PWD/.local&port=55483"
export VIESETT_TEST_DATABASE_URL="$VIESETT_DATABASE_URL"
uv sync --frozen
ruff check .
ruff format --check .
mypy
alembic upgrade head
alembic check
pytest
```

Logs: `.local/verification-m5/{1..7}.log`, exit codes in `results.json`, source hashes in `final-source-hashes.json`, coverage in `coverage.xml` (all gitignored). Threshold remains **85%**, branch collection and SQLAlchemy thread/greenlet coverage remain. No production exclusions or existing-test removals. Normal tests block live HTTP. Product tests add 30 cases for preview states/privacy/rates, independent selections, automatic intake, aggregate/citations/idempotence, owner/PDF isolation, completeness, demo labels/production guards, unresolved-property recovery, current associations and source-generation consistency.

## Frontend gates and build

From repository root:

```sh
npm ci --prefix web
PYTHONPATH=src .venv/bin/python scripts/generate_web_contract.py --check
npm --prefix web run typecheck
npm --prefix web run lint
npm --prefix web run format:check
npm --prefix web test
npm --prefix web run build
```

Frozen install completed with **267 packages**. npm reported unapproved install scripts for esbuild/fsevents under the local npm policy; no approval bypass was used and the subsequent build succeeded. `web/package-lock.json` is committed source; no dependency directory or build output is included. Contract generation/check is deterministic and response-only. The frontend test fixture is synthetic and excluded from the runtime bundle.

Final frontend results: typecheck, ESLint and Prettier pass; **30 tests / 2 files pass in 3.46s**; Vite build **845ms**. Output: HTML **0.59 kB** (gzip 0.36), CSS **19.83 kB** (gzip 5.12), JavaScript **347.65 kB** (gzip 108.63). No chunk-size waiver or lowered checks. Logs: `.local/m5-frozen-install.log` and `.local/verification-m5-web/{typecheck,lint,format,tests,build}.log`.

Resolved primary versions: React/React DOM 19.3.1, TypeScript 5.9.3, Vite 7.3.8, Router 7.18.5, TanStack Query 5.107.1, Lucide 0.577.0. Tooling: Vitest 4.1.12, Playwright 1.65.0, axe integration 4.14.0, ESLint 10.14.0. The lockfile pins transitive dependencies.

## Browser journeys

The final server used a new dedicated database `viesett_m5_demo_final` and object root `.local/m5-demo-final-objects`, migrated to head, with explicit synthetic-provider/development-session/safety flags. See [launch configuration](docs/frontend/development.md). It bound only to `127.0.0.1:8000`, with request access logging off. Playwright started/stopped the local Vite server. One test worker, no retries, no traces or forced clicks. Credentials were reused only in worker memory through the actual token-entry UI, preserving the five-per-minute bootstrap limiter.

Final command, from `web/` after the local browser download:

```sh
PLAYWRIGHT_BROWSERS_PATH=../.local/playwright npm run e2e
```

**6 passes in 14.3s**, log `.local/verification-m5-web/e2e-final.log`. Projects: desktop 1440×1050, tablet 900×1100, Pixel 7 mobile emulation. Two scenarios per project:

1. Enter fictional address → official-shaped preview → private evaluation/dossier → upload fixture PDF with current attestation → automatic analysis → finding → question → authenticated Blob PDF with target page → notary print route. Checks no persistent browser token and no external network request from the page.
2. Full fictional apartment dossier → completeness → selected axe audit/no horizontal page overflow → co-ownership estimate/assumptions/undetermined responsibility → evidence → return to Overview. Screenshot waits for the actual route; bounded page height prevents stale Evidence capture from being mistaken for Overview.

Inspected the resulting desktop/mobile Overview viewport captures and desktop notary handoff capture for layout. Native browser PDF page handling is only checked through the authorized Blob URL, iframe and visible target-page indicator; there is no pixel-level PDF rendering/highlight claim. Browser print action/route and print CSS exist; exhaustive printer pagination and all browser engines are unverified. Full Chromium was used because headless-shell stalled on this host; Vitest uses a single thread because default forks stalled on Node 25. Neither workaround skips product checks.

## Migration preservation

All **32 commands** below passed on a separate disposable `viesett_m5_migrations` database. Use the same environment as above with both database variables set to that database:

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
alembic upgrade head
python scripts/verify_m5_upgrade.py verify
python scripts/verify_m5_upgrade.py guard
alembic check
alembic downgrade d64802d3610f
python scripts/verify_m5_upgrade.py verify
alembic upgrade head
python scripts/verify_m5_upgrade.py verify
python scripts/verify_m5_upgrade.py cleanup
alembic downgrade da321bc669fb
alembic upgrade head
alembic downgrade base
alembic upgrade head
alembic check
```

The M5 sentinel seeds a valid synthetic typed M4 evaluation. Upgrade, guarded atomic refusal with demo data, M5→M4 preservation, empty-schema head upgrade and safe full downgrade after sentinel cleanup pass. Prior M1/M2/M3/M4 sentinel/guard paths remain. Only `demo_workspaces` is new; previous notices and acknowledgements are unchanged. Logs/exit codes: `.local/verification-m5-migrations/{1..32}.log` and `results.json`.

## Integrity, privacy and cleanup

Compared repository files with entry HEAD; unchanged SHA-256:

| File | SHA-256 |
| --- | --- |
| README | `3b7508969c50367fa3477b0685b051b241530cf8ec0a14ccec40b0b4edd0bdac` |
| M1 `5e1e917449ce` | `c418dbdef0df8a099f7ba6e0439a3c3d3cafdd25148f5e7ef6f425888067785d` |
| M2 `da321bc669fb` | `3d062e3967b8f81be5ea287f377029a74602ec415d0162b0f9ea1d5906255c99` |
| M3 `192e0442ffc8` | `ddc193dfa3f18de3a421e1ca73c3d1e150987b97d31d8730fbba69522bbe810a` |
| M4 `d64802d3610f` | `172fe597ac4cfc8487cd22c9bb3d5033a44cd981f93706028bcbc31bfb39da2d` |

Owner-only dossier/PDF/print data, private/no-store responses, source authority and deletion/export cascades remain covered. Preview does not create accounts/workspaces/evidence/history. No public file links, raw extracted-text logging, customer training, new processor, external analytics, live AI, mailbox or automatic communication is added. Privacy drafts receive scoped M5 clarifications; persisted M4 notice/upload acknowledgement behavior is unchanged. Public legal/operational review remains pending.

Automatic approval review rejected a proposed relocation of debug-demo objects from shared `.local/objects` because ownership of every source object was not proved. The move was not executed or retried. A new isolated demo database/root completed verification; earlier objects/databases remain intact. This rejection did not leave any requested M5 function blocked.

The task-owned loopback demo server and temporary Unix-socket PostgreSQL server are stopped after final checks. Synthetic databases/files/logs remain local and gitignored; no shared files or unrelated service processes are removed. Local Python 3.12.14, uv 0.13.7, PostgreSQL 15.15, Node 25.6.1; CI targets Python 3.12/PostgreSQL 16/Node 24.

CI preserves all Python gates and prior migration sentinels, adds M5 preservation/guard and frozen frontend/contract/quality/build/Chromium E2E gates. Results above are **local**, not a hosted-GitHub-green claim. M5 is uncommitted and no hosted M5 run was triggered or inspected. No commit, push, deployment or M6 work.
