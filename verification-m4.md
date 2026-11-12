# Milestone 4 verification — 2026-11-12

Final results below cover the existing repository plus M4. Root README and all three prior migrations are unchanged. Detailed implementation boundaries: [M4 report](docs/implementation-report-m4.md).

## Before implementation

Entry tree clean at `531a042b6aabe294516dd0818c21742f6bb58eff`. All seven baseline commands passed before application changes: **271 tests, 93.79% combined branch-aware coverage**. Baseline logs: `.local/verification-m4-baseline/` (gitignored).

## Final gates

**379 tests passed in 38.17s; combined branch-aware coverage 94.00%.** Added 108 M4 cases; all 271 prior cases pass. Every final command returned exit 0.

| Command | Result |
| --- | --- |
| `uv sync --frozen` | PASS, 43 packages checked; local project 0.4.0 |
| `ruff check .` | PASS |
| `ruff format --check .` | PASS |
| `mypy` | PASS, strict, 106 source/test/migration/script files |
| `alembic upgrade head` | PASS, `d64802d3610f` |
| `alembic check` | PASS, no new upgrade operations |
| `pytest` | Final exact count/coverage above; exit 0 |

Run from `viesett` with dedicated local test PostgreSQL (Unix socket only):

```sh
export PATH="$PWD/.bootstrap/bin:$PWD/.venv/bin:$PATH"
export UV_CACHE_DIR="$PWD/.uv-cache"
export UV_PYTHON_DOWNLOADS=never
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

No existing tests removed. Threshold remains >=85%; branch measurement and SQLAlchemy thread/greenlet support remain enabled. No production coverage omissions/exclusions were added. Normal tests block live HTTP and need no keys, government service, AI provider or OCR executable. Synthetic NL/FR fixtures only; no real apartment minutes/accounting were committed. Logs and exit codes: `.local/verification-m4/{1..7}.log`, `results.json`; coverage: `coverage.xml` (all gitignored). The final run occurs after code changes; earlier intermediate runs are not substituted for it.

## Migration chain and preserved M3 data

All **23 commands** below passed against disposable migration databases. The final strengthened sentinel was rerun on `viesett_m4_migrations_final` with nonempty M3 structured fields; normal regression tests use `viesett_m4_migrations`:

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
alembic upgrade head
python scripts/verify_m4_upgrade.py verify
python scripts/verify_m4_upgrade.py guard
alembic check
alembic downgrade 192e0442ffc8
python scripts/verify_m4_upgrade.py verify-m3
alembic upgrade head
python scripts/verify_m4_upgrade.py verify
python scripts/verify_m4_upgrade.py cleanup
alembic downgrade da321bc669fb
alembic upgrade head
alembic downgrade base
alembic upgrade head
alembic check
```

The new sentinel preserves actual synthetic private source/artifact bytes and M3 analysis, evidence, rule finding, evaluation, old privacy text and acknowledgement. These survive both M4 upgrade and M4 → M3 downgrade. Guard subprocesses intentionally reject nonempty M4 evaluation or a manual-kind-only M4 analysis, preserving the head revision/data atomically. Full downgrade is checked after removing synthetic dossier data; it is not a promise of destructive downgrade with private data. Old M1/M2 preservation checks and M3 guard remain in CI. Normal regression tests use the earlier disposable migration database; the strengthened nonempty-field sentinel was then repeated on a fresh database. Static lint/format/type checks passed again after that sentinel refinement. Migration logs: `.local/verification-m4-migrations/` and final strengthened sentinel logs `.local/verification-m4-migrations-final/`.

## Integrity, official sources and hosted status

SHA-256 before/after:

| File | Unchanged SHA-256 |
| --- | --- |
| Root README | `3b7508969c50367fa3477b0685b051b241530cf8ec0a14ccec40b0b4edd0bdac` |
| M1 `5e1e917449ce` | `c418dbdef0df8a099f7ba6e0439a3c3d3cafdd25148f5e7ef6f425888067785d` |
| M2 `da321bc669fb` | `3d062e3967b8f81be5ea287f377029a74602ec415d0162b0f9ea1d5906255c99` |
| M3 `192e0442ffc8` | `ddc193dfa3f18de3a421e1ca73c3d1e150987b97d31d8730fbba69522bbe810a` |

Official current consolidated Book 3 was successfully fetched/read over HTTPS, after a browser-tool failure on the same URL. The official header states update through 16-02-2026. Official Fednot guidance was also read. This verifies documented baseline/source text, not counsel approval, live real-document accuracy or legal payment responsibility. [Source review](docs/rules/source-review-2026-11-12-m4.md) records exact links/version/hash. No new registry integration, real customer document, paid service, LLM or external OCR was invoked. Existing M2 live-service limitations remain unchanged.

M4 changes are local and uncommitted. No hosted M4 run was triggered. Connected GitHub returned no PR-triggered workflow runs for base `531a042`; its tool filters PR events, so push-run status was not established. CI configuration preserves all prior gates and adds M4 preservation/guard/downgrade checks. No hosted-green claim, commit, push or deployment.

Local Python 3.12.14, uv 0.13.7, PostgreSQL 15.15; CI PostgreSQL 16. Runtime dependencies unchanged except project version; lockfile updated to 0.4.0. The temporary project-local PostgreSQL server started for this task is stopped after verification; source and unrelated databases are retained.
