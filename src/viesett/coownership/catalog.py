from datetime import date

from viesett.domain.coownership import CheckMetadata

LEGAL_SOURCE = "https://www.ejustice.just.fgov.be/eli/loi/2020/02/04/2020A20347/justel"
DESCRIPTIONS = {
    "ADDRESS_CONSISTENCY": "Explicit address differs from selected official property",
    "UNIT_CONSISTENCY": "Explicit box or private lot differs between applicable documents",
    "PARCEL_CONSISTENCY": "Document parcel conflicts with official parcels",
    "CO_OWNERSHIP_IDENTITY_CONSISTENCY": "Different enterprise identities for one building",
    "OWNERSHIP_SHARE_CONSISTENCY": "Different rational shares for same lot/date/context",
    "RESERVE_CAPITAL_AMOUNT_CONSISTENCY": (
        "Reserve observations disagree at same date/context/currency"
    ),
    "WORKING_CAPITAL_AMOUNT_CONSISTENCY": (
        "Working-capital observations disagree at same date/context/currency"
    ),
    "CAPITAL_CALL_CONSISTENCY": "Comparable capital-call observations disagree",
    "AGM_WORK_VS_CAPITAL_CALL": (
        "Explicit full-project capital call conflicts with approved project budget"
    ),
    "AGM_WORK_VS_SYNDIC_INFO": (
        "Syndic denies approved works despite an earlier applicable decision"
    ),
    "ARTICLE_3_94_PACKAGE_COMPLETENESS": (
        "Important pre-contractual component or coverage is absent"
    ),
    "BE_RESERVE_CAPITAL_CONTRIBUTION": (
        "Verify annual contribution, age and documented waiver conditions"
    ),
    "CO_GOVERNANCE_RESTRICTION": (
        "Explicit supported operational/statutory restriction needs review"
    ),
    "CO_PENDING_LITIGATION": "Pending VME litigation disclosed; outcome and responsibility unknown",
    "CO_PLANNED_WORK_REVIEW": "Approved work has missing budget/funding/allocation evidence",
    "CO_CAPITAL_CALL_RESPONSIBILITY": (
        "Clarify buyer/seller responsibility for a documented capital call"
    ),
}
CATALOG = {
    code: CheckMetadata(
        code=code,
        description=description,
        category="REGULATORY_RULE"
        if code in {"ARTICLE_3_94_PACKAGE_COMPLETENESS", "BE_RESERVE_CAPITAL_CONTRIBUTION"}
        else "CROSS_DOCUMENT_CHECK",
        inputs=[
            "current normalized evidence",
            "document association",
            "date/context",
            "evaluation_date",
        ],
        severity_policy=(
            "Specific review or data gap; no amount-based risk scoring or legal payment conclusion"
        ),
        official_source=LEGAL_SOURCE
        if code in {"ARTICLE_3_94_PACKAGE_COMPLETENESS", "BE_RESERVE_CAPITAL_CONTRIBUTION"}
        else None,
        effective_from=date(2021, 9, 1)
        if code in {"ARTICLE_3_94_PACKAGE_COMPLETENESS", "BE_RESERVE_CAPITAL_CONTRIBUTION"}
        else None,
    )
    for code, description in DESCRIPTIONS.items()
}
