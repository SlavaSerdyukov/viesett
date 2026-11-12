# Proportional exposure derivation

`PROJECT_PROPORTIONAL_EXPOSURE`, `proportional-exposure:1.0.0`, category FINANCIAL_DERIVATION, reviewed 2026-11-12. This is arithmetic on documented inputs, with INFERRED authority and legal payment responsibility UNDETERMINED.

Only an explicitly APPROVED work with an explicitly approved budget and a documented applicable expense share can produce a calculated estimate. A cost estimate in an approved discussion is not an approved budget. General common-parts ownership is used only where the matching project explicitly states that the general key applies. An explicit applicable expense key takes precedence. Unknown allocation, conflicting identity/project/share data, negative budgets or incompatible funding block precision.

```
gross proportional amount = approved project cost × numerator / denominator
remaining financing basis = approved project cost − explicit project reserve allocation
estimated proportional amount = remaining financing basis × numerator / denominator
```

Amounts use bounded Decimal cents and an exact Fraction; the exact numerator/denominator are retained before HALF_UP rounding to cents. Example: approved €120,000, applicable 75/1000 and explicitly project-allocated €40,000 yield €9,000 gross and €6,000 after that allocation. A reserve **balance** of €40,000 does not establish project funding and is never subtracted. If funding is absent, the estimate explicitly states that funding is unverified and shows gross exposure without a deduction. It does not assert that all financing is known.

A reserve allocation must use the budget's currency and fall between zero and the budget. No foreign-exchange conversion, amount-based materiality threshold, solvency inference or overall risk score exists. A call comparison requires an explicit same-project full-project claim and compatible timing; an instalment does not contradict a whole-project budget by amount alone.

The snapshot carries status, gross project cost, explicit funding, remaining basis, gross/estimated proportional values, applicable share, exact fraction, confidence, assumptions, version and all relevant evidence IDs. Supported results include CALCULATED, UNKNOWN_ALLOCATION, INSUFFICIENT_BUDGET and CONFLICTING_INPUTS. Non-approved work is preserved without an approved-work exposure estimate.

No figure is the buyer's legally owed debt. A notary must verify the allocation key, statutes, decision scope, agreement, request/payment and transfer timing under [Book 3, Article 3.94](https://www.ejustice.just.fgov.be/eli/loi/2020/02/04/2020A20347/justel). Working-capital adjustments, reserve ownership and Article 3.95 withholding are not netted into these calculations.
