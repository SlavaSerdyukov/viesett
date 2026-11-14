# M6 browser, PDF, accessibility and request behavior

The default Playwright configuration includes Chromium desktop/tablet/mobile plus critical Firefox and WebKit projects. It uses one worker, no retry/forced click, synthetic local providers/PDFs, an isolated database/root and opt-in development bootstrap. Traces are off and test credentials remain only in worker memory. Mobile ambiguity uses an explicit normalized UI fixture; private creation still independently validates its IDs through the local provider adapter.

Locally, Chromium and WebKit critical journeys pass. Firefox's installed engine exits **before page creation** with “Could not find profile folder.” The failure repeats with the default directory, a project-local directory and canonical `/private/tmp`. No security preference or failing product behavior was bypassed. Its project remains enabled in CI; this host provides no Firefox product-success claim. At the first local verification, a Linux/other supported-host run was still needed.

Continuation verified **2026-11-14**: that supported-host check now exists. [GitHub Actions run 43530283363](https://github.com/SlavaSerdyukov/viesett/actions/runs/43530283363), exact commit `1928f9e`, passes all **eight** configured tests on Linux, including Firefox and WebKit critical journeys. Its logs were read, not inferred from a badge. This closes the cross-browser verification gap while retaining the separate local macOS launch limitation; it does not certify native embedded-PDF pixels or physical devices.

```sh
# Full configured matrix on a host supporting all engines:
cd web
npx playwright install chromium firefox webkit
npm run e2e
# Actual supported local matrix used in M6:
PLAYWRIGHT_BROWSERS_PATH=../.local/playwright npm run e2e -- --project desktop --project tablet --project mobile --project webkit
```

The main journey exercises private exchange/cookie flags, reload, keyboard dialogs/navigation/upload/copy, automatic analysis, finding/page citation, private PDF fallback/reload, print media and server logout. Sample dossiers exercise the optional unverified date, co-ownership assumptions and return navigation. Axe WCAG A/AA-tag checks cover Start, Overview, Documents, Findings, Co-ownership, Questions, Evidence and Print on desktop, plus sample Overview at tablet/mobile sizes. Passing selected automated checks is not human assistive-technology testing or accessibility certification.

Focus management runs before a user can interact after routing; a delayed animation frame had been able to steal focus from the upload input. Dialog close restores the initiating control or a surviving heading. Upload/classification completion focuses the uploaded-document group; session expiry focuses reconnect. Keyboard tests cover these transitions. Upload has a visible focus-within outline; copy has a graceful manual fallback when Clipboard API permission/support is missing. Mobile retains a visible logout action.

The selected private PDF alone is fetched with authorization/cookie into a Blob URL. Closing/unmounting aborts/revokes it; reload creates a fresh URL. The viewer displays the target page and offers download if native rendering is absent/blank. Browser tests verify the surrounding controls/authorization/Blob target, not native PDF pixels or coordinate highlighting. Unit tests verify revocation. No external viewer or public file URL exists.

## Browser print

The notary view opens its native `details` elements before printing; CSS alone cannot reliably reveal closed disclosure content. Thus source citations, rule versions and assumptions are present. Print CSS removes keyboard outlines and controls, avoids orphan headings and small-card/row splits, and allows the longer Article 3.94 package to flow between pages. Source references wrap and unlinked buyer-context labels are separated from adjacent links. One professional-review footer remains.

The desktop sample creates a synthetic A4 PDF using [Playwright browser printing](https://playwright.dev/docs/api/class-page#page-pdf). It is rasterized locally with macOS CoreGraphics for page-by-page inspection because Poppler was unavailable. This is QA output under `.local/`, not a new server PDF feature, public artifact or pixel-identical cross-browser promise. Exact final page count/results are in [verification-m6.md](../../verification-m6.md). No manual in-app browser interaction or real printer/device study is claimed.

## Requests and payloads

One query key per dossier composes current state; PDFs load only on demand. Active processing polls at 3 seconds, doubles after failures, caps its interval, and stops after four failures or a two-minute activity bound. A retry's analysis start time, rather than an old upload date, anchors that bound. Hidden-window interval requests are disabled through Query and unmounted observers stop; shared query keys deduplicate simultaneous views. A successful fetch resets backoff. No WebSocket or endpoint-by-endpoint polling was added.

The aggregate continues to omit histories, raw text/provider bodies, PDF bytes, storage keys and evaluation archives. The final five-document sample is about 90 KB, still bounded and explicitly truncated at existing limits. [Performance measurements](../private-beta/performance.md) are local synthetic baselines, not production SLAs.
