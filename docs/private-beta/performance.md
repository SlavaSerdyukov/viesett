# Local M6 performance baseline

Final continuation measurement **2026-11-14**, after the deterministic-demo hotfix, exact application source `1928f9e`. Synthetic data, actual loopback HTTP, one application process, new local PostgreSQL 15.15 database, Python 3.12.14, Chromium and freshly built Vite production assets. Official providers use the explicit demo transport with artificial delay disabled. These are **not production SLAs or live-source latency measurements**.

| Operation | Samples | Median / observation | Range |
| --- | --- | --- | --- |
| Five-document dossier GET | 5 | 118.12 ms | 93.67–753.21 ms |
| Production-asset Start ready in fresh browser contexts | 3 | 544.51 ms | 277.01–962.49 ms |
| Authenticated reload → Overview ready | 3 | 476.54 ms | 425.93–491.17 ms |
| Synthetic 1,004-byte text PDF upload → analyzed response | 1 | 1,287.69 ms | Not a distribution |
| Deterministic co/document refresh, public sources=false | 1 | 93.02 ms | Not a distribution |
| Seed five synthetic documents through actual pipelines | 1 | 5,005.48 ms | Not a distribution |

The sample contains **5 documents, 105 current facts, 89,872 uncompressed response bytes**, unchanged from the first M6 sample. M5's corresponding sample was about 86 KB. Current context/processing-date fields and fictional transaction facts remain bounded. No full evidence history, raw document/page text, upstream archive, PDF bytes, duplicate internal finding/question collection or evaluation inputs appear in the normal DTO. No cache/compression subsystem was added.

Actual session-authorized HTTP requests exercise the private upload/parser/evaluation pipeline. Browser timing includes session/config restoration and the visible-ready condition; production assets are served through local Vite preview. Fresh and subsequent samples may use different OS/database caches. Hardware load, scheduling, file/layout limits and source availability change results. Earlier November-13 observations (GET median 18.38 ms, Start 73.97 ms, reload 102.35 ms) are retained under `.local/verification-m6-performance/`; the two runs are not a controlled performance comparison and establish no cause for the timing difference.

Final build: JS **356.13KB / 111.23KB gzip**, CSS **20.67KB / 5.32KB gzip**, HTML 0.59KB; 1,817 modules, **7.30s** in this local run. The same assets built in 1.50s in the inspected hosted run. Bundle size is unchanged; build/response durations are observations, not promises.

Current aggregates: `.local/m6-continuation-2026-11-14/backend.json` and `frontend.json`. Task-local measurement helpers write only aggregate timings/counts and do not modify the checked-in DTO fixture. No credential constants, customer files, analytics/replay SDK or research storage were added. Both temporary servers and the task PostgreSQL were stopped after measurement. [Exact verification](../../verification-m6.md).
