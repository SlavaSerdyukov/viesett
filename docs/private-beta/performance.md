# Local M6 performance baseline

2026-11-13. Synthetic data, loopback HTTP, one application process, local PostgreSQL 15.15, Python 3.12.14, Chromium and Vite production assets. Official providers were replaced by the explicit demo transport with its artificial delay disabled. These observations are **not production SLAs or live-source latency measurements**.

| Operation | Samples | Median / observation | Range |
| --- | --- | --- | --- |
| Five-document dossier GET | 5 | 18.38 ms | 17.89–39.78 ms |
| Production-asset Start ready in fresh browser contexts | 3 | 73.97 ms | 73.22–136.21 ms |
| Authenticated reload → Overview ready | 3 | 102.35 ms | 94.80–102.78 ms |
| Synthetic 1,004-byte text PDF upload → analyzed dossier response | 1 | 204.79 ms | Not a distribution |
| Deterministic co/document refresh, public sources=false | 1 | 17.90 ms | Not a distribution |
| Seed five synthetic documents through actual pipelines | 1 | 977.92 ms | Not a distribution |

The initial sample contains **5 documents, 105 current facts, 89,872 uncompressed response bytes**. M5's corresponding sample was about 86 KB; the small increase includes explicit context/processing-date fields and two fictional transaction facts. No full evidence history, raw document/page text, upstream archive, PDF bytes, duplicated internal finding/question collection or evaluation inputs are in the normal DTO. Limits/truncation remain explicit; no speculative cache/compression subsystem was added.

Measurements time actual local HTTP requests with session authorization and the real private upload/parser/evaluation pipeline. Browser timing includes session/config restoration and the visible-ready condition; production assets are served locally through Vite preview, not a deployed edge. First and subsequent samples can benefit from OS/database caches. Hardware, process scheduling, network, file size/layout, parser limits and source availability can change results substantially.

Final bundle metrics and exact verification commands are recorded in [verification-m6.md](../../verification-m6.md). Local aggregate logs: `.local/verification-m6-performance/backend.json` and `frontend.json`. Measurement helpers are task-local, contain no credential constants, and write only timings/counts. No analytics/session replay SDK or automatic research storage was added. Re-run the same fixture/environment before making an optimization decision.
