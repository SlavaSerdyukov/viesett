# Viesett hotfix — source citations and notary handoff

2026-11-15. Presentation/API-projection work on 0.6.0, before any further milestone. Entry: `main` at `7bf0e30586f503d581750c73394611bd5a2230e7`, with existing uncommitted demo-search and whole-dossier deletion fixes. Those changes were preserved. The user-facing demo API/Vite processes were stopped before editing; test services use isolated synthetic accounts/data. No commit, push or deployment.

1. **Raw API links — root cause.** The old shared `Citations` rendered any `https://` value in `uri` directly as a primary anchor. The field described provenance, not a reviewed browser destination. All official evidence also received one generic label. The existing demo fixture contains identifier URIs, rather than the user's example API URI; both URI shapes are covered by the regression. Reproduction found eight generic official labels within individual findings, repeated document-page references, and 69 generic-register labels in the prior ten-page print sample.

2. **Source presentation architecture.** Additive response-only `CitationResponse` metadata: `kind`, `human_url`, `technical_uri`, `provider`, `source_identifier`; existing label/document/page/URI/retrieval fields remain. Kinds include DOCUMENT, OFFICIAL_REGISTER, RULE_AUTHORITY and PUBLIC_INFORMATION, plus USER_CONTEXT and DERIVED so unverified/derived information does not become a public registry. `present_citation` decorates dossier projections using one exact destination catalog; the existing contract generator exports the same catalog to TypeScript. No storage key, schema/migration, fetch, new evidence authority or persistence semantics is added.

3. **GRAR — human versus technical.** The primary label is “Official Flemish Address Register” with the reviewed [Vlaanderen dataset page](https://www.vlaanderen.be/datavindplaats/catalogus/gebouwen-en-adressenregister). It describes the source and is not represented as an exact-object deep link. The original API/identifier URI, source identifier and retrieval metadata remain available in the response and collapsed “Technical source” details as plain text. Unknown/arbitrary HTTPS, protocol-relative, userinfo, javascript/data and modified catalog URLs are not promoted into clickable links. Exact known rule/guidance destinations for OVAM, VEKA/Vlaanderen, FOD Economie and Justel are handled separately. Private document citations still navigate to the existing authenticated Viesett viewer/page.

4. **Semantic deduplication.** The display groups official evidence by provider, documents by document ID/page, and guidance by approved destination. Retrieval timestamps and different official object URIs no longer create repeated provider pills. Every original reference remains in the group; unique technical URI/identifier/retrieval combinations remain inspectable. Underlying citation arrays, evidence IDs and evidence relationships are not collapsed or deleted.

5. **Evidence versus rule authority.** Shared citations explicitly group “Evidence” and “Rule / guidance”. This applies to Findings, Questions, Evidence/co-ownership references, full print and compact notary references. A document or official address observation supports a fact; the separately labeled official guidance supports a check. Unverified buyer context retains its label and status.

6. **Source appendix.** Replaces the flat source list with “Official registers and public sources”, “Uploaded documents” and “Rules and official guidance”. Documents appear once with sorted distinct cited page links. Public provider rows preserve supplied attribution/retrieval and reviewed reuse references. An additional “Other evidence” group prevents buyer context/derivations being mislabeled as official sources. Sources occur once per semantic group; repeated references across separate findings remain useful traceability. Notary print uses two columns within appendix lists, with wrapping and intact list entries.

7. **Oversized handoff — root cause.** “Prepare for notary” previously opened the full print route. That page sequenced interactive findings, the complete requirements presentation, all supplied documents, full co-ownership components and every question group; its layout effect opened all details. It had no separate professional handoff selection/presentation. Smaller text alone would not resolve that structure.

8. **Dedicated notary architecture.** `/workspaces/{id}/notary` uses `NotaryHandoff` and pure presentation selectors. It includes property identity/resolution/staleness; existing information coverage and gap/open-applicability counts; unresolved WARNING/REVIEW/BLOCKING_DATA_GAP findings with explanation, clarification and compact sources; concise missing/conditional information; unverified buyer context where present; co-ownership/share/current funds/approved works/calls/litigation; existing exposure/assumptions; NOTARY questions; grouped sources and the existing disclaimer. INFO is omitted. There is no full requirements/component table, unchanged interactive `FindingCard`, details widget or details-opening effect. A bounded DTO notice remains visible when applicable; a 25-matter regression verifies that no frontend page-count cap silently drops findings.

9. **Full dossier.** `/workspaces/{id}/print` remains separately accessible via “Print full dossier”. It retains all current findings, detailed requirements/deferred disclosure, supplied documents, full co-ownership package, calculations/assumptions and all question groups. Its prior details-opening behavior now excludes technical-source details; technical references remain available on screen and in the private data/export, without a printed URI dump. Both routes share print actions/disclaimer and the new appendix. Full and notary content are distinct.

10. **Question filtering and finance.** The notary handoff filters exactly `target_role === "NOTARY"`. Seller/agent/syndic groups remain in the full dossier. The demo retains its €120,000 project cost, €40,000 explicit project funding, 75/1000 share, €80,000 remaining financing basis, €9,000 gross proportional amount and €6,000 existing estimate. All supplied assumptions and “Legal payment responsibility: Not determined” remain visible. Missing/conflicting allocation states do not acquire a precise estimate. No completeness, due-diligence, co-ownership, calculation, parser, resolution, authority or privacy logic was changed.

11. **Browser headers and print UX.** Both actions still call native `window.print()`. Pre-print help says to disable “Headers and footers” in browser print settings; print media hides that help and controls. CSS cannot reliably disable the browser's date/title/URL/page-count headers, and no guarantee is made. Print CSS preserves card/list entries, keeps headings with following content, wraps sources and hides technical details/navigation. The notary output is concise through content selection/layout, with 12px primary print text. No server PDF renderer was introduced.

12. **Files changed in this task.** Backend/projection: `src/viesett/domain/product.py`, `src/viesett/services/dossier.py`, new `src/viesett/services/source_presentation.py`, `scripts/generate_web_contract.py`. Frontend data: generated `web/src/contracts.ts`, citation-display-only changes to `web/src/test-fixture.json`. Shared presentation: `web/src/components.tsx`, new `SourceCitations.tsx`, `sources.ts`, `print-presentation.ts`, `PrintActions.tsx`, and `styles.css`. Pages: `Dossier.tsx`, `Overview.tsx`, `Print.tsx`, new `Notary.tsx`. Verification: new `tests/test_source_presentation.py`, new `web/src/source-presentation.test.tsx` / `notary.test.tsx`, updated `App.test.tsx` / `web/e2e/journey.spec.ts`. Documentation: this report and `docs/frontend/development.md`. Previous demo fix files remain, including their deletion/search tests. README, private PDF viewer, demo date hotfix, rules/calculators/parsers/official adapters, migrations, workflow and privacy documents remain byte-identical to entry.

13. **Backend verification.** All seven backend gates pass: frozen offline sync, Ruff check/format, mypy, head migration, `alembic check`, full pytest. **489 passed, 69.87s; 92.64% branch-aware coverage**, threshold unchanged at 85%, no new exclusions. Ten new cases cover exact raw API/identifier preservation, safe human destinations, unknown URLs, known provider destinations, rule distinction and a real local API/DB projection test proving stored official provenance/authority/locators remain unchanged. Existing 479 cases include the deterministic 80% demo/date regressions and prior search/deletion fixes. Python 3.12; PostgreSQL 15.15 locally. No live property/document/AI calls in tests.

14. **Frontend verification.** Generated-contract check, typecheck, lint, format, unit tests and production build pass. **65 tests across six files**, retaining all 45 entry cases. Twenty new cases cover provider/document-page deduplication, approved/unsafe/legacy URLs, technical details, private viewer links, evidence/guidance grouping, appendix pages, distinct routes, important findings, NOTARY-only questions, concise gaps, unchanged input data, €6,000/assumptions/responsibility, unavailable estimates, native print/help and untruncated larger input. Runtime dependencies/lockfile/coverage policy are unchanged.

15. **Browser and print checks.** **Eight locally supported Playwright journeys pass**: three desktop Chromium (including whole-dossier deletion and distinct demo search), two tablet, two mobile and one critical WebKit. The new handoff checks important section presence/absence, safe source anchors, source appendix, exact responsibility and print-hidden help; desktop axe checks pass. The existing print scenario generates both PDFs and asserts a loose five-page handoff ceiling plus fewer pages/bytes than full print, without an exact page-count assertion. All three desktop cases pass again after the final print-only layout adjustment. The earlier five responsive/WebKit passes cover identical application logic; that final adjustment changes only print background/appendix columns. Local Firefox has the already documented M6 host profile launch limitation and was not re-run here; no new hosted-CI or Firefox result is claimed. No forced clicks/retries or manual in-app-browser claim.

16. **Measured synthetic output and visual QA.** Final notary PDF: **3 A4 pages, 331,416 bytes**. Full dossier: **12 pages, 529,071 bytes**. Notary has six important matters, two confirmed information gaps, three unresolved applicability checks, one notary question and the existing financial estimate/assumptions. Both retain 80% scenario coverage and one disclaimer. PDF text checks confirm no raw GRAR API URI or print-help text; notary has no seller question group/full Article 3.94 table, while full print retains them. All **15 final pages** were rendered with macOS CoreGraphics and visually inspected for clipping, split content, headings, source wrapping and disclaimer; an initial footer-only fourth handoff page was corrected before final QA. These are synthetic Chromium-generated examples, not physical-printer or cross-browser pixel certification. Private artifacts/logs remain ignored under `.local/source-notary-fix/`.

17. **README and preservation.** **README changed: no**, byte-identical to entry and HEAD; SHA-256 `3b7508969c50367fa3477b0685b051b241530cf8ec0a14ccec40b0b4edd0bdac`. Entry hashes/diff and final integrity evidence are retained privately. No reset/clean/discard, new milestone, schema migration, commit/push or deployment. The demo evaluation date remains 2026-11-12 at the existing service boundaries. Demo data is preserved; services remain stopped after verification.

## Commands and local evidence

Backend runner: `.local/source-notary-fix/run_gates.py current`; logs `current-gates/1.log` … `7.log` and `results.json`. It uses the existing synthetic `viesett_hotfix_current` database on the local Unix socket/port 55483, not the interactive demo database.

```sh
uv sync --frozen --offline
uv run --no-sync ruff check .
uv run --no-sync ruff format --check .
uv run --no-sync mypy
uv run --no-sync alembic upgrade head
uv run --no-sync alembic check
uv run --no-sync pytest
PYTHONPATH=src .venv/bin/python scripts/generate_web_contract.py --check
npm --prefix web run typecheck
npm --prefix web run lint
npm --prefix web run format:check
npm --prefix web test
npm --prefix web run build
```

Frontend logs/results: `.local/source-notary-fix/frontend-gates/`. Playwright uses a separately created/migrated `viesett_sources_notary_test` database and synthetic providers, private test storage, one worker, zero retries; API/Vite processes are owned by Playwright and stopped on completion. From `web/`, with `VIESETT_DATABASE_URL` pointed at that local database:

```sh
PLAYWRIGHT_BROWSERS_PATH=../.local/playwright npm run e2e -- --project desktop --output ../.local/source-notary-fix/test-results
PLAYWRIGHT_BROWSERS_PATH=../.local/playwright npm run e2e -- --project tablet --project mobile --project webkit --output ../.local/source-notary-fix/responsive-test-results
```

Results: `e2e-desktop.log` (3 passed, 9.5s), `e2e-responsive.log` (5 passed, 15.2s). PDF metrics/text/hash checks: `print-metrics.json`, `pdf-qa.json`. Final rasters: `notary-pages-final/`, `full-pages-final/`. Source/README preservation: `entry-state.json`, `entry.diff`, `entry-hashes.json`, `integrity.json`. No current hosted run was triggered or inspected for these uncommitted changes.

## Human destination review

The exact source catalog destinations were checked against provider-owned public pages on 2026-11-15. This checks presentation destinations, not a new legal interpretation or service SLA. General GRAR/heritage destinations intentionally make no object-deep-link claim.

| Source | Human destination / review |
| --- | --- |
| GRAR / Digitaal Vlaanderen | [Vlaanderen dataset catalog](https://www.vlaanderen.be/datavindplaats/catalogus/gebouwen-en-adressenregister), successfully opened |
| Heritage | [Inventory UI](https://inventaris.onroerenderfgoed.be/) and [reuse page](https://inventaris.onroerenderfgoed.be/hergebruik), successfully opened; supplied attribution retained, no universal reuse/legal approval inferred |
| Flood | [Waterinfo information duty UI](https://waterinfo.vlaanderen.be/informatieplicht), successfully opened; scores remain manual/unavailable as before |
| OVAM | Existing exact asbestos/private/common/validity and soil guidance references from `rules/catalog.py`, successfully opened; catalog values and rules unchanged |
| Vlaanderen / VEKA | Existing exact EPC and renovation references from `rules/catalog.py`, successfully opened; rules unchanged |
| FOD Economie / AREI | Existing exact electrical guidance reference from `rules/catalog.py`, successfully opened |
| Civil Code | Existing [Justel Book 3 page](https://www.ejustice.just.fgov.be/eli/loi/2020/02/04/2020A20347/justel): web tool returned an internal access error; independent verified-TLS HTTP GET returned **200 HTML**, title “Banque de données Justel”, same final URL. `justel-url-check.json` records status/title only. The existing legal source/rules were not revised. |
