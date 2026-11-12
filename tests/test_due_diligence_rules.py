from dataclasses import replace
from datetime import date
from uuid import uuid4

import pytest

from viesett.domain.intelligence import (
    AnalysisKind,
    Applicability,
    AssociationStatus,
    ExtractionStatus,
    Presence,
)
from viesett.domain.types import Severity
from viesett.rules.catalog import CATALOG, effective
from viesett.rules.engine import DocumentInput, Fact, RuleContext, add_months, evaluate

WHEN = date(2026, 11, 12)


def fact(value: object) -> Fact:
    assert isinstance(value, (str, int, float, bool))
    return Fact(value, (uuid4(),))


def doc(kind: AnalysisKind, **fields: object) -> DocumentInput:
    data: dict[str, tuple[Fact, ...]] = {key: (fact(value),) for key, value in fields.items()}
    return DocumentInput(
        uuid4(),
        kind,
        ExtractionStatus.READY,
        AssociationStatus.MATCHED,
        data,
        tuple(e for values in data.values() for f in values for e in f.evidence_ids),
    )


def context(*documents: DocumentInput, **facts: object) -> RuleContext:
    when = facts.pop("when", WHEN)
    assert isinstance(when, date)
    return RuleContext(when, documents, facts={key: fact(value) for key, value in facts.items()})


def req(ctx: RuleContext, code: str) -> tuple[Applicability, Presence]:
    result = next(r for r in evaluate(ctx).requirements if r.rule.code == code)
    return result.applicability, result.presence


@pytest.mark.parametrize(
    "residential,transfer,exempt,expected",
    [
        (True, True, False, "REQUIRED"),
        (True, False, False, "NOT_REQUIRED"),
        (False, True, False, "NOT_REQUIRED"),
        (True, True, True, "NOT_REQUIRED"),
    ],
)
def test_epc_requirement_needs_explicit_applicability(
    residential: bool,
    transfer: bool,
    exempt: bool,
    expected: str,
) -> None:
    ctx = context(
        **{
            "property.residential": residential,
            "transaction.qualifying_transfer": transfer,
            "transaction.epc_exemption": exempt,
        }
    )
    assert req(ctx, "FL_EPC_REQUIRED") == (expected, "MISSING")


@pytest.mark.parametrize("label", ["E", "F"])
@pytest.mark.parametrize("residential", [True, False, None])
def test_renovation_never_assumes_residential_or_deadline(
    label: str, residential: bool | None
) -> None:
    epc = doc(AnalysisKind.EPC, label=label)
    predicates = {} if residential is None else {"property.residential": residential}
    finding = next(
        f for f in evaluate(context(epc, **predicates)).findings if f.code == "FL_EPC_RENOVATION"
    )
    assert finding.severity == Severity.REVIEW
    assert "Indicative deadline" not in finding.details
    if residential is True:
        assert "six years" in finding.details and "unavailable" in finding.details


def test_actual_deed_date_and_sufficient_conditions_allow_calculation() -> None:
    ctx = context(
        doc(AnalysisKind.EPC, label="E", residential=True),
        **{
            "transaction.qualifying_transfer": True,
            "transaction.authentic_deed_date": "2026-02-28",
            "transaction.renovation_exemption": False,
            "transaction.existing_renovation_obligation": False,
        },
    )
    finding = next(f for f in evaluate(ctx).findings if f.code == "FL_EPC_RENOVATION")
    assert finding.severity == Severity.WARNING and "2032-02-28" in finding.details
    assert finding.rule.version == "1.0.0" and finding.rule.official_source_reference
    assert finding.evidence_ids
    conflict = replace(ctx, documents=(ctx.documents[0], doc(AnalysisKind.EPC, label="D")))
    assert (
        next(f for f in evaluate(conflict).findings if f.code == "FL_EPC_RENOVATION").severity
        == Severity.REVIEW
    )


@pytest.mark.parametrize("label", ["A+", "A", "B", "C", "D"])
def test_other_epc_labels_do_not_create_ef_finding(label: str) -> None:
    assert not any(
        f.code == "FL_EPC_RENOVATION"
        for f in evaluate(context(doc(AnalysisKind.EPC, label=label))).findings
    )


@pytest.mark.parametrize(
    "year,accessible,area,larger,transfer,expected",
    [
        (1999, True, 30, False, True, "REQUIRED"),
        (1999, True, 16, True, True, "REQUIRED"),
        (1999, True, 16, False, True, "NOT_REQUIRED"),
        (2001, True, 30, False, True, "NOT_REQUIRED"),
        (1999, False, 30, False, True, "NOT_REQUIRED"),
        (1999, True, 30, False, False, "NOT_REQUIRED"),
    ],
)
def test_asbestos_conditions_and_area_exceptions(
    year: int,
    accessible: bool,
    area: int,
    larger: bool,
    transfer: bool,
    expected: str,
) -> None:
    ctx = context(
        **{
            "property.construction_year": year,
            "property.accessible": accessible,
            "property.aggregate_accessible_area_m2": area,
            "property.part_of_larger_construction": larger,
            "transaction.qualifying_transfer": transfer,
        }
    )
    assert req(ctx, "FL_ASBESTOS_REQUIRED")[0] == expected


def test_missing_year_is_conditional_and_no_validity_is_not_validity_proof() -> None:
    certificate = doc(
        AnalysisKind.ASBESTOS_CERTIFICATE, variant="PRIVATE_UNIT", conclusion="asbestveilig"
    )
    result = evaluate(context(certificate))
    requirement = next(r for r in result.requirements if r.rule.code == "FL_ASBESTOS_REQUIRED")
    assert (
        requirement.applicability == "CONDITIONAL" and requirement.validity_status == "UNVERIFIED"
    )
    assert not any(f.code == "FL_ASBESTOS_VALIDITY" for f in result.findings)


@pytest.mark.parametrize(
    "when,expected",
    [
        (date(2026, 12, 31), "NOT_YET_EFFECTIVE"),
        (date(2027, 1, 1), "REQUIRED"),
    ],
)
@pytest.mark.parametrize("transfer", [True, False])
def test_common_parts_future_timing(when: date, expected: str, transfer: bool) -> None:
    ctx = context(
        when=when,
        **{
            "property.forced_coownership": True,
            "property.construction_year": 1990,
            "property.accessible": True,
            "property.aggregate_accessible_area_m2": 100,
            "transaction.qualifying_transfer": transfer,
        },
    )
    assert req(ctx, "FL_ASBESTOS_COMMON_PARTS")[0] == expected


def test_expired_rule_version_cannot_make_a_current_requirement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(
        CATALOG,
        "FL_EPC_REQUIRED",
        CATALOG["FL_EPC_REQUIRED"].model_copy(update={"effective_to": date(2026, 11, 11)}),
    )
    assert (
        req(
            context(
                **{
                    "property.residential": True,
                    "transaction.qualifying_transfer": True,
                    "transaction.epc_exemption": False,
                }
            ),
            "FL_EPC_REQUIRED",
        )[0]
        == "UNKNOWN"
    )


def test_commonly_used_parts_have_separate_date() -> None:
    metadata = CATALOG["FL_ASBESTOS_COMMONLY_USED"]
    assert metadata.effective_from == date(2025, 5, 1)
    assert not effective(metadata, date(2025, 4, 30))
    assert effective(metadata, date(2025, 5, 1))


@pytest.mark.parametrize(
    "expiry,expected", [("2026-11-11", True), ("2026-11-12", False), ("2030-01-01", False)]
)
def test_explicit_asbestos_validity_uses_evaluation_date(expiry: str, expected: bool) -> None:
    certificate = doc(
        AnalysisKind.ASBESTOS_CERTIFICATE,
        variant="PRIVATE_UNIT",
        conclusion="asbestveilig",
        valid_until=expiry,
    )
    result = evaluate(context(certificate))
    assert any(f.code == "FL_ASBESTOS_VALIDITY" for f in result.findings) == expected
    assert (req(context(certificate), "FL_ASBESTOS_REQUIRED")[1] == "EXPIRED") == expected


@pytest.mark.parametrize("sale", [True, False])
@pytest.mark.parametrize("with_deed", [True, False])
def test_negative_electrical_report_uses_only_sale_context(sale: bool, with_deed: bool) -> None:
    certificate = doc(
        AnalysisKind.ELECTRICAL_INSPECTION,
        conforming=False,
        inspection_type="verkoop" if sale else "periodieke controle",
    )
    predicates = {"transaction.authentic_deed_date": "2026-02-28"} if with_deed else {}
    finding = next(
        f
        for f in evaluate(context(certificate, **predicates)).findings
        if f.code == "BE_ELECTRICAL_NEGATIVE_SALE"
    )
    assert finding.severity == (Severity.WARNING if sale else Severity.REVIEW)
    assert ("2027-08-28" in finding.details) == (sale and with_deed)
    assert ("18 months" in finding.details) == sale


def test_electrical_requirement_keeps_history_and_exemption_conditions() -> None:
    assert req(context(), "BE_ELECTRICAL_REQUIRED")[0] == "CONDITIONAL"
    facts = {
        "property.residential": True,
        "transaction.qualifying_transfer": True,
        "transaction.electrical_sale_exemption": False,
        "electrical.installation_before_1981": True,
        "electrical.complete_conformity_inspection": False,
    }
    assert req(context(**facts), "BE_ELECTRICAL_REQUIRED")[0] == "REQUIRED"
    facts["transaction.electrical_sale_exemption"] = True
    assert req(context(**facts), "BE_ELECTRICAL_REQUIRED")[0] == "NOT_REQUIRED"
    conforming = doc(AnalysisKind.ELECTRICAL_INSPECTION, conforming=True)
    assert not any(
        f.code == "BE_ELECTRICAL_NEGATIVE_SALE" for f in evaluate(context(conforming)).findings
    )


def test_soil_required_presence_coverage_and_risk_are_separate() -> None:
    certificate = doc(
        AnalysisKind.SOIL_CERTIFICATE,
        **{"parcel.capakey": "11001B0001/00S000", "risk_ground": True},
    )
    ctx = replace(
        context(certificate, **{"transaction.ground_transfer": True}),
        parcels=frozenset({"11001B0001/00S000", "11001B0009/00G004"}),
    )
    result = evaluate(ctx)
    requirement = next(r for r in result.requirements if r.kind == AnalysisKind.SOIL_CERTIFICATE)
    assert requirement.applicability == "REQUIRED" and requirement.presence == "UNUSABLE"
    assert requirement.missing_parcels == ["11001B0009/00G004"]
    assert {"FL_SOIL_RISK_GROUND", "FL_SOIL_PARCEL_COVERAGE", "FL_SOIL_REQUIRED"} <= {
        f.code for f in result.findings
    }
    for f in result.findings:
        assert "soil is clean" not in f.details
    assert (
        req(context(**{"transaction.ground_transfer": False}), "FL_SOIL_REQUIRED")[0]
        == "NOT_REQUIRED"
    )


@pytest.mark.parametrize(
    "association",
    [AssociationStatus.MISMATCH, AssociationStatus.POSSIBLE_MATCH, AssociationStatus.UNVERIFIED],
)
def test_unassociated_facts_never_affect_property_rules(association: AssociationStatus) -> None:
    certificate = replace(
        doc(AnalysisKind.EPC, label="E", residential=True), association=association
    )
    result = evaluate(context(certificate))
    assert not any(f.code == "FL_EPC_RENOVATION" for f in result.findings)
    assert any(f.code == "DOCUMENT_PROPERTY_ASSOCIATION" for f in result.findings)


@pytest.mark.parametrize(
    "status,presence",
    [
        (ExtractionStatus.OCR_REQUIRED, "OCR_REQUIRED"),
        (ExtractionStatus.FAILED, "UNUSABLE"),
        (ExtractionStatus.PENDING, "UNUSABLE"),
    ],
)
def test_presence_distinguishes_unusable_pdf(status: ExtractionStatus, presence: str) -> None:
    certificate = replace(doc(AnalysisKind.EPC, label="E"), status=status)
    assert req(context(certificate), "FL_EPC_REQUIRED")[1] == presence


def test_effective_range_is_inclusive_and_date_input_controls_results() -> None:
    metadata = CATALOG["FL_EPC_REQUIRED"].model_copy(update={"effective_to": date(2026, 12, 31)})
    assert not effective(metadata, date(2026, 11, 11))
    assert effective(metadata, date(2026, 11, 12)) and effective(metadata, date(2026, 12, 31))
    assert not effective(metadata, date(2027, 1, 1))
    assert add_months(date(2024, 2, 29), 72) == date(2030, 2, 28)


@pytest.mark.parametrize("case", ["exempt", "expired", "future_deed"])
def test_renovation_exceptions_and_stale_dates_cannot_produce_absolute_deadline(case: str) -> None:
    certificate = doc(
        AnalysisKind.EPC,
        label="E",
        residential=True,
        valid_until="2026-01-01" if case == "expired" else "2030-01-01",
    )
    result = evaluate(
        context(
            certificate,
            **{
                "transaction.qualifying_transfer": True,
                "transaction.renovation_exemption": case == "exempt",
                "transaction.existing_renovation_obligation": False,
                "transaction.authentic_deed_date": "2027-01-01"
                if case == "future_deed"
                else "2026-01-01",
            },
        )
    )
    finding = next(f for f in result.findings if f.code == "FL_EPC_RENOVATION")
    assert "Indicative deadline" not in finding.details
    if case != "future_deed":
        assert finding.severity == "REVIEW"
