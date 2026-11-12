# Article 3.94 information package

Reviewed 2026-11-12 against [consolidated Book 3, Justel](https://www.ejustice.just.fgov.be/eli/loi/2020/02/04/2020A20347/justel) and [Fednot buyer guidance](https://www.notaire.be/immobilier/acheter-et-vendre-un-bien-immobilier/acheter-un-appartement). See the [source review](../rules/source-review-2026-11-12-m4.md) for retrieval evidence and boundaries.

Article 3.94 §1 concerns information before the contract, purchase offer or promise in the relevant inter vivos lot-transfer context. The syndic communicates it on simple request within **15 days**. The notary/professional intermediary/outgoing co-owner supplies it to the incoming co-owner as applicable. Failure to respond triggers information about the omission; this software does not adjudicate a deadline breach or transaction validity. A stored request date is not proof of valid receipt or standing.

Article 3.94 §2 has a separate registered-request/notarial transfer context and **30-day** response framework. Cost responsibility depends on documented decisions, payment requests, transfer/enjoyment dates, contractual clauses and circumstances such as attendance by proxy. The application does not automate those legal determinations. Article 3.95 concerns notarial handling of seller arrears and competing claims, not a buyer-debt calculator.

## Evaluated components

| Component code | Documentary basis / completeness policy |
| --- | --- |
| `WORKING_CAPITAL` | Explicit separately labeled amount; zero is a value |
| `RESERVE_CAPITAL` | Explicit separately labeled amount; not interchangeable with working capital |
| `SELLER_ARREARS` | Explicit seller/lot amount; zero is EXPLICIT_NONE, silence is missing |
| `RESERVE_CAPITAL_CALLS` | Explicit reserve-call status or reserve-capital calls; an extraordinary/working-capital call alone does not supply this component |
| `PENDING_LITIGATION` | Explicit absence or disclosed property-related pending litigation and amounts where available |
| `AGM_MINUTES_3Y` | Explicit coverage of ordinary and extraordinary minutes over the rolling previous three years |
| `PERIODIC_CHARGES_2Y` | Explicit statement/statement-period coverage over the rolling previous two years |
| `LATEST_APPROVED_BALANCE_SHEET` | Available approved balance copy; a latest-approved reference alone is PARTIAL and must match the copy identifier when supplied |

The eight product components split statutory numbered items for useful review; they do not add new statutory duties. Basis deeds, co-ownership regulations and internal rules have separate governance purposes and are not presented as eight additional §1 requirements.

PRESENT, EXPLICIT_NONE, MISSING, PARTIAL, UNPARSEABLE and NOT_APPLICABLE are separate states. Missing/partial/unparseable important components generate BLOCKING_DATA_GAP, meaning the check cannot finish; this never declares a prohibited transaction. NOT_APPLICABLE currently means co-ownership scope is unestablished, with that reason shown; it is not a legal exemption determination.

Coverage stores target start/end, explicitly documented intervals and exact gaps as of the evaluation date, including leap-year handling. A meeting date alone proves no three-year coverage. A supported response can explicitly assert complete ordinary/extraordinary coverage; this remains DOCUMENTED information, not verification that every legally required meeting was supplied. Undated/latestness assertions and unidentified copies require human review. The package is not a legal completeness certificate.

Selected accounting facts preserve period, currency, date, context, document and citations. The application does not reconcile ledgers or infer undisclosed arrears, litigation, funds or calls. Old and future information cannot silently become a current dated balance. Fees included in statutory seller arrears and particular legal/timing questions require the syndic/notary's confirmation.
