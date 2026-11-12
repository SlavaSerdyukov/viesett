# Deterministic rules catalog

All codes below are version **1.0.0**. Implementation: `src/viesett/rules/catalog.py` and `engine.py`. Pure typed Python, explicit RuleContext/evaluation date, no expression interpreter or AI. Jurisdiction BE-VLG except electrical BE. Official documentation was reviewed on **2026-11-12**; this is technical source review, not counsel approval.

| Code | Version coverage starts | Behavior |
| --- | --- | --- |
| FL_EPC_REQUIRED | 2026-11-12 | Residential qualifying transfer with established exception conditions: requirement; otherwise conditional/not required within this rule's residential scope |
| FL_EPC_RENOVATION | 2026-11-12 | Matched E/F evidence creates a conditional review; residential qualifying transfer can raise attention to the six-year D baseline; dates/exemptions/remaining inherited period stay explicit |
| FL_ASBESTOS_REQUIRED | 2022-11-23 | Pre-2001 reference construction year, accessible construction, aggregate >=20m² or larger-construction exception, qualifying transfer; unknown predicates remain conditional |
| FL_ASBESTOS_COMMON_PARTS | 2027-01-01 | Separate VME common-parts possession duty with construction/accessibility/ownership conditions; not dependent on a sale; before start NOT_YET_EFFECTIVE |
| FL_ASBESTOS_COMMONLY_USED | 2025-05-01 | Separate common-used-parts transfer context; ownership/use conditions remain explicit |
| FL_ASBESTOS_VALIDITY | 2026-11-12 | Only an explicitly printed end date establishes expiry/current date comparison |
| BE_ELECTRICAL_REQUIRED | 2026-11-12 | Installation/conformity history and sale exception determine requirement; generally conditional without them |
| BE_ELECTRICAL_NEGATIVE_SALE | 2026-11-12 | Explicit non-conforming sale inspection: buyer remedy/reinspection attention, normally 18 months from authentic deed; other inspection contexts remain review |
| FL_SOIL_REQUIRED | 2026-11-12 | Applicable ground transfer needs a bodemattest, risk or non-risk; transfer definition remains explicit |
| FL_SOIL_PARCEL_COVERAGE | 2026-11-12 | Missing applicable certificate coverage for any current official parcel is a data gap |
| FL_SOIL_RISK_GROUND | 2026-11-12 | Explicit risk-ground evidence requires verification of investigation/exemption and additional transfer conditions |
| DOCUMENT_PROPERTY_ASSOCIATION | 2026-11-12 | Non-regulatory identifier comparison/review safeguard; excludes unrelated/uncertain documents from substantive rules |

Dates for the reviewed current-baseline versions deliberately start at the review date unless a specific verified obligation start is encoded. They are implementation coverage bounds, not claims that longstanding obligations originated in November 2026. Historical six-year amendment interpretation is not retroactively guessed. All versions carry `effective_to`, currently null; evaluation outside a bounded version cannot apply it. Before-start requirements show NOT_YET_EFFECTIVE; after-end versions show UNKNOWN. Future legal changes require a new version and source review.

Applicability: REQUIRED, CONDITIONAL, NOT_REQUIRED, UNKNOWN, NOT_YET_EFFECTIVE. Presence: PRESENT, MISSING, UNUSABLE, EXPIRED, MISMATCHED, OCR_REQUIRED. These axes are independent. `validity_status` separately reports EXPLICIT_CURRENT, EXPIRED or UNVERIFIED. PRESENT is documentary presence, not legal approval. Older residential EPCs without the current sale-label evidence, missing conclusions, uncertain asbestos scope and incomplete soil coverage cannot establish usable coverage. Safety-blocked/deleted/superseded sources do not enter evaluation.

The engine consumes normalized evidence and current document states, records each rule version/source/effective range, and stores the explicit date and inputs/hash. Findings use INFO/REVIEW/WARNING/BLOCKING_DATA_GAP. The last means Viesett lacks reliable evidence for a check; it never declares a transaction prohibited. No overall property score exists.

Unknown residential use, reference year, transfer, installation history, exemptions, construction scope and deed dates remain conditional. The four supported PDF families do not universally establish those predicates. Stable future predicates include `property.residential`, `property.construction_year`, `property.accessible`, `property.aggregate_accessible_area_m2`, `property.part_of_larger_construction`, `property.forced_coownership`, `property.commonly_used_parts`, `transaction.qualifying_transfer`, `transaction.ground_transfer`, `transaction.authentic_deed_date`, `transaction.epc_exemption`, `transaction.renovation_exemption`, `transaction.existing_renovation_obligation`, `transaction.electrical_sale_exemption`, `electrical.installation_before_1981`, `electrical.complete_conformity_inspection`. These require trusted evidence, not a new questionnaire or guessed defaults.

Absolute deadlines require a relevant actual date. Renovation additionally requires established exception/remaining-period conditions; unknown deed/right-establishment date gives no calendar deadline. A printed E/F label with unknown residential status yields REVIEW. Risk-ground is not a sale ban; no-GIR is not clean-soil proof. See the [official-source review](source-review-2026-11-11.md).
