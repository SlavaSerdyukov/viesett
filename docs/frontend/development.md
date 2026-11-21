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

The interactive demo searches a finite fictional catalog: **Teststraat 42, 9000 Gent** and **Teststraat 42 bus 1, 9000 Gent**. The second address resolves to a different private unit. A broad `Teststraat` query offers both choices; unrelated addresses show “Address not in the demo,” rather than returning the first sample. This is not a live address search or a new address parser. Late responses from a previous query cannot replace the latest result.

**Delete dossier** is available beside a saved dossier on Start and in the footer of an open dossier. Confirmation names the property and removes the whole dossier/PDF/evidence/history through the existing owner-scoped DELETE API. Cancel preserves the dossier; errors remain visible in the dialog. Success clears that dossier's cache, updates the list, announces deletion and restores focus. It is separate from document-level Delete.

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

## Local diagnostic follow-up, 2026-11-14

The first manual launch disabled raw access logs and had no INFO handler for the existing `viesett.http` logger, so it supplied no retrospective request trace. Direct reproduction showed owner-scoped whole-dossier DELETE **204**, an empty list for the isolated test account and **404** on the deleted dossier; the UI lacked the whole-dossier action. The old demo transport returned the same first property for unrelated queries. The UI/catalog fixes above address those gaps; no user dossier was removed to diagnose them.

The running local instance now writes the existing allowlisted request events to `.local/demo-launch/safe-http.log`: **event, method, status, correlation_id** only. Its task-local logging configuration is not a production logging policy. No raw URLs, queries, headers, tokens, response/document bodies or exception representations are added. Local demo preview rate is bounded at 30/minute (synthetic sources); production/provider defaults are unchanged. Only requests after the restart are recorded.

Verification: **479 backend cases / 92.60% branch-aware coverage**, seven backend gates; **45 frontend tests**, type/lint/format/build; **three Chromium E2E cases** against the running demo, including separate query results, unknown-address messaging, responsive deletion confirmation, actual DELETE 204, list refresh/reload and deleted GET 404. Logs under `.local/demo-fixes/`. The original 80% assertion/date hotfix and README/migrations remain unchanged. This follow-up is local/uncommitted; the prior hosted M6 success predates these changes.

## Source citations and print follow-up, 2026-11-15

Citation responses distinguish `kind`, approved `human_url`, exact `technical_uri`, provider and source identifier from private document/page navigation. The original `uri` remains available in owner-scoped data/export. The backend owns the reviewed destination catalog in `services/source_presentation.py`; the contract generator copies it into `contracts.ts`. Only an exact catalog destination becomes an external link. GRAR links describe the official register, without claiming an object-specific browser deep link. Document citations still use the authenticated private viewer.

The shared citation component groups Evidence separately from Rule / guidance and deduplicates provider/document-page references for display. Since the 2026-11-19 [visibility hotfix](../implementation-report-provenance-visibility.md), shared citations never render technical provenance. Only Evidence offers a closed “Source details” disclosure with known provider/retrieval metadata and permitted registry object numbers. Machine URI facts/identifiers remain in data rather than HTML, even after disclosure. The response's additive fact `key` selects explicit registry-reference fields without matching translated labels or parsing URLs. Version/locator/history remain internal. Print appendices group public sources, documents with sorted distinct pages, and official guidance; no technical appendix is added. Display grouping does not alter evidence relationships or authority.

**Prepare for notary** opens `/workspaces/{id}/notary`: a dedicated current-information handoff with important unresolved findings, concise gaps/applicability, co-ownership/current funds/approved works, existing financial estimates and assumptions, only NOTARY questions, and the source appendix. **Print full dossier** opens `/workspaces/{id}/print` and retains the detailed checklist, Article 3.94 information and all question groups. The notary page has no interactive details to expand. Neither view recomputes domain decisions or truncates findings to achieve a page count.

Both native print actions explain how to disable browser “Headers and footers”; that help is hidden during printing. Browser-generated headers remain a user print setting. No server PDF renderer is added. The demo services were stopped at the user's request before this work; Playwright starts and stops isolated test services only.

Verification, source URL review and measured three-page notary / twelve-page full synthetic PDFs: [focused hotfix report](../implementation-report-source-notary-fix.md). The earlier launch/test measurements above remain historical.
