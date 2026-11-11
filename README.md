# Viesett

Viesett is Flanders-first, privacy-first, buyer-side residential property due-diligence software. This repository is Milestone 1: a backend foundation, **not yet a public production service**.

Viesett is not a real-estate brokerage, Belgian notary or mortgage intermediary. It does not negotiate, provide legal advice or submit binding offers. Users upload only relevant property documents. There is no mailbox access or automatic communication: generated seller/agent/notary request text is copied and sent by the user. Customer documents and dossiers are not used to train AI models.

## Local development

Requires Python 3.12+, [uv](https://docs.astral.sh/uv/) and Docker Compose (or a dedicated PostgreSQL 15+ installation).

If uv is unavailable globally, keep it inside this project: `python3.12 -m venv .bootstrap`, then `.bootstrap/bin/python -m pip install --no-cache-dir uv==0.13.7`. The PATH below prefers that local installation when present.

```sh
export PATH="$PWD/.bootstrap/bin:$PATH"
cp .env.example .env
uv sync --frozen
docker compose up -d db
set -a
. ./.env
set +a
export PYTHONPATH="$PWD/src"
uv run alembic upgrade head
uv run viesett create-account
uv run uvicorn viesett.api.app:create_app --factory --host 127.0.0.1 --port 8000 --no-access-log
```

The provisioning command prints an opaque bearer token once. Store it securely; it expires after 24 hours by default. No registration, passwords, email address or other profile PII is required. Do not paste the token into logs or commit it. Provisioning is disabled in production. Use the returned token in `Authorization: Bearer …` through a local API client. Development API docs: `http://127.0.0.1:8000/docs`.

`Settings` reads environment variables; `.env` is deliberately sourced explicitly above rather than discovered from arbitrary working directories. All local private objects and tool caches are gitignored.

The explicit development `PYTHONPATH` imports the working tree and also handles macOS Python installations that skip an editable-install `.pth` marked hidden. Tests configure their `src` path directly; Linux containers use the installed package normally.

## Initial workflow

1. `POST /api/v1/workspaces` with `{}` or `{"canonical_address":"…"}`.
2. `GET /api/v1/policies`, then `POST /api/v1/me/policy-acknowledgements` with `{"policy_version_id":"…"}` for the current `UPLOAD_ATTESTATION`. Acknowledge notice/terms separately as appropriate; none is universal GDPR consent.
3. Upload raw PDF bytes with `POST /api/v1/workspaces/{id}/documents`, `Content-Type: application/pdf`, `X-Filename: epc.pdf`, optional `X-Document-Kind: EPC`. This is a binary request, not multipart. PDFs only in this milestone; default maximum 10 MiB, request maximum 11 MiB.
4. Get document metadata, evidence or findings through workspace routes. `GET …/documents/{id}/content` requires current authentication and `READY` status. Files are forced attachments with private/no-store responses. There are no public or presigned object URLs.
5. `POST …/document-request-draft` with `{"requested_document_types":["EPC","SOIL_CERTIFICATE"],"language":"en"}`. English and Dutch templates are deterministic. There is no send action.

By default, the unavailable scanner quarantines every upload. The example development configuration explicitly opts into deterministic safety doubles so local property PDFs can become `READY`. **These doubles are not antivirus, OCR or reliable identity-document detection.** Production refuses to start with them. No production safety provider or AI provider is supplied.

## Tests and migrations

Tests truncate the configured database: always use the dedicated `viesett_test` database.

```sh
docker compose exec db createdb -U viesett viesett_test
export VIESETT_TEST_DATABASE_URL=postgresql+asyncpg://viesett:development-only@localhost:5432/viesett_test
VIESETT_DATABASE_URL="$VIESETT_TEST_DATABASE_URL" uv run alembic upgrade head
uv sync --frozen
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run alembic upgrade head
uv run alembic check
uv run pytest
```

The last migration commands operate on `VIESETT_DATABASE_URL`; `pytest` operates on `VIESETT_TEST_DATABASE_URL`. CI uses fresh PostgreSQL, strict mypy and branch-aware coverage >=85%. Migration `5e1e917449ce` creates all tables and seeds initial draft policies; the application never calls `create_all`.

## Deletion, export and retention

`DELETE …/documents/{id}`, `DELETE …/workspaces/{id}` and `DELETE /api/v1/me` remove private content and dependencies. File deletion removes linked evidence/findings and invalidates workspace request drafts. Account deletion also revokes tokens. Successful deletion verifies physical cleanup. If storage fails, data remains inaccessible and a durable task survives; the API reports 503 pending cleanup rather than claiming complete erasure.

`GET /api/v1/me/export` returns caller-only account, versioned acknowledgements, workspaces, document metadata, structured evidence, findings with references, and request drafts. It excludes tokens, storage keys, private binaries and external processor administration. Download ready files separately before deleting them. Quarantined files are not downloadable through ordinary APIs; rejected bytes are removed immediately.

Archive/unarchive with `PATCH …/workspaces/{id}` and `{"status":"ARCHIVED"}` / `{"status":"ACTIVE"}`. Archive purge is disabled unless `VIESETT_ARCHIVED_RETENTION_DAYS` is explicitly set. Run `uv run viesett purge` from a scheduler to process expired archives and durable cleanup tasks. Schedule at least every ten minutes when running the service. No statutory retention period is invented.

## Project map

`src/viesett/` contains `api`, `core`, `domain`, `db`, `storage`, `document_safety`, `services` and `ai`. See [architecture](docs/architecture.md), [boundaries](docs/product-boundaries.md), [document handling](docs/security/document-handling.md) and [verification report](docs/verification.md). All [privacy drafts](docs/privacy/privacy-notice-draft.md), the Terms and third-party-data design require Belgian legal/privacy review before public beta.

Next milestone: Flemish property resolution and explicitly approved official/public data enrichment. No public-data integration, portal scraping, OCR, paid LLM, rule engine or frontend is implemented here.
