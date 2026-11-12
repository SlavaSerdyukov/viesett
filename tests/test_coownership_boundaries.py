import hashlib
import logging
from dataclasses import replace
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from tests.coownership_fixtures import AGM_NL, CALL_NL, DEED_NL, IDENTITY_NL, SYNDIC_NL
from tests.test_coownership_engine import context, doc, result
from tests.test_pdf_intelligence import pages
from viesett.coownership.context import Document, Fact
from viesett.coownership.coverage import coverage
from viesett.coownership.engine import evaluate
from viesett.coownership.extraction import amount, extract_co
from viesett.domain.coownership import CoverageInterval
from viesett.domain.intelligence import AnalysisKind, ExtractedField
from viesett.domain.property import OfficialParcel


def test_reference_without_balance_copy_is_partial_and_no_deed_required_for_arrears() -> None:
    snapshot = result(doc(SYNDIC_NL, AnalysisKind.SYNDIC_INFORMATION))
    components = {c.code: c.status for c in snapshot.article_3_94_completeness}
    assert components["LATEST_APPROVED_BALANCE_SHEET"] == "PARTIAL"
    assert components["SELLER_ARREARS"] == "EXPLICIT_NONE"
    assert snapshot.identity and snapshot.identity.ownership_share is None
    assert snapshot.seller_arrears[0].lot == "A1"


@pytest.mark.parametrize(
    "fund,expected",
    [("buitengewoon", "MISSING"), ("reservekapitaal", "PRESENT"), ("werkkapitaal", "MISSING")],
)
def test_extraordinary_call_does_not_prove_reserve_call_status(fund: str, expected: str) -> None:
    snapshot = result(doc(CALL_NL.replace("buitengewoon", fund), AnalysisKind.CAPITAL_CALL))
    component = next(
        c for c in snapshot.article_3_94_completeness if c.code == "RESERVE_CAPITAL_CALLS"
    )
    assert component.status == expected
    assert snapshot.capital_calls[0].fund_type in {
        "RESERVE_CAPITAL",
        "WORKING_CAPITAL",
        "EXTRAORDINARY",
    }


def test_title_alone_is_not_a_known_call_and_bad_amount_is_unparseable() -> None:
    snapshot = result(doc("Kapitaaloproep\n" + IDENTITY_NL, AnalysisKind.CAPITAL_CALL))
    assert snapshot.capital_calls == []
    text = (
        "Syndicusinformatie\n"
        + IDENTITY_NL.replace("Toestand op: 2026-11-12\n", "")
        + "Werkkapitaal: EUR onleesbaar\n"
    )
    snapshot = result(doc(text, AnalysisKind.SYNDIC_INFORMATION))
    assert (
        next(c for c in snapshot.article_3_94_completeness if c.code == "WORKING_CAPITAL").status
        == "UNPARSEABLE"
    )


def test_estimated_cost_in_approved_decision_is_not_approved_budget() -> None:
    snapshot = result(
        doc(DEED_NL, AnalysisKind.BASIS_DEED),
        doc(AGM_NL.replace("Goedgekeurd budget", "Geraamde kost"), AnalysisKind.AGM_MINUTES),
    )
    work = snapshot.planned_works[0]
    assert work.approved_total_cost is None and work.estimated_total_cost
    assert snapshot.financial_exposure_estimates[0].status == "INSUFFICIENT_BUDGET"


@pytest.mark.parametrize("funding", ["EUR 140000,00", "USD 40000,00", "EUR -1,00"])
def test_incompatible_project_funding_blocks_precise_estimate(funding: str) -> None:
    snapshot = result(
        doc(DEED_NL, AnalysisKind.BASIS_DEED),
        doc(AGM_NL.replace("EUR 40000,00", funding), AnalysisKind.AGM_MINUTES),
    )
    assert snapshot.financial_exposure_estimates[0].status == "CONFLICTING_INPUTS"
    assert snapshot.financial_exposure_estimates[0].estimated_proportional_amount is None


def test_fraction_retains_exact_value_before_rounding() -> None:
    text = AGM_NL.replace("EUR 120000,00", "EUR 100,00").replace(
        "Reserveallocatie project: EUR 40000,00\n", ""
    )
    snapshot = result(
        doc(DEED_NL.replace("75/1000", "1/3"), AnalysisKind.BASIS_DEED),
        doc(text, AnalysisKind.AGM_MINUTES),
    )
    estimate = snapshot.financial_exposure_estimates[0]
    assert (estimate.exact_numerator, estimate.exact_denominator) == (100, 3)
    assert (
        estimate.estimated_proportional_amount
        and estimate.estimated_proportional_amount.amount == Decimal("33.33")
    )
    assert any("unverified" in a for a in estimate.assumptions)


def test_conflicting_shares_lots_and_working_capital_generate_specific_checks() -> None:
    snapshot = result(
        doc(DEED_NL, AnalysisKind.BASIS_DEED),
        doc(DEED_NL.replace("75/1000", "80/1000"), AnalysisKind.BASIS_DEED),
        doc(SYNDIC_NL, AnalysisKind.SYNDIC_INFORMATION),
        doc(SYNDIC_NL.replace("EUR 12000,00", "EUR 13000,00"), AnalysisKind.SYNDIC_INFORMATION),
        doc(CALL_NL.replace("Kavel: A1", "Kavel: A2"), AnalysisKind.CAPITAL_CALL),
    )
    codes = {f.code for f in snapshot.cross_document_findings}
    assert {
        "OWNERSHIP_SHARE_CONSISTENCY",
        "WORKING_CAPITAL_AMOUNT_CONSISTENCY",
        "UNIT_CONSISTENCY",
    } <= codes
    assert snapshot.identity and snapshot.identity.ownership_share is None
    assert snapshot.capital_calls[0].lot_specific_amount is None
    assert any(q.target_role == "NOTARY" for q in snapshot.questions)


def test_enterprise_conflict_does_not_select_current_money() -> None:
    snapshot = result(
        doc(SYNDIC_NL, AnalysisKind.SYNDIC_INFORMATION),
        doc(SYNDIC_NL.replace("0000000196", "0000000295"), AnalysisKind.SYNDIC_INFORMATION),
    )
    assert snapshot.co_ownership_status == "REVIEW"
    assert snapshot.current_reserve_capital is None
    assert any(
        f.code == "CO_OWNERSHIP_IDENTITY_CONSISTENCY" for f in snapshot.cross_document_findings
    )


def test_capital_call_conflict_and_uncertain_work_candidates_remain_distinct() -> None:
    snapshot = result(
        doc(CALL_NL, AnalysisKind.CAPITAL_CALL),
        doc(CALL_NL.replace("EUR 120000,00", "EUR 130000,00"), AnalysisKind.CAPITAL_CALL),
        doc(AGM_NL, AnalysisKind.AGM_MINUTES),
        doc(AGM_NL.replace("EUR 120000,00", "EUR 140000,00"), AnalysisKind.AGM_MINUTES),
    )
    assert any(f.code == "CAPITAL_CALL_CONSISTENCY" for f in snapshot.cross_document_findings)
    assert len(snapshot.planned_works) == 2
    assert all(e.status == "CONFLICTING_INPUTS" for e in snapshot.financial_exposure_estimates)


def test_content_duplicate_without_project_reference_deduplicates() -> None:
    text = AGM_NL.replace("Projectreferentie: ROOF-2026\n", "")
    source = doc(text, AnalysisKind.AGM_MINUTES)
    source = replace(source, source_sha256=hashlib.sha256(text.encode()).hexdigest())
    snapshot = result(source, replace(source, id=uuid4()))
    assert len(snapshot.meetings) == len(snapshot.planned_works) == 1
    assert len(snapshot.meetings[0].decisions) == 1


def test_later_decision_supersedes_status_without_deleting_meeting_history() -> None:
    newer = AGM_NL.replace("2026-03-01", "2026-09-01").replace(
        "Besluit: goedgekeurd", "Besluit: verworpen"
    )
    snapshot = result(doc(AGM_NL, AnalysisKind.AGM_MINUTES), doc(newer, AnalysisKind.AGM_MINUTES))
    assert len(snapshot.meetings) == 2 and len(snapshot.planned_works) == 1
    assert snapshot.planned_works[0].decision_status == "REJECTED"
    assert snapshot.financial_exposure_estimates == []


def test_future_addressless_enterprise_document_does_not_strengthen_into_current_state() -> None:
    future = SYNDIC_NL.replace("Gebouwadres: Teststraat 42, 9000 Gent\n", "").replace(
        "2026-11-12", "2027-11-12"
    )
    snapshot = result(
        doc(DEED_NL, AnalysisKind.BASIS_DEED), doc(future, AnalysisKind.SYNDIC_INFORMATION)
    )
    assert snapshot.reserve_capital == [] and snapshot.associations[1].status == "UNVERIFIED"


def test_box_mismatch_remains_reviewable() -> None:
    snapshot = result(doc(SYNDIC_NL + "Bus: 99\n", AnalysisKind.SYNDIC_INFORMATION))
    assert snapshot.associations[0].status == "POSSIBLE_MATCH" and snapshot.reserve_capital == []
    assert any(f.code == "UNIT_CONSISTENCY" for f in snapshot.cross_document_findings)


def test_parcel_check_consumes_normalized_existing_fact() -> None:
    fact = ExtractedField(
        key="document.soil.parcel.capakey",
        value="11001A0002/00A000",
        value_kind="text",
        page=1,
        start=0,
        end=18,
        parser_version="soil:1.0.0",
    )
    document = Document(
        uuid4(), AnalysisKind.SOIL_CERTIFICATE, (Fact(fact, uuid4()),), "PARSED", "a" * 64
    )
    ctx = context(document)
    parcel = OfficialParcel(
        official_id="11001A0001-00A000",
        source_uri="https://data.vlaanderen.be/id/perceel/11001A0001-00A000",
        source_version=None,
        retrieved_at=ctx.property.address.retrieved_at if ctx.property.address else None,
        status="gerealiseerd",
        capakey="11001A0001/00A000",
        address_official_ids=[],
    )
    snapshot = evaluate(
        replace(ctx, property=ctx.property.model_copy(update={"parcels": [parcel]}))
    )
    assert any(f.code == "PARCEL_CONSISTENCY" for f in snapshot.cross_document_findings)


def test_rolling_coverage_preserves_leap_day_and_exact_gap() -> None:
    result = coverage(
        date(2024, 2, 29),
        3,
        [
            CoverageInterval(start=date(2021, 2, 28), end=date(2023, 12, 31)),
            CoverageInterval(start=date(2024, 2, 1), end=date(2024, 2, 29)),
        ],
    )
    assert result.coverage_start == date(2021, 2, 28)
    assert [(g.start, g.end) for g in result.gaps] == [(date(2024, 1, 1), date(2024, 1, 31))]


@pytest.mark.parametrize("text", ["EUR 12 34,00", "EUR 1.234.56", "EUR 1,234.56"])
def test_malformed_grouping_is_not_massaged(text: str) -> None:
    assert amount(text) is None


def test_content_never_enters_coownership_logs(caplog: pytest.LogCaptureFixture) -> None:
    private = "PRIVATE_ATTENDEE_9988"
    text = AGM_NL + "Aanwezigen: " + private + "\nIBAN: BE00 1234 1234 1234\n"
    with caplog.at_level(logging.DEBUG):
        fields, _ = extract_co(pages(text), AnalysisKind.AGM_MINUTES)
        result(doc(text, AnalysisKind.AGM_MINUTES))
    assert private not in caplog.text and "BE00" not in caplog.text
    assert private not in str(fields)


def test_official_box_requires_private_lot_corroboration_before_exposure() -> None:
    ctx = context(doc(DEED_NL, AnalysisKind.BASIS_DEED), doc(AGM_NL, AnalysisKind.AGM_MINUTES))
    assert ctx.property.address
    property = ctx.property.model_copy(
        update={"address": ctx.property.address.model_copy(update={"box_number": "2"})}
    )
    snapshot = evaluate(replace(ctx, property=property))
    assert snapshot.identity and snapshot.identity.lot_identifier is None
    assert snapshot.financial_exposure_estimates[0].status == "UNKNOWN_ALLOCATION"
    confirmed = doc(DEED_NL + "Bus: 2\n", AnalysisKind.BASIS_DEED)
    snapshot = evaluate(replace(ctx, property=property, documents=(confirmed, ctx.documents[1])))
    assert snapshot.identity and snapshot.identity.lot_identifier == "A1"
    assert snapshot.financial_exposure_estimates[0].status == "CALCULATED"


def test_share_preserves_printed_rational_representation() -> None:
    snapshot = result(doc(DEED_NL.replace("75/1000", "75 / 1000"), AnalysisKind.BASIS_DEED))
    assert snapshot.identity and snapshot.identity.ownership_share
    assert snapshot.identity.ownership_share.original_representation == "75 / 1000"
    assert snapshot.identity.ownership_share.denominator == 1000


@pytest.mark.parametrize(
    "heading,status,pending",
    [
        ("Geschil 1", "", False),
        ("Litige en cours 1", "", True),
        ("Geschil 1", "Status geschil: afgesloten\n", False),
    ],
)
def test_litigation_requires_explicit_pending_status(
    heading: str, status: str, pending: bool
) -> None:
    snapshot = result(
        doc(
            SYNDIC_NL + "\n" + heading + ": dakgebreken\n" + status, AnalysisKind.SYNDIC_INFORMATION
        )
    )
    assert bool(snapshot.pending_litigation) == pending
    assert (
        any(f.code == "CO_PENDING_LITIGATION" for f in snapshot.cross_document_findings) == pending
    )
    if not status and not pending:
        assert (
            next(
                c for c in snapshot.article_3_94_completeness if c.code == "PENDING_LITIGATION"
            ).status
            == "PARTIAL"
        )


def test_lot_balances_are_not_building_funds_or_cross_lot_conflicts() -> None:
    first = SYNDIC_NL.replace("Context: gebouw", "Context: kavel")
    second = first.replace("Kavel: A1", "Kavel: A2").replace("EUR 50000,00", "EUR 60000,00")
    snapshot = result(
        doc(first, AnalysisKind.SYNDIC_INFORMATION), doc(second, AnalysisKind.SYNDIC_INFORMATION)
    )
    assert snapshot.current_reserve_capital is None
    assert {o.lot for o in snapshot.reserve_capital} == {"A1", "A2"}
    assert not any(
        f.code == "RESERVE_CAPITAL_AMOUNT_CONSISTENCY" for f in snapshot.cross_document_findings
    )
