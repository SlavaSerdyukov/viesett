# GRAR / Basisregisters Vlaanderen v2

Provider: Digitaal Vlaanderen. Purpose: establish official Flemish property identity. Reviewed: 2026-11-11. Public anonymous read API; optional `x-api-key` for an assigned plan. Only v2 read APIs are used, without v1, feeds or extract endpoints.

## Contract and search

The official [free-text use case](https://vlaamseoverheid.atlassian.net/wiki/spaces/AGB/pages/7844659375) identifies the address/street-name fuzzy search service. Its current public controller and filter contract confirm:

```text
GET https://api.basisregisters.vlaanderen.be/v2/adressen/zoeken
    ?query=<unstructured address>&resultType=Address&status=inGebruik&limit=6
```

Primary implementation references, reviewed at commit `ac14b5ef2a5145ade86079c85d19e0d10c144eba`:

- [AddressController](https://github.com/Informatievlaanderen/address-registry/blob/ac14b5ef2a5145ade86079c85d19e0d10c144eba/src/AddressRegistry.Api.Oslo/Address/V2/AddressController.cs).
- [Search filter](https://github.com/Informatievlaanderen/address-registry/blob/ac14b5ef2a5145ade86079c85d19e0d10c144eba/src/AddressRegistry.Api.Oslo/Address/V2/Search/AddressSearchRequest.cs) and [search response](https://github.com/Informatievlaanderen/address-registry/blob/ac14b5ef2a5145ade86079c85d19e0d10c144eba/src/AddressRegistry.Api.Oslo/Address/V2/Search/AddressSearchResponse.cs).
- [Official API reference](https://docs.basisregisters.vlaanderen.be/docs/api-documentation.html); its JavaScript documentation shell was reachable through research, but direct specification retrieval/live API access was unavailable in this environment.

Input preprocessing only normalizes NFC and whitespace. No address components or bus numbers are guessed. The official search performs fuzzy matching. Search results are followed to normalized detail objects, and only current `inGebruik` addresses are usable. The decoder supports the public response's camel/Pascal member casing for search. It validates official ID namespaces and reconstructs fixed detail URLs, rather than trusting arbitrary detail links.

Exactly one usable address resolves automatically. A unique full canonical-string match can disambiguate multiple suggestions without parsing components. Otherwise the response is NEEDS_SELECTION, with up to five choices and an explicit truncation flag. Six returned search suggestions are conservatively treated as potentially truncated. Explicit user selections must still occur in the freshly queried official candidates.

## Relationships and ambiguity

Prefer address detail `_links.gebouweenheden.href` and `_links.percelen.href`. Without those optional links, use only the documented `GET /v2/gebouweenheden?adresobjectid=…` and `GET /v2/percelen?adresobjectid=…` relationships, also demonstrated by the [official FAQ](https://www.vlaanderen.be/digitaal-vlaanderen/onze-diensten-en-platformen/gebouwen-en-adressenregister/faq). Follow bounded `volgende` pagination while preserving the original address relationship.

Unit details independently confirm the selected address in `adressen`; building details must list the selected unit. Parcel details must confirm the address. All realized parcels and their source-supplied CaPaKey values are retained. A missing relationship or withdrawn detail yields PARTIALLY_RESOLVED, not fabricated data. A failed service is UPSTREAM_UNAVAILABLE; an unsafe link or malformed contract is INVALID_SOURCE_RESPONSE. Neither is silently NOT_FOUND.

Unit status/function semantics come from the provider's [official enums](https://github.com/Informatievlaanderen/grar-common/tree/d4ffa89e9a4a2c6635cf6575cbbaa70dbc57812a/src/Be.Vlaanderen.Basisregisters.GrAr.Legacy/Gebouweenheid): `gerealiseerd` units are usable candidates; `gemeenschappelijkDeel` is excluded from private-unit selection. `nietGekend` is preserved as unknown, not interpreted as residential, HOUSE or APARTMENT. Multiple private candidates require explicit selection. Missing details cannot make a remaining candidate automatically unique. Detail inspection is bounded to 20 unit candidates, with explicit ambiguity/truncation when more exist; explicit related-unit selection is revalidated. Relationship collection is limited to three pages/100 IDs and fails explicitly if exceeded.

Building geometry/status and identifiers are preserved; no year, ownership, legal conformity, condition or value is inferred. The v2 parcel read contract supplies CaPaKey/status/address links but no parcel geometry. Viesett leaves that geometry absent and uses the selected building footprint for this milestone's heritage query. No Capakey/geospatial service has been added speculatively.

Parcel object IDs use the dash notation; source CaPaKeys use the slash notation. The provider's [CaPaKey value object](https://github.com/Informatievlaanderen/grar-common/blob/d4ffa89e9a4a2c6635cf6575cbbaa70dbc57812a/src/Be.Vlaanderen.Basisregisters.GrAr.Common/CaPaKey.cs) permits `_` and `0` as well as letters in the exponent position. Both non-letter forms are covered through resolution, persisted snapshot/evidence and the manual Waterinfo reference.

## Provenance, attribution and safety

Official source identifiers, URIs, versions and retrieval times accompany normalized data. Source GML coordinates and CRS (EPSG:31370, EPSG:3812, or explicitly supplied EPSG:4326) are retained. Transformed WGS84 coordinates are used only for the heritage query and are labeled as derived. Registry/cadastral geometry is not a legal boundary guarantee.

The required credit **“Bron: Digitaal Vlaanderen”** is taken from the [official dataset metadata](https://www.vlaanderen.be/datavindplaats/catalogus/gebouwen-en-adressenregister). It is persisted on source runs and exposed in snapshots. Metadata notes copyright and public access; review the precise production redistribution/hosting terms rather than treating anonymous access as a waiver of all conditions.

[Published API limits](https://vlaamseoverheid.atlassian.net/wiki/spaces/AGB/pages/7843315864) document `x-api-key` and bounded retry advice; [key-plan information](https://vlaamseoverheid.atlassian.net/wiki/spaces/AGB/pages/8322613443) describes shared anonymous capacity and assigned plans. Viesett's per-process 350ms gap is conservative, not a quota entitlement or guarantee against 429. Freshness is per-object version/retrieval time, not a promise of immediate upstream consistency.

Navigation accepts fixed official hosts only. The documented `basisregisters.vlaanderen.be/api/v2/…` alias is canonicalized to `api.basisregisters.vlaanderen.be/v2/…`; it is never contacted separately with a key. Unexpected schemes, hosts, ports, credentials, fragments, encoded/dot path segments and relationship changes are rejected. Data-URI identifiers are preserved for provenance and are never followed as network navigation.

If a pagination builder supplies only offset/limit, Viesett reapplies the original documented `adresobjectid` filter. A different supplied address filter is rejected. Pagination values are bounded and normalized before requesting the fixed endpoint; no unscoped list query is made.
