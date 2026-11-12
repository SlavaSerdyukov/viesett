from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Literal, Self
from uuid import UUID

from pydantic import Field, model_validator

from viesett.domain.base import Schema
from viesett.domain.intelligence import AnalysisKind, AssociationStatus
from viesett.domain.types import Authority, Severity

CO_EVALUATION_VERSION = "co-ownership-evaluation:1.0.0"
EXPOSURE_VERSION = "proportional-exposure:1.0.0"
QUESTIONS_VERSION = "buyer-questions:1.0.0"
CO_KINDS = frozenset(AnalysisKind) - {
    AnalysisKind.UNKNOWN,
    AnalysisKind.EPC,
    AnalysisKind.ASBESTOS_CERTIFICATE,
    AnalysisKind.ELECTRICAL_INSPECTION,
    AnalysisKind.SOIL_CERTIFICATE,
}


class DecisionStatus(StrEnum):
    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    POSTPONED = "POSTPONED"
    INFORMATION_ONLY = "INFORMATION_ONLY"
    UNKNOWN = "UNKNOWN"


class WorkCategory(StrEnum):
    ROOF = "ROOF"
    FACADE = "FACADE"
    LIFT = "LIFT"
    HEATING = "HEATING"
    INSULATION = "INSULATION"
    WINDOWS = "WINDOWS"
    STRUCTURAL = "STRUCTURAL"
    ELECTRICAL_COMMON = "ELECTRICAL_COMMON"
    FIRE_SAFETY = "FIRE_SAFETY"
    OTHER = "OTHER"


class PackageStatus(StrEnum):
    PRESENT = "PRESENT"
    EXPLICIT_NONE = "EXPLICIT_NONE"
    MISSING = "MISSING"
    PARTIAL = "PARTIAL"
    UNPARSEABLE = "UNPARSEABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class Share(Schema):
    numerator: int = Field(ge=0, le=1_000_000_000)
    denominator: int = Field(gt=0, le=1_000_000_000)
    original_representation: str = Field(max_length=100)
    basis: Literal["GENERAL_OWNERSHIP_SHARE", "EXPLICIT_EXPENSE_ALLOCATION_KEY"]
    context: str = "general"
    lot: str | None = None
    effective_date: date | None = None
    evidence_ids: list[UUID] = Field(default_factory=list)

    @model_validator(mode="after")
    def valid_fraction(self) -> Self:
        if self.numerator > self.denominator:
            raise ValueError("Share exceeds the documented total")
        return self


class Money(Schema):
    amount: Decimal = Field(max_digits=14, decimal_places=2)
    currency: Literal["EUR", "USD", "GBP"]


class MoneyObservation(Schema):
    concept: str
    money: Money
    effective_date: date | None
    context: str
    lot: str | None = None
    document_id: UUID
    evidence_ids: list[UUID]


class CoverageInterval(Schema):
    start: date
    end: date
    evidence_ids: list[UUID] = Field(default_factory=list)

    @model_validator(mode="after")
    def ordered(self) -> Self:
        if self.end < self.start:
            raise ValueError("Reversed coverage")
        return self


class Coverage(Schema):
    coverage_start: date
    coverage_end: date
    periods_present: list[CoverageInterval] = Field(default_factory=list)
    gaps: list[CoverageInterval] = Field(default_factory=list)
    basis: str = "Explicit documented coverage; no inference from one meeting date"


class PackageComponent(Schema):
    code: str
    status: PackageStatus
    reason: str
    evidence_ids: list[UUID] = Field(default_factory=list)
    coverage: Coverage | None = None
    legal_reference: str = "Belgian Civil Code 3.94 §1"
    rule_version: str = "1.0.0"


class CoOwnershipIdentity(Schema):
    association_name: str | None = None
    enterprise_number: str | None = None
    building_address: str | None = None
    syndic_name: str | None = None
    syndic_enterprise_number: str | None = None
    lot_identifier: str | None = None
    private_unit_designation: str | None = None
    ownership_share: Share | None = None
    attached_lots: list[str] = Field(default_factory=list)
    source_document_ids: list[UUID] = Field(default_factory=list)
    evidence_ids: list[UUID] = Field(default_factory=list)


class Decision(Schema):
    reference: str | None
    category: WorkCategory
    decision_status: DecisionStatus
    meeting_date: date | None
    topic: str
    budget: Money | None = None
    estimated_budget: Money | None = None
    agenda_item_number: str | None = None
    normalized_decision: str | None = None
    reserve_allocation: Money | None = None
    capital_call_total: Money | None = None
    funding_source: str | None = None
    expected_start: date | None = None
    vote_result: str | None = None
    evidence_ids: list[UUID] = Field(default_factory=list)


class Meeting(Schema):
    key: str
    meeting_date: date | None
    meeting_type: Literal["ORDINARY", "EXTRAORDINARY"]
    decisions: list[Decision]
    source_document_ids: list[UUID]


class PlannedWork(Schema):
    key: str
    reference: str | None
    category: WorkCategory
    description: str
    decision_status: DecisionStatus
    decision_date: date | None
    estimated_total_cost: Money | None = None
    approved_total_cost: Money | None = None
    funding_source: str | None = None
    reserve_fund_allocation: Money | None = None
    capital_call_total: Money | None = None
    expected_start: date | None = None
    evidence_ids: list[UUID]


class CapitalCall(Schema):
    reference: str | None
    project_reference: str | None
    total: Money | None
    lot_specific_amount: Money | None
    lot: str | None
    due_date: date | None
    effective_date: date | None
    purpose: str | None
    fund_type: Literal["WORKING_CAPITAL", "RESERVE_CAPITAL", "EXTRAORDINARY", "UNKNOWN"]
    covers_full_project: bool = False
    evidence_ids: list[UUID]


class Litigation(Schema):
    subject_category: str
    status: str
    amount_in_dispute: Money | None
    effective_date: date | None
    evidence_ids: list[UUID]


class Exposure(Schema):
    planned_work_key: str
    status: Literal["CALCULATED", "UNKNOWN_ALLOCATION", "INSUFFICIENT_BUDGET", "CONFLICTING_INPUTS"]
    gross_project_cost: Money | None
    explicit_project_funding: Money | None = None
    remaining_financing_basis: Money | None = None
    share: Share | None = None
    gross_proportional_amount: Money | None = None
    estimated_proportional_amount: Money | None = None
    exact_numerator: int | None = None
    exact_denominator: int | None = None
    confidence: Literal["DOCUMENTED_INPUTS", "INSUFFICIENT_INPUTS"]
    assumptions: list[str]
    source_evidence_ids: list[UUID]
    calculation_version: str = EXPOSURE_VERSION
    calculation_code: str = "PROJECT_PROPORTIONAL_EXPOSURE"
    category: Literal["FINANCIAL_DERIVATION"] = "FINANCIAL_DERIVATION"
    reviewed_at: date = date(2026, 11, 12)
    authority: Authority = Authority.INFERRED
    legal_payment_responsibility: Literal["UNDETERMINED"] = "UNDETERMINED"


class CheckMetadata(Schema):
    code: str
    version: str = "1.0.0"
    category: Literal["REGULATORY_RULE", "CROSS_DOCUMENT_CHECK", "FINANCIAL_DERIVATION"]
    description: str
    inputs: list[str]
    severity_policy: str
    reviewed_at: date = date(2026, 11, 12)
    official_source: str | None = None
    effective_from: date | None = None
    effective_to: date | None = None


class CoFinding(Schema):
    key: str
    code: str
    severity: Severity
    summary: str
    reason: str
    evidence_ids: list[UUID]
    check: CheckMetadata


class BuyerQuestion(Schema):
    key: str
    code: str
    target_role: Literal["SELLER", "AGENT", "SYNDIC", "NOTARY"]
    question_text: str
    reason: str
    evidence_ids: list[UUID]
    generator_version: str = QUESTIONS_VERSION


class AssociationResult(Schema):
    document_id: UUID
    status: AssociationStatus
    reason: str
    scope: Literal["BUILDING", "PRIVATE_UNIT"]


class CoSnapshot(Schema):
    workspace_id: UUID
    evaluation_id: UUID | None = None
    evaluation_date: date
    identity_revision: str | None
    input_hash: str
    co_ownership_status: Literal["NOT_ESTABLISHED", "DOCUMENTED", "REVIEW"]
    identity: CoOwnershipIdentity | None
    associations: list[AssociationResult]
    article_3_94_completeness: list[PackageComponent]
    working_capital: list[MoneyObservation]
    reserve_capital: list[MoneyObservation]
    current_working_capital: MoneyObservation | None
    current_reserve_capital: MoneyObservation | None
    seller_arrears: list[MoneyObservation]
    accounting_observations: list[MoneyObservation]
    capital_calls: list[CapitalCall]
    pending_litigation: list[Litigation]
    meetings: list[Meeting]
    planned_works: list[PlannedWork]
    financial_exposure_estimates: list[Exposure]
    cross_document_findings: list[CoFinding]
    questions: list[BuyerQuestion]
    latest_balance_sheet_reference: str | None
    syndic_request_date: date | None
    syndic_response_date: date | None
    statutory_response_days: int = 15
    response_period_context: str = (
        "Article 3.94 §1 simple request; §2 has a separate 30-day context"
    )
