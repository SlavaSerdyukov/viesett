# Milestone 3 verification — 2026-11-12

All seven local gates passed: **271 tests, 93.79% combined branch-aware coverage**. The 163 M1/M2 cases remain green; 108 cases were added in M3. Threshold remains >=85%, branch coverage enabled, SQLAlchemy thread/greenlet concurrency retained. No production code exclusions were added. Normal tests block live HTTP transports and require no government access, OCR binary, paid service or AI key.

| Required command | Final result |
| --- | --- |
| `uv sync --frozen` | PASS, exit 0; 43 packages checked |
| `ruff check .` | PASS, exit 0 |
| `ruff format --check .` | PASS, exit 0 |
| `mypy` | PASS, exit 0; strict, 87 files |
| `alembic upgrade head` | PASS, exit 0 |
| `alembic check` | PASS, exit 0; no new upgrade operations |
| `pytest` | PASS, exit 0; 271 tests in 25.31s, coverage 93.79% |

Commands run from the existing repository with project-local tools and dedicated test PostgreSQL:

```sh
export PATH="$PWD/.bootstrap/bin:$PWD/.venv/bin:$PATH"
export UV_CACHE_DIR="$PWD/.uv-cache"
export UV_PYTHON_DOWNLOADS=never
export VIESETT_DATABASE_URL='postgresql+asyncpg:///viesett_test?host=/Users/slavaserdukov/Desktop/dev/viesett/.local&port=55483'
export VIESETT_TEST_DATABASE_URL="$VIESETT_DATABASE_URL"
uv sync --frozen
ruff check .
ruff format --check .
mypy
alembic upgrade head
alembic check
pytest
```

Separate disposable `viesett_m3_migrations` database successfully ran:

```sh
alembic upgrade 5e1e917449ce
python scripts/verify_milestone_upgrade.py seed
alembic upgrade da321bc669fb
python scripts/verify_milestone_upgrade.py verify
python scripts/verify_m3_upgrade.py seed
alembic upgrade head
python scripts/verify_m3_upgrade.py verify
alembic check
alembic downgrade da321bc669fb
alembic upgrade head
alembic check
alembic downgrade base
alembic upgrade head
alembic check
python scripts/verify_m3_upgrade.py guard
```

All succeeded. The last command intentionally checks that nonempty M3 prevents downgrade, without changing revision/data, then removes its synthetic sentinel. The positive downgrade paths contain no M3 dossier data. Existing M1 account/workspace/acknowledgements and M2 property/two parcels/document/page evidence/finding/acknowledgements were verified before synthetic cleanup. M1/M2 migration bytes remain unchanged. CI now runs the same chain plus the guard and all existing gates. Hosted CI for local M3 changes has not run; no hosted-green claim is made.

Local environment: Python 3.12.14, uv 0.13.7, PostgreSQL 15.15; CI PostgreSQL 16. `pypdf` 6.21.4 is locked. Local Unix socket only, no new TCP listener. Raw gate logs/results and migration command records: `.local/verification-m3/`; generated coverage: `coverage.xml`, all gitignored. Earlier M1/M2 verification reports remain historical.

An inspected obsolete local `viesett-0.2.0.dist-info` directory containing duplicated metadata filenames without a RECORD was removed after the version upgrade. The current 0.3.0 installation has a valid RECORD; final frozen sync completed cleanly. The temporary project-local PostgreSQL server was stopped after verification.

Four fictional PDFs were generated from `tests/document_fixtures.py`, rendered with macOS `sips` and visually inspected under `.local/pdf-qa/`. All fields/headings are readable; no customer PDF or official sample PDF was copied. Rendering is development QA only; runtime/CI uses Python without Poppler, Tesseract or other PDF binaries.

Official VEKA/Vlaanderen, OVAM and FOD Economie/AREI documentation was read for every regulatory code. This verifies the reviewed public rule descriptions, not legal counsel approval or real customer-document accuracy. No M3 live registry/API lookup was needed/performed. M2 transport failure was not reworked; deployed GRAR/heritage compatibility retains its previously documented limitation. See [source review](rules/source-review-2026-11-11.md).

Root README SHA-256 before/after M3: `3b7508969c50367fa3477b0685b051b241530cf8ec0a14ccec40b0b4edd0bdac`. Its preexisting M2 working-tree changes were preserved. No README edit, commit, push, deployment or Milestone 4 work was performed.
