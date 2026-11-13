# M6 official GRAR contract review

Actual review and live-check date: **2026-11-13**, Europe/Brussels. The filename follows the requested milestone filename; it is not a claim of retrieval on November 12.

Primary reference: [official v2 API documentation](https://docs.basisregisters.vlaanderen.be/docs/api-documentation.html), version **2026-10-29**, documentation shell 8.17.4. Its linked [OpenAPI 3.0.4 JSON](https://docs.basisregisters.vlaanderen.be/docs/v2/docs.json?culture=en-GB) was retrieved directly. Search returns `resultaten` containing `id`, `objectId`, `detail`, `result`. Detail and relationship GETs expose normalized registry objects. The search vocabulary is:

```text
GET https://api.basisregisters.vlaanderen.be/v2/adressen/zoeken
    ?q=<address>&resultaatType=adressen&status=inGebruik&limit=6
```

| Documented concept | Viesett use |
| --- | --- |
| `q` | NFC/whitespace-normalized user query |
| `gemeenteNaam`, `niscode` | Optional upstream filters; not guessed from input |
| `limit` | Provider default 10, maximum 50; Viesett requests 6 |
| `status` | `inGebruik`; detail status independently checked |
| `resultaatType` | `adressen`; provider also documents `straatnamen` |
| `x-api-key` | Optional header, only on the exact API host; never logged |

Search guidance specifies a 300ms typing debounce. Viesett submits explicitly and retains a 350ms provider gap. Plan-dependent request limits and 429 remain upstream-controlled; no quota entitlement is asserted. [Provider key information](https://basisregisters.vlaanderen.be/apikey) and [limits](https://basisregisters.vlaanderen.be/apikey/limieten) remain operational references.

The M2 report/code mismatch was **real**: entry code sent `query` and `resultType=Address`, and fixtures asserted that behavior. M6 changes those two request fields, checks the generated request, and uses current response-shape fixtures. This corrects the adapter; it does not change domain authority or relax identifier/navigation validation.

Address detail is read from `/v2/adressen/{objectId}`. Its published links and actual live response use lower-case `adresobjectid` in unit/parcel navigation, while parameter metadata names `adresObjectId`. The existing validated linked navigation works live. Fixed fallback paths, parent/address revalidation, bounded pagination, CRS handling and all realized parcels remain intact. Search result order is not a selection rule.

## Actual result

The opt-in verifier returned **LIVE_SUCCESS / RESOLVED** for the fixed public example from the existing M2 tool. DNS, verified TLS, search, address detail, building-unit list/detail, building detail, parcel list/detail and domain normalization succeeded. One parcel, one selected unit, no missing relationships. Output contains only fixed stage categories, counts and booleans; no key, provider body or customer query. This verifies one request chain, not general uptime, every ambiguity case, heritage, legal status or reuse approval.

The live drift checker returned SUCCESS with no failed expectations. Schema hash for that retrieval: `98addb524772085552877c7c4255c2e0f14b48a01898b19bfd4e4c5ee2b01a35`. Provider examples include generated timestamps, so a different whole-document hash alone is not a semantic drift failure. The committed selected metadata fixture omits those examples; expectations cover paths, parameter locations/vocabularies, optional key behavior and search-item structure. No upstream change is applied automatically.

```sh
VIESETT_RUN_LIVE_SOURCE_TESTS=1 uv run python -m viesett.tools.verify_grar
uv run python -m viesett.tools.check_grar_contract --live
uv run python -m viesett.tools.check_grar_contract --schema /private/local/schema.json
```

Live CLI commands refuse CI. Normal tests inject MockTransport and block network HTTP. Normal product errors retain safe existing categories; developer diagnostics distinguish DNS/connect/TLS/read/status/contract failures without exception text. No current GRAR key was printed, requested from another project or placed in a browser bundle. Historical M2 report/migrations remain unchanged; this review supersedes its obsolete request description. M2 heritage/flood/legal/source limitations otherwise remain.
