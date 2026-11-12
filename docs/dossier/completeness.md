# Dossier completeness

Completeness measures available, usable information, not property risk, compliance approval or whether a purchase should proceed.

The denominator includes only M3 requirements explicitly classified REQUIRED. CONDITIONAL/UNKNOWN requirements are counted separately and excluded until applicability is established; NOT_REQUIRED/NOT_YET_EFFECTIVE items are excluded. A required item completes only when its existing presence is PRESENT and not expired. Missing, mismatched, OCR-required or otherwise unusable documents do not satisfy it. An adverse conclusion in a usable certificate can coexist with completeness: the data is available and still needs attention.

Where documentary co-ownership scope is established, applicable Article 3.94 package components are added once each. PRESENT and EXPLICIT_NONE complete a component. MISSING/PARTIAL/UNPARSEABLE do not. Unestablished scope is not treated as a legal exemption or an unconditional missing apartment package.

```
completed_count = usable required checks + complete applicable co-ownership components
applicable_count = required checks + applicable co-ownership components
percentage = round(100 × completed_count / applicable_count)
```

The response exposes both counts, the unweighted basis and conditional count. Zero applicable checks yields null percentage, never a default 100%. States: active work → IN_PROGRESS; no applicable denominator → BLOCKED_BY_MISSING_DATA; all applicable checks complete with no unresolved conditional applicability → COMPLETE; otherwise INCOMPLETE. A percentage of 100% of known applicable items can coexist with INCOMPLETE while conditional questions remain; the UI explains the exclusions.

Completeness and findings are separate panels. Missing information never becomes a legally blocked purchase. The product adds no new statutory requirement, monetary severity weighting or subjective score. Existing M3/M4 sources, rule versions and uncertainty remain available through citations/details.

Tests separately cover required/present, missing, OCR, mismatched, unusable, conditional exclusions, zero denominator, true complete state and co-ownership components. Reclassification, deletion and refreshed source/analysis generations recompute the projection.
