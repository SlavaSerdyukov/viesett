# Official heritage spatial enrichment

Provider: Agentschap Onroerend Erfgoed. Reviewed 2026-11-11. Purpose: retain official heritage objects/designations intersecting the selected property's available official area, without deriving legal restrictions or a risk score.

The agency's current [Geoportaal help](https://geo.onroerenderfgoed.be/help) and [downloads/service page](https://geo.onroerenderfgoed.be/downloads) link the publicly accessible [Geozoekdiensten API](https://geo.onroerenderfgoed.be/zoekdiensten/api_doc). The agency's [technical service documentation](https://onroerenderfgoed.github.io/posts/2017/geozoekdiensten/) documents `GET /zoekdiensten/afbakeningen` with GeoJSON `geometrie`, `buffer`, optional `categorie`, and `geef_geometrie`. The documentation is older, but the current service pages still direct integrators to this API. Deployment response compatibility has not been live-verified here.

Viesett queries all published categories with:

```text
GET https://geo.onroerenderfgoed.be/zoekdiensten/afbakeningen
    ?geometrie=<WGS84 GeoJSON Polygon/MultiPolygon>&buffer=0&geef_geometrie=0
```

The source building footprint is retained in its native CRS. Safe GML parsing rejects DTD/entities and unsupported CRS. Standard pyproj/PROJ transforms it with explicit source/target CRS and XY axis order; network grid downloads and ballpark transformations are disabled. The run records source/target CRS, and each match states its building-polygon intersection basis. Native coordinates are never relabeled as provider-supplied WGS84.

This milestone uses the selected building footprint because GRAR parcel detail does not expose parcel geometry. Matches therefore cover that footprint, not a guarantee about the entire parcel or every part of a multi-unit building. There is no point buffer, guessed parcel boundary, spatial risk algorithm or legal-boundary claim. If precise polygon geometry is missing, the source state is NOT_APPLICABLE with `precise_property_area_unavailable`; this does not mean “no heritage.” Geometry query JSON above 6000 characters stops with an explicit unavailable outcome, rather than truncating geometry. Large-area POST support is deliberately deferred until its current request contract can be verified live.

Every returned meaningful match is preserved, including source ID/URI, title, category, published type URI/label, match basis and retrieval time. `aanduidingsobjecten` is the designation category; the original type label/URI distinguishes protections and establishments. `erfgoedobjecten` is scientific inventory presence, stored as INVENTORY_ONLY. `plannen` remains OTHER. Viesett never turns these into one heritage boolean, invents legal validity dates, or claims that inventory presence establishes a legal protection. The [designation dataset](https://www.vlaanderen.be/datavindplaats/catalogus/aanduidingsobjecten) and [inventory dataset](https://www.vlaanderen.be/datavindplaats/catalogus/erfgoedobjecten) document that distinction. Missing legal status remains null.

The snapshot carries the metadata publisher credit **“Onroerend Erfgoed”**, source API reference and [reuse terms](https://inventaris.onroerenderfgoed.be/hergebruik). Those terms describe free reuse and attribution; text/photo-specific authorship or share-alike conditions must be reviewed before adding full descriptions or images. This integration retains identifiers and concise published metadata, without copying articles, photos or private material. Required object-specific attribution must not be discarded if later endpoints provide it.

No key is configured or forwarded. No numeric service quota or freshness SLA was confirmed; Viesett uses one request at a time, conservative pacing, bounded retry and retrieval timestamps. A failed refresh leaves the last successful matches visible with a stale flag. A successful empty response records an empty observation and expires previous current heritage evidence, preserving history.
