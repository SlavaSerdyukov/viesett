# First web UX — local development

Use Python 3.12+, PostgreSQL and Node 24 LTS (local verification also ran on Node 25.6.1). Install Python dependencies using the existing project-local uv workflow and frontend dependencies with `npm ci --prefix web`. Commit `web/package-lock.json`; never commit `node_modules`, `dist`, test reports, tokens or private files.

The frontend follows the [Vite React setup](https://vite.dev/guide/), [React Router declarative routing](https://reactrouter.com/start/declarative/installation) and [TanStack Query](https://tanstack.com/query/latest/docs/framework/react/overview). It uses native fetch and local CSS/component classes, with system fonts and Lucide icons. There is no external font, UI framework, analytics SDK or Node backend. Pages are separated under `web/src/pages/`; shared presentation/access/API/contracts live alongside them. [Playwright webServer configuration](https://playwright.dev/docs/test-webserver) starts local services for deterministic browser tests.

## Demo launch

Use an empty, dedicated development database and a separate private directory. Example for the local PostgreSQL Unix-socket instance used during implementation (start PostgreSQL separately):

```sh
export PYTHONPATH="$PWD/src"
export VIESETT_DATABASE_URL="postgresql+asyncpg:///viesett_m6_demo?host=$PWD/.local&port=55483"
export VIESETT_STORAGE_ROOT="$PWD/.local/m6-demo-objects"
export VIESETT_DEMO_MODE=true
export VIESETT_ALLOW_DEVELOPMENT_WEB_SESSIONS=true
export VIESETT_BROWSER_SESSIONS_ENABLED=true
export VIESETT_BROWSER_COOKIE_SECURE=false
export VIESETT_ALLOW_DEVELOPMENT_SAFETY=true
export VIESETT_WEB_ORIGINS='["http://127.0.0.1:5173","http://localhost:5173"]'
export VIESETT_SOURCE_MIN_INTERVAL=0
export VIESETT_SOURCE_RETRY_BASE=0
.venv/bin/alembic upgrade head
.venv/bin/uvicorn viesett.demo:create_demo_app --factory --host 127.0.0.1 --port 8000 --no-access-log
```

In another terminal, `npm --prefix web run dev -- --port 5173`. Vite proxies `/api` to the local FastAPI process. Open `http://127.0.0.1:5173`, choose “Explore a sample dossier”, start a private evaluation session and review/confirm the upload attestation/notice for synthetic documents. The sample contains EPC E, electrical non-conformity, missing soil information, co-ownership, approved roof works, €6,000 proportional remaining-basis estimate and questions. No live government service is contacted in this mode.

For development with actual reviewed providers, leave `VIESETT_DEMO_MODE` false and use separately configured provider settings. The preview and private APIs retain existing source safety/legal/deployment limitations. No real customer documents were used for M5 verification.

The optional browser bootstrap issues a random one-hour bearer token only with explicit development opt-in, loopback peer, configured Origin and strict limiter. Production forbids the flags. For an existing dossier, enter its original operator-provisioned token; a new evaluation session is a different account. With browser sessions enabled, access is exchanged for a short-lived HttpOnly cookie and survives reload. The original bearer is not persisted in JavaScript storage. Logout revokes the server session. The explicit non-production Secure=false flag is only for loopback HTTP; private beta requires HTTPS/Secure. With browser sessions disabled, the prior in-memory bearer bridge remains available for compatibility. Public signup, recovery/email verification remain deferred. See [M6 sessions](../private-beta/sessions.md); never put tokens in Vite variables or browser storage.

## Checks

```sh
PYTHONPATH=src .venv/bin/python scripts/generate_web_contract.py --check
npm --prefix web run lint
npm --prefix web run typecheck
npm --prefix web run format:check
npm --prefix web test
npm --prefix web run build
```

`contracts.ts` is generated from response Pydantic schemas; regenerate with `scripts/generate_web_contract.py` after intentional contract changes. It is excluded from hand formatting. The committed UI fixture is a source-safe fictional DTO, not a customer export, credential or bundled runtime dataset.

For browser tests, install Chromium once (`cd web && npx playwright install chromium`), provide a dedicated migrated database, then `npm --prefix web run e2e`. The test config uses synthetic providers, private local storage, a single worker and desktop/tablet/mobile Chromium projects plus critical Firefox/WebKit projects. Session credentials are reused only in test-worker memory to exercise the existing-token bridge without weakening the development session limiter. Traces are disabled; screenshots contain fictional data only. M6 verifies Chromium and WebKit locally. Firefox exits before page creation with a host profile error, including in two alternate temporary directories; its test remains enabled in CI. See [browser verification](m6-browser-print.md) for exact supported-matrix commands and limits. No manual in-app browser execution is claimed.

Vitest uses one thread worker for deterministic local behavior; the default fork setup stalled on this host's Node 25 runtime. Full Chromium resolved a host-specific headless-shell actionability/rendering stall. These choices remain ordinary supported test configurations, without forced clicks or skipped safety checks.


M6 private real-data operation uses the [separate fail-closed profile](../private-beta/deployment.md), not the demo launch above. Create the dedicated demo database before migration; the application never creates databases automatically.
