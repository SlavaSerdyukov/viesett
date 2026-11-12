# Official/public property sources

Reviewed 2026-11-11. Viesett calls documented government read services, never scraped portals or private frontend endpoints. No customer documents, bearer tokens, account identifiers or correspondence are sent to these services.

| Source | Integration | Data sent | Result |
| --- | --- | --- | --- |
| [GRAR](grar.md) / Digitaal Vlaanderen | Basisregisters v2 search/detail/read relationships | Normalized address query, official identifiers | Official address, unit, building and parcels |
| [Onroerend Erfgoed](onroerend-erfgoed.md) | Geozoekdiensten `afbakeningen` | Selected official building polygon transformed to WGS84 | Separate designation/inventory/other spatial matches |
| [Waterinfo](flood-information.md) | External official verification links only | Nothing sent by backend | Typed manual P/G-score lookup, with Capakey links |

See the [dated source review](source-review-2026-11-11.md) for what is documented, tested, attempted live and still unverified. Public access and published reuse information are not claims that counsel has approved Viesett's entire processing or commercial deployment.

Development lookups run only when the authenticated owner requests them. Set `VIESETT_OFFICIAL_SOURCES_ENABLED=false` to disable both clients. Production additionally requires `VIESETT_OFFICIAL_SOURCES_REVIEWED=true`; otherwise lookups return an explicit unavailable state without making outbound calls. This operational switch is not user consent, a legal basis or DPA approval. Existing production document-safety and AI-processor gates remain in force.

`VIESETT_GRAR_API_KEY` (or `GRAR_API_KEY`) is optional and secret. It is sent only in GRAR's documented `x-api-key` header, never to heritage, browser clients, exports or logs. Keep it outside Git. Anonymous GRAR reads are supported.

HTTP behavior: separate connect/read/write/pool timeouts of 2/4/2/1 seconds; a 20-second operation budget within the normal 30-second request limit; two attempts maximum by default, configurable up to three; GET only; exponential backoff starting at 0.3 seconds; numeric/HTTP-date Retry-After honored up to a five-second wait. A longer requested wait stops this operation instead of retrying too early. Only transport failures, 429 and 5xx are retried. No redirects or environment proxies are followed. Each provider client has one in-flight request and a minimum 350ms start interval. These limits are per process; coordinate limits before scaling beyond the milestone's single worker.

Responses are bounded at 2 MiB and parsed into typed domain objects. Normal logs/traces must exclude query addresses, geometry, keys, response bodies and provider exception representations. HTTPX/HTTPCore verbose logging is disabled. Source failures become safe status/error codes. No external APM body/URL capture should be enabled by deployment.

No persistent provider response cache or raw JSON archive exists. Typed normalized observations and provenance remain part of the private dossier until deletion. Historical evidence and attempts are exported; cascades remove them on workspace/account deletion. A failed refresh preserves the last successful data and exposes staleness separately for each source.
