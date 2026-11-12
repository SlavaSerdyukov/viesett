# Flood information: authoritative manual lookup

Reviewed 2026-11-11. Provider/reference: VMM / official Waterinfo. The [official information-duty FAQ](https://www.waterinfo.vlaanderen.be/default.aspx?path=Public%2FOver+waterinfo%2FFAQ+informatieplicht) distinguishes parcel P-score and building G-score, with A–D classes. Viesett does not calculate either score.

Review covered the [official information-duty portal](https://waterinfo.vlaanderen.be/informatieplicht), [public-access guidance](https://www.waterinfo.vlaanderen.be/accountaanvragen), the [public ArcGIS service directory](https://inspirepub.waterinfo.be/arcgis/rest/services/informatieplicht), and the published OGRK webservice manual linked from Waterinfo. The directory lists fluvial/pluvial/coastal hazard services; this is not a confirmed application contract returning authoritative property P/G-score pairs.

**Conclusion of this review:** a clearly documented public authoritative P/G-score lookup endpoint suitable for this application was not confirmed. This is an assessment of the reviewed documentation, not a claim that no such service can exist. No private browser endpoint was investigated or implemented. No HTML scraping, WMS pixel interpretation, A–D derivation, hazard-to-score conversion or undocumented report-download endpoint is used.

With resolved parcels, snapshots return `MANUAL_OFFICIAL_LOOKUP_REQUIRED`, null `p_score`/`g_score`, the official verification reference, and one URL per source-supplied CaPaKey:

```text
https://waterinfo.vlaanderen.be/informatieplicht?capakey=<URL-encoded CaPaKey>
```

These are external verification paths, not a retrieved score or confirmation that a report exists. The official site exposes [Capakey links](https://waterinfo.vlaanderen.be/informatieplicht?capakey=38014F0742%2F00K000); opening/preselection behavior has not been live-tested in this environment. Always expose the generic official reference and the actual Capakey so the user can verify manually if preselection fails. No backend request is sent when constructing these links.

Without any resolved parcel, the result is NOT_APPLICABLE, meaning automatic property-specific lookup cannot currently be offered, not “no flood exposure.” SOURCE_UNAVAILABLE is reserved for a verification-path/service availability problem. There is intentionally no automatic AVAILABLE/score constructor: the current typed result rejects scores. A future approved authoritative contract must extend it with tests and provenance; test doubles cannot smuggle guessed scores into this milestone.

No flood map context is implemented. This avoids a GIS expansion and prevents hazard datasets being confused with statutory property scores. References carry Waterinfo's source name and link; there is no copied map/data product, backend recipient, authentication token, cache, rate-limit dependency or score freshness claim. Final application-specific access/reuse conditions and any future official-score integration still require review.
