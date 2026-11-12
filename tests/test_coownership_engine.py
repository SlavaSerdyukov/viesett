from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from tests.coownership_fixtures import (
    AGM_NL,
    BALANCE_NL,
    CALL_NL,
    DEED_NL,
    SAMPLES,
    SYNDIC_NL,
)
from tests.test_pdf_intelligence import pages
from viesett.coownership.context import CrossDocumentContext, Document, Fact
from viesett.coownership.engine import evaluate
from viesett.coownership.extraction import extract_co
from viesett.domain.coownership import CoSnapshot, PackageStatus
from viesett.domain.intelligence import AnalysisKind
from viesett.domain.property import FloodResult, OfficialAddress, PropertySnapshot

WHEN = date(2026, 11, 12)


def doc(text: str, kind: AnalysisKind) -> Document:
    fields, metadata = extract_co(pages(text), kind)
    return Document(
        uuid4(), kind, tuple(Fact(f, uuid4()) for f in fields), metadata.parse_status, "a" * 64
    )


def context(*docs: Document) -> CrossDocumentContext:
    wid = uuid4()
    property = PropertySnapshot(
        workspace_id=wid,
        resolution_status="RESOLVED",
        latest_input_address_query=None,
        snapshot_input_address_query=None,
        property_key="test",
        identity_revision="b" * 64,
        last_successful_retrieval=None,
        stale=False,
        address=OfficialAddress(
            official_id="1",
            source_uri="https://data.vlaanderen.be/id/adres/1",
            source_version=None,
            retrieved_at=datetime(2026, 11, 12, tzinfo=UTC),
            status="inGebruik",
            canonical_address="Teststraat 42, 9000 Gent",
            street_name="Teststraat",
            house_number="42",
            postal_code="9000",
            municipality="Gent",
        ),
        flood=FloodResult(status="NOT_APPLICABLE"),
    )
    return CrossDocumentContext(wid, WHEN, property, docs)


def result(*docs: Document) -> CoSnapshot:
    return evaluate(context(*docs))


def test_complete_package_and_zero_arrears_are_explicit() -> None:
    snapshot = result(
        doc(DEED_NL, AnalysisKind.BASIS_DEED),
        doc(SYNDIC_NL, AnalysisKind.SYNDIC_INFORMATION),
        doc(BALANCE_NL, AnalysisKind.BALANCE_SHEET),
    )
    assert snapshot.identity and snapshot.identity.ownership_share
    assert snapshot.identity.ownership_share.numerator == 75
    assert snapshot.identity.ownership_share.denominator == 1000
    assert snapshot.identity.attached_lots == ["Kelder K1"]
    states = {c.code: c.status for c in snapshot.article_3_94_completeness}
    assert set(states.values()) == {PackageStatus.PRESENT, PackageStatus.EXPLICIT_NONE}
    assert states["SELLER_ARREARS"] == "EXPLICIT_NONE"
    assert snapshot.seller_arrears[0].money.amount == Decimal("0.00")
    assert snapshot.statutory_response_days == 15
    assert not any(
        f.code == "ARTICLE_3_94_PACKAGE_COMPLETENESS" for f in snapshot.cross_document_findings
    )


@pytest.mark.parametrize(
    "remove,code",
    [
        (
            "Volledige dekking gewone en buitengewone AV: 2023-11-12 tot 2026-11-12\n",
            "AGM_MINUTES_3Y",
        ),
        ("Volledige dekking afrekeningen: 2024-11-12 tot 2026-11-12\n", "PERIODIC_CHARGES_2Y"),
        ("Laatste goedgekeurde balans: SYN-BAL-2025\n", "LATEST_APPROVED_BALANCE_SHEET"),
        ("Achterstallen verkoper: EUR 0,00\n", "SELLER_ARREARS"),
    ],
)
def test_missing_component_is_not_none(remove: str, code: str) -> None:
    snapshot = result(
        doc(DEED_NL, AnalysisKind.BASIS_DEED),
        doc(SYNDIC_NL.replace(remove, ""), AnalysisKind.SYNDIC_INFORMATION),
    )
    assert next(c for c in snapshot.article_3_94_completeness if c.code == code).status == "MISSING"
    assert any(q.target_role == "SELLER" and code in q.reason + q.key for q in snapshot.questions)


def test_one_meeting_does_not_claim_three_year_coverage() -> None:
    snapshot = result(doc(AGM_NL, AnalysisKind.AGM_MINUTES))
    coverage = next(c for c in snapshot.article_3_94_completeness if c.code == "AGM_MINUTES_3Y")
    assert coverage.status == "MISSING" and coverage.coverage and coverage.coverage.gaps
    assert len(snapshot.meetings) == len(snapshot.planned_works) == 1


@pytest.mark.parametrize(
    "status,active",
    [
        ("goedgekeurd", True),
        ("voorgesteld", False),
        ("verworpen", False),
        ("uitgesteld", False),
        ("besproken", False),
    ],
)
def test_only_explicit_approval_enables_exposure(status: str, active: bool) -> None:
    snapshot = result(
        doc(DEED_NL, AnalysisKind.BASIS_DEED),
        doc(AGM_NL.replace("Besluit: goedgekeurd", "Besluit: " + status), AnalysisKind.AGM_MINUTES),
    )
    assert bool(snapshot.financial_exposure_estimates) == active
    if active:
        exposure = snapshot.financial_exposure_estimates[0]
        assert exposure.status == "CALCULATED"
        assert exposure.gross_proportional_amount is not None
        assert exposure.estimated_proportional_amount is not None
        assert exposure.gross_proportional_amount.amount == Decimal("9000.00")
        assert exposure.estimated_proportional_amount.amount == Decimal("6000.00")
        assert (exposure.exact_numerator, exposure.exact_denominator) == (6000, 1)
        assert (
            exposure.authority == "INFERRED"
            and exposure.legal_payment_responsibility == "UNDETERMINED"
        )


def test_general_fund_balance_is_not_project_funding() -> None:
    work = AGM_NL.replace("Reserveallocatie project: EUR 40000,00\n", "")
    snapshot = result(
        doc(DEED_NL, AnalysisKind.BASIS_DEED),
        doc(work, AnalysisKind.AGM_MINUTES),
        doc(SYNDIC_NL, AnalysisKind.SYNDIC_INFORMATION),
    )
    assert snapshot.financial_exposure_estimates[0].estimated_proportional_amount is not None
    assert snapshot.financial_exposure_estimates[0].estimated_proportional_amount.amount == Decimal(
        "9000.00"
    )
    assert snapshot.financial_exposure_estimates[0].explicit_project_funding is None


def test_general_ownership_share_does_not_prove_expense_key() -> None:
    work = AGM_NL.replace("Algemene kostensleutel van toepassing: ja\n", "")
    snapshot = result(doc(DEED_NL, AnalysisKind.BASIS_DEED), doc(work, AnalysisKind.AGM_MINUTES))
    assert snapshot.financial_exposure_estimates[0].status == "UNKNOWN_ALLOCATION"
    assert snapshot.financial_exposure_estimates[0].estimated_proportional_amount is None
    assert any(q.target_role == "NOTARY" for q in snapshot.questions)


def test_explicit_expense_share_overrides_general_share() -> None:
    snapshot = result(
        doc(DEED_NL, AnalysisKind.BASIS_DEED),
        doc(AGM_NL + "Kostensleutel: 1/10\n", AnalysisKind.AGM_MINUTES),
    )
    assert snapshot.financial_exposure_estimates[0].estimated_proportional_amount is not None
    assert snapshot.financial_exposure_estimates[0].estimated_proportional_amount.amount == Decimal(
        "8000.00"
    )
    assert snapshot.financial_exposure_estimates[0].share is not None
    assert snapshot.financial_exposure_estimates[0].share.basis == "EXPLICIT_EXPENSE_ALLOCATION_KEY"


def test_same_meeting_and_project_deduplicate_and_call_links() -> None:
    snapshot = result(
        doc(AGM_NL, AnalysisKind.AGM_MINUTES),
        doc(AGM_NL, AnalysisKind.AGM_MINUTES),
        doc(CALL_NL, AnalysisKind.CAPITAL_CALL),
    )
    assert len(snapshot.meetings) == len(snapshot.planned_works) == len(snapshot.capital_calls) == 1
    assert len(snapshot.meetings[0].decisions) == 1
    assert len(snapshot.meetings[0].source_document_ids) == 2
    assert not any(f.code == "AGM_WORK_VS_CAPITAL_CALL" for f in snapshot.cross_document_findings)


@pytest.mark.parametrize("other_date,conflict", [("2026-11-12", True), ("2026-10-12", False)])
def test_fund_amount_comparison_requires_same_date_context(other_date: str, conflict: bool) -> None:
    second = SYNDIC_NL.replace("EUR 50000,00", "EUR 60000,00").replace(
        "Toestand op: 2026-11-12", "Toestand op: " + other_date
    )
    snapshot = result(
        doc(SYNDIC_NL, AnalysisKind.SYNDIC_INFORMATION),
        doc(second, AnalysisKind.SYNDIC_INFORMATION),
    )
    assert (
        any(
            f.code == "RESERVE_CAPITAL_AMOUNT_CONSISTENCY" for f in snapshot.cross_document_findings
        )
        == conflict
    )
    assert (snapshot.current_reserve_capital is None) == conflict
    assert (
        snapshot.current_working_capital
        and snapshot.current_working_capital.money.amount == Decimal("12000.00")
    )


def test_different_building_excluded_and_enterprise_strengthens_only_unverified_address() -> None:
    bad = SYNDIC_NL.replace("Teststraat 42", "Andereweg 9")
    snapshot = result(doc(bad, AnalysisKind.SYNDIC_INFORMATION))
    assert snapshot.identity is None and snapshot.reserve_capital == []
    assert snapshot.associations[0].status == "MISMATCH"
    anchored = result(
        doc(DEED_NL, AnalysisKind.BASIS_DEED),
        doc(
            SYNDIC_NL.replace("Gebouwadres: Teststraat 42, 9000 Gent\n", ""),
            AnalysisKind.SYNDIC_INFORMATION,
        ),
    )
    assert all(a.status == "MATCHED" for a in anchored.associations)
    assert anchored.reserve_capital


def test_litigation_and_restrictions_generate_questions_without_people() -> None:
    case = SYNDIC_NL + "Hangend geschil 1: dakgebreken\nBedrag geschil: EUR 20000,00\n"
    snapshot = result(
        doc(case, AnalysisKind.SYNDIC_INFORMATION),
        doc(SAMPLES[AnalysisKind.INTERNAL_RULES][0], AnalysisKind.INTERNAL_RULES),
    )
    assert snapshot.pending_litigation[0].amount_in_dispute is not None
    assert snapshot.pending_litigation[0].amount_in_dispute.amount == Decimal("20000.00")
    assert {"CO_PENDING_LITIGATION", "CO_GOVERNANCE_RESTRICTION"} <= {
        f.code for f in snapshot.cross_document_findings
    }
    assert len({q.key for q in snapshot.questions}) == len(snapshot.questions)


def test_capital_call_and_syndic_work_contradictions() -> None:
    snapshot = result(
        doc(AGM_NL, AnalysisKind.AGM_MINUTES),
        doc(CALL_NL.replace("EUR 120000,00", "EUR 130000,00"), AnalysisKind.CAPITAL_CALL),
        doc(SYNDIC_NL + "Goedgekeurde werken: geen\n", AnalysisKind.SYNDIC_INFORMATION),
    )
    assert {"AGM_WORK_VS_CAPITAL_CALL", "AGM_WORK_VS_SYNDIC_INFO"} <= {
        f.code for f in snapshot.cross_document_findings
    }
    assert snapshot.financial_exposure_estimates[0].status == "CONFLICTING_INPUTS"


def test_small_balance_alone_is_not_reserve_compliance_failure() -> None:
    snapshot = result(
        doc(SYNDIC_NL.replace("EUR 50000,00", "EUR 1,00"), AnalysisKind.SYNDIC_INFORMATION)
    )
    assert not any(
        f.code == "BE_RESERVE_CAPITAL_CONTRIBUTION" for f in snapshot.cross_document_findings
    )
    financial = (
        SYNDIC_NL + "Voorlopige oplevering gemene delen: 2010-01-01\nJaarlijk"
        "se reservebijdrage: EUR 100,00\nGewone lasten vorig boek"
        "jaar: EUR 10000,00\n"
    )
    snapshot = result(doc(financial, AnalysisKind.SYNDIC_INFORMATION))
    assert any(
        f.code == "BE_RESERVE_CAPITAL_CONTRIBUTION" for f in snapshot.cross_document_findings
    )
    waived = result(
        doc(
            financial + "Vrijstelling reservekapitaal AV: ja\nStemresultaat: 4/5\n",
            AnalysisKind.SYNDIC_INFORMATION,
        )
    )
    assert not any(
        f.code == "BE_RESERVE_CAPITAL_CONTRIBUTION" for f in waived.cross_document_findings
    )
