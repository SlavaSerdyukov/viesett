# Viesett Milestone 2 verification — 2026-11-11

All seven required local gates passed. **163 tests, 94.54% combined line/branch coverage**, original >=85% threshold unchanged. Ruff lint and formatting passed. Strict mypy: 67 source/test/migration/script files.

| Exact command | Result |
| --- | --- |
| `uv sync --frozen` | PASS, exit 0; package 0.2.0, locked dependencies |
| `ruff check .` | PASS, exit 0 |
| `ruff format --check .` | PASS, exit 0 |
| `mypy` | PASS, exit 0; strict |
| `alembic upgrade head` | PASS, exit 0 |
| `alembic check` | PASS, exit 0; no new upgrade operations |
| `pytest` | PASS, exit 0; 163 tests, 94.54% coverage |

Environment: Python 3.12.14, uv 0.13.7, PostgreSQL 15.15, pyproj 3.8.0, defusedxml 0.7.1. CI/Compose use PostgreSQL 16. Test data, temporary PostgreSQL/socket, cache and logs stay in project-local gitignored directories. The deadline regression uses a deliberately slow mock, not live latency.

Commands ran from repository root with:

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

Separate disposable database `viesett_m2_migrations` verified:

```sh
alembic upgrade 5e1e917449ce
python scripts/verify_milestone_upgrade.py seed
alembic upgrade head
python scripts/verify_milestone_upgrade.py verify
alembic check
alembic downgrade base
alembic upgrade head
alembic check
```

All succeeded. The sentinel verified preservation of an M1 account/workspace and old notice/upload acknowledgements, new notice currentness, unchanged upload-policy version, and actual provenance CHECK constraints. M1 history was not rewritten. Downgrade preserves policy/acknowledgement history while reverting notice currentness; the empty-database test recreated the full chain. CI now includes both paths.

Coverage initially missed resumed ORM execution because its concurrency model omitted greenlet. The [documented coverage.py requirement](https://coverage.readthedocs.io/en/latest/config.html#run-concurrency) is now configured for thread/greenlet. Branch measurement and threshold remain, without added code omissions/exclusions.

The opt-in live CLI was actually invoked with the provider's fixed example address. Result: GRAR UPSTREAM_UNAVAILABLE / transport_unavailable; heritage NOT_APPLICABLE without a live identity. No successful deployed compatibility is claimed. [Source review](integrations/source-review-2026-11-11.md) records documentation/fixture/live distinctions. Normal CI blocks HTTP network transports and does not depend on government availability or PROJ downloads.

The GitHub origin exists. M2 changes have not been committed/pushed or hosted-verified; the inspected foundation workflow was queued. See [implementation report](implementation-report-m2.md). Green results here are local. No deployment, legal approval, paid integration or mailbox access was performed.

Local raw results: `.local/verification/results.json`, `1.log`–`7.log`; `coverage.xml`; `.local/source-review/live-smoke.json`. These are gitignored. An obsolete incomplete local 0.1.0 dist-info artifact was removed after versioning; the final frozen sync is clean. Docker Compose configuration remains valid; container execution was not newly verified.
