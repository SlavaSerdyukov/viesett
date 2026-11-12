from decimal import ROUND_HALF_UP, Decimal
from fractions import Fraction

from viesett.domain.coownership import Exposure, Money, PlannedWork, Share


def exposure(work: PlannedWork, share: Share | None, *, conflict: bool = False) -> Exposure:
    assumptions = [
        "Mathematical proportional estimate, not the buyer's legally owed debt.",
        "Notary must verify transfer timing, agreement and Article 3.94 §2 allocation.",
        (
            "Only explicitly allocated project funding is deducted; "
            "general fund balances are not used."
        ),
    ]
    references = sorted(set(work.evidence_ids + (share.evidence_ids if share else [])))
    base = {
        "planned_work_key": work.key,
        "gross_project_cost": work.approved_total_cost,
        "share": share,
        "source_evidence_ids": references,
        "assumptions": assumptions,
        "confidence": "INSUFFICIENT_INPUTS",
    }
    if conflict:
        return Exposure.model_validate({**base, "status": "CONFLICTING_INPUTS"})
    budget = work.approved_total_cost
    if budget is None or budget.amount < 0:
        return Exposure.model_validate({**base, "status": "INSUFFICIENT_BUDGET"})
    if share is None:
        return Exposure.model_validate({**base, "status": "UNKNOWN_ALLOCATION"})
    funding = work.reserve_fund_allocation
    if funding is None:
        assumptions.append(
            "Project funding is unverified: the estimate shows gross exposure without a deduction."
        )
    if funding and (
        funding.currency != budget.currency or not 0 <= funding.amount <= budget.amount
    ):
        return Exposure.model_validate({**base, "status": "CONFLICTING_INPUTS"})
    remaining = budget.amount - (funding.amount if funding else Decimal(0))
    ratio = Fraction(share.numerator, share.denominator)
    exact = Fraction(remaining) * ratio
    gross_exact = Fraction(budget.amount) * ratio

    def rounded(value: Fraction) -> Money:
        result = (Decimal(value.numerator) / Decimal(value.denominator)).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )
        return Money(amount=result, currency=budget.currency)

    return Exposure.model_validate(
        {
            **base,
            "status": "CALCULATED",
            "confidence": "DOCUMENTED_INPUTS",
            "explicit_project_funding": funding,
            "remaining_financing_basis": Money(amount=remaining, currency=budget.currency),
            "gross_proportional_amount": rounded(gross_exact),
            "estimated_proportional_amount": rounded(exact),
            "exact_numerator": exact.numerator,
            "exact_denominator": exact.denominator,
        }
    )
