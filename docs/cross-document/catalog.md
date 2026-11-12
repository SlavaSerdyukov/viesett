# Cross-document check catalog — M4

Reviewed 2026-11-12. Every code below is **version 1.0.0** and persists its code, category, description, inputs, severity policy, source where applicable, review/effective dates and evaluation provenance. Evaluation: `co-ownership-evaluation:1.0.0`; questions: `buyer-questions:1.0.0`. These versions participate in the input hash.

| Code | Category | Trigger / policy |
| --- | --- | --- |
| `ADDRESS_CONSISTENCY` | CROSS_DOCUMENT_CHECK | Explicit address differs from selected official property |
| `UNIT_CONSISTENCY` | CROSS_DOCUMENT_CHECK | Explicit box or private lot differs between applicable documents |
| `PARCEL_CONSISTENCY` | CROSS_DOCUMENT_CHECK | Document parcel conflicts with official parcels |
| `CO_OWNERSHIP_IDENTITY_CONSISTENCY` | CROSS_DOCUMENT_CHECK | Different enterprise identities for one building |
| `OWNERSHIP_SHARE_CONSISTENCY` | CROSS_DOCUMENT_CHECK | Different rational shares for same lot/date/context |
| `RESERVE_CAPITAL_AMOUNT_CONSISTENCY` | CROSS_DOCUMENT_CHECK | Reserve observations disagree at same date/context/currency |
| `WORKING_CAPITAL_AMOUNT_CONSISTENCY` | CROSS_DOCUMENT_CHECK | Working-capital observations disagree at same date/context/currency |
| `CAPITAL_CALL_CONSISTENCY` | CROSS_DOCUMENT_CHECK | Comparable capital-call observations disagree |
| `AGM_WORK_VS_CAPITAL_CALL` | CROSS_DOCUMENT_CHECK | Explicit full-project capital call conflicts with approved project budget |
| `AGM_WORK_VS_SYNDIC_INFO` | CROSS_DOCUMENT_CHECK | Syndic denies approved works despite an earlier applicable decision |
| `ARTICLE_3_94_PACKAGE_COMPLETENESS` | REGULATORY_RULE | Important pre-contractual component or coverage is absent |
| `BE_RESERVE_CAPITAL_CONTRIBUTION` | REGULATORY_RULE | Verify annual contribution, age and documented waiver conditions |
| `CO_GOVERNANCE_RESTRICTION` | CROSS_DOCUMENT_CHECK | Explicit supported operational/statutory restriction needs review |
| `CO_PENDING_LITIGATION` | CROSS_DOCUMENT_CHECK | Pending VME litigation disclosed; outcome and responsibility unknown |
| `CO_PLANNED_WORK_REVIEW` | CROSS_DOCUMENT_CHECK | Approved work has missing budget/funding/allocation evidence |
| `CO_CAPITAL_CALL_RESPONSIBILITY` | CROSS_DOCUMENT_CHECK | Clarify buyer/seller responsibility for a documented capital call |

Checks run in a dedicated engine over current normalized evidence and official identity, without parsing raw PDFs. Monetary conflicts require the same concept, explicit effective date, currency and reporting/lot context. Different-date observations are preserved without a mismatch merely because values changed. Missing identifiers, unknown context and unsupported layouts preserve uncertainty. Parcel checks consume existing structured M3 facts; no listing parser was added.

Address/parcel/entity and comparable numerical conflicts use WARNING where supported. Lot ambiguity, restrictions, litigation and financial responsibility generally use REVIEW. Missing important statutory components use BLOCKING_DATA_GAP: insufficient data, never a transaction prohibition. No arbitrary euro threshold, score or severity based only on a litigation amount exists.

Each finding produces a stable-key question with target role, reason and evidence IDs. Completeness requests target the seller; documented discrepancies normally target the syndic; allocation/governance questions target the notary. Controlled facts replace personal source paragraphs. Unchanged evaluation reuse prevents duplicate findings, work candidates, estimates or questions. New results preserve history and resolve superseded managed findings. Copyable requests include dated gaps and never send messages.

`PROJECT_PROPORTIONAL_EXPOSURE` is a separate FINANCIAL_DERIVATION, version `proportional-exposure:1.0.0`; see [financial-exposure.md](financial-exposure.md). Regulatory scope and reviewed sources: [source review](../rules/source-review-2026-11-12-m4.md).
