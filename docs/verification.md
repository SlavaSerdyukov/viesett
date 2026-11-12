# Viesett verification — 2026-11-11

Historical Milestone 1 verification. For the current implementation see [Milestone 2 verification](verification-m2.md).

All seven required local gates passed on the final implementation. **78 tests passed; branch-aware combined coverage: 91.85%** (minimum enforced: 85%). Full run: 44.58 seconds. Ruff checked/formatted 53 Python files; strict mypy checked 42 source/test/migration files.

Environment: macOS, Python 3.12.14, uv 0.13.7, PostgreSQL 15.15. PostgreSQL data and its Unix socket were created exclusively in this project's gitignored `.local/` directory. The temporary test server was stopped after verification. CI/Compose use PostgreSQL 16, not SQLite.

| Exact command | Result |
| --- | --- |
| `uv sync --frozen` | PASS, exit 0; 39 packages checked |
| `ruff check .` | PASS, exit 0 |
| `ruff format --check .` | PASS, exit 0; 53 files formatted |
| `mypy` | PASS, exit 0; strict mode in pyproject.toml |
| `alembic upgrade head` | PASS, exit 0 |
| `alembic check` | PASS, exit 0; no new upgrade operations detected |
| `pytest` | PASS, exit 0; 78 tests, 91.85% coverage |

Commands were invoked sequentially with the following local environment (the Unix-socket database has no remote credentials):

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

The normal Docker-based development environment and commands are documented in the [README](../README.md). Do not point integration tests at a user database: fixtures truncate private tables. Test-generated files use `.local/pytest`, and uv caches use `.uv-cache`.

The initial migration was first applied to an empty PostgreSQL database. `alembic downgrade base` then succeeded; `alembic upgrade head` recreated the empty schema and seeded policies successfully, followed by a clean `alembic check`. Final gates repeated upgrade/check against that migrated database. The API does not create its schema at runtime.

Tests cover ownership/enumeration, document paths/content/size, private keys/downloads, workspace-local deduplication including concurrent uploads, sensitive quarantine/scanner failures, logging and secret-safe errors, AI authority/minimisation/provenance, processor review/no-training, versioned acknowledgements, copyable requests, export scope, physical deletion, storage failures, cleanup reservations and archive/unarchive races. Two race tests were observed failing before the corresponding fixes and passing after them. Config tests run successfully with both CI database environment variables set.

Additional checks: `docker compose config --quiet` passed (exit 0), and the development CLI help was checked using the README's explicit source path. Docker image build/container execution were not verified; the sandbox could not access the local Docker engine socket. No real credentials, paid services, external AI requests or mailbox access were used.

[GitHub Actions](../.github/workflows/ci.yml) contains all required gates and a fresh PostgreSQL 16 service. No Git remote is configured, so **hosted CI has not run** and no hosted-green claim is made. This report records local verification, not public-production approval or Belgian legal review.

Machine-readable local results and per-command output remain in gitignored `.local/verification/results.json` and `.local/verification/1.log` through `7.log`. Coverage XML is generated as gitignored `coverage.xml`. All recorded commands returned zero on the final run.
