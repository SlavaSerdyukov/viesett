# Official-source review — 2026-11-11

Technical/documentation review for Viesett Milestone 2, not Belgian legal approval. No customer data was used. No private frontend traffic was inspected. This review distinguishes provider documentation from proof that a deployed service answered successfully.

| Area | Evidence reviewed | Verification level |
| --- | --- | --- |
| GRAR unstructured search | Official free-text use case; public v2 controller/filter/response | Documented contract; automated synthetic-fixture tests |
| GRAR address links | Current public `AddressDetailOsloResponse`, its response options, official relationship FAQ | Documented navigation and fallback, automated validation/SSRF tests |
| GRAR unit/building/parcel contracts | Provider-owned current response models and common enum definitions | Documented normalized fields/relations; deterministic tests |
| Optional key/rate limits | Official API limit/key-plan pages | Documented; mock-header, retry and secret-log tests |
| Heritage | Current Geoportaal help/downloads, agency technical article/API reference, official datasets/reuse page | Documented public service; fixture parsing and geometry tests; not live-verified |
| Flood | Waterinfo FAQ/portal, public ArcGIS directory, OGRK documentation | Reviewed only; no approved automatic score contract found; manual-path behavior tested |
| Live GRAR smoke | Dedicated opt-in command using `Dahliastraat 97, 9000 Gent`, an official documentation example | Actually attempted; UPSTREAM_UNAVAILABLE / transport_unavailable |
| Live heritage / flood score | No successful resolved live identity; no approved automatic flood endpoint | Not performed / not claimed |

The GRAR API documentation shell identifies API release 2026-10-29. Direct DNS/HTTP access to the official GRAR host/documentation was unavailable from the execution environment. The browser research service could read official documentation, and the connected GitHub source reader could inspect the government-owned current public API implementation. No live compatibility claim is derived from those reads.

Pinned public implementation revisions consulted:

- `Informatievlaanderen/address-registry`: `ac14b5ef2a5145ade86079c85d19e0d10c144eba` — v2 search route, query/result-type/status fields, detail identifiers and address navigation.
- `Informatievlaanderen/building-registry`: `df8369d9ea5a09f3a6fd8ed0a8afa41100777053` — v2 building/unit response models, parent/address relationships, geometry fields.
- `Informatievlaanderen/parcel-registry`: `2586ce03f1807f11cb6960e1b36237da57494c06` — parcel ID, CaPaKey, status, related addresses; no parcel polygon in the read response.
- `Informatievlaanderen/grar-common`: `d4ffa89e9a4a2c6635cf6575cbbaa70dbc57812a` — published statuses/functions and CaPaKey formats. In particular, unknown function and common/shared unit are distinct; no residential classification was invented. The CaPaKey exponent accepts letters, `_` and `0`; regression tests preserve the latter two forms through parcel resolution, evidence and Waterinfo references.

Primary links, endpoint families, attributions and semantic limitations are in [GRAR](grar.md), [heritage](onroerend-erfgoed.md), and [flood](flood-information.md). GRAR reads permit anonymous use; an optional key changes quota, not the data model. Heritage is documented as public; an exact numeric quota was not found. Provider-specific terms, deployment/recipient roles and future commercial redistribution details remain legal/operational review items before beta.

Attributions are derived from current metadata: `Bron: Digitaal Vlaanderen`, metadata publisher `Onroerend Erfgoed`, and the Waterinfo verification-reference name. These are persisted separately from evidence text and exposed to future clients. They do not imply provider endorsement or legal sign-off.

All fixtures are synthetic examples matching inspected published shapes, not customer uploads or recordings of a successful live call. Normal CI blocks HTTP network transports and injects MockTransport. PROJ grid downloads are disabled. The opt-in CLI is the only supplied live-smoke mechanism; it is disabled unless `VIESETT_RUN_LIVE_SOURCE_TESTS=1` is set. It never prints API keys.

Scraping portals and reverse-engineering private endpoints were rejected because they do not meet the documented-source policy. Flood remains a typed manual lookup until an authoritative supported contract can be established. Large-area heritage POST support and separate parcel geometry lookup are deferred rather than guessed. Re-run the opt-in live checks and confirm current provider contracts/terms before public beta.
