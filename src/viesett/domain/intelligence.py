from datetime import date, datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import Field, JsonValue

from viesett.domain.base import Schema


class AnalysisKind(StrEnum):
    UNKNOWN = "UNKNOWN"
    EPC = "EPC"
    ASBESTOS_CERTIFICATE = "ASBESTOS_CERTIFICATE"
    ELECTRICAL_INSPECTION = "ELECTRICAL_INSPECTION"
    SOIL_CERTIFICATE = "SOIL_CERTIFICATE"
    SYNDIC_INFORMATION = "SYNDIC_INFORMATION"
    AGM_MINUTES = "AGM_MINUTES"
    EXTRAORDINARY_AGM_MINUTES = "EXTRAORDINARY_AGM_MINUTES"
    BASIS_DEED = "BASIS_DEED"
    CO_OWNERSHIP_REGULATIONS = "CO_OWNERSHIP_REGULATIONS"
    INTERNAL_RULES = "INTERNAL_RULES"
    PERIODIC_CHARGE_STATEMENT = "PERIODIC_CHARGE_STATEMENT"
    BALANCE_SHEET = "BALANCE_SHEET"
    CAPITAL_CALL = "CAPITAL_CALL"
    RESERVE_FUND_STATEMENT = "RESERVE_FUND_STATEMENT"
    OTHER_CO_OWNERSHIP_DOCUMENT = "OTHER_CO_OWNERSHIP_DOCUMENT"


class ExtractionStatus(StrEnum):
    PENDING = "PENDING"
    EXTRACTING = "EXTRACTING"
    READY = "READY"
    OCR_REQUIRED = "OCR_REQUIRED"
    FAILED = "FAILED"
    DELETED = "DELETED"


class AssociationStatus(StrEnum):
    MATCHED = "MATCHED"
    POSSIBLE_MATCH = "POSSIBLE_MATCH"
    MISMATCH = "MISMATCH"
    UNVERIFIED = "UNVERIFIED"


class AsbestosVariant(StrEnum):
    PRIVATE_UNIT = "PRIVATE_UNIT"
    COMMON_PARTS = "COMMON_PARTS"
    COMMONLY_USED_PARTS = "COMMONLY_USED_PARTS"
    UNSPECIFIED = "UNSPECIFIED"


class Classification(Schema):
    predicted_kind: AnalysisKind = AnalysisKind.UNKNOWN
    confidence: float = Field(default=0, ge=0, le=1)
    matched_signals: list[str] = Field(default_factory=list)
    classifier_version: str = "signals:1.0.0"


class Association(Schema):
    status: AssociationStatus = AssociationStatus.UNVERIFIED
    reason: str
    identity_revision: str | None = None
    matched_parcels: list[str] = Field(default_factory=list)
    signals: list[str] = Field(default_factory=list)


class TextPage(Schema):
    number: int = Field(ge=1)
    text: str


class PageText(Schema):
    parser_version: str = "pdf-text:1.0.0"
    pages: list[TextPage]


class ExtractedField(Schema):
    key: str = Field(pattern=r"^[a-z][a-z0-9_.]*$", max_length=120)
    value_kind: Literal["text", "integer", "decimal", "boolean", "date", "epc_label", "money"] = (
        "text"
    )
    value: str | int | float | bool
    page: int = Field(ge=1)
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    confidence: float = Field(default=1, ge=0, le=1)
    parser_version: str
    effective_date: date | None = None
    currency: Literal["EUR", "USD", "GBP"] | None = None
    context: str | None = Field(default=None, max_length=120)
    group: str = Field(default="root", max_length=80)


class CoMetadata(Schema):
    detected_language: Literal["nl", "fr", "unknown"]
    detector_version: str = "co-language:1.0.0"
    confidence: float = Field(ge=0, le=1)
    parse_status: Literal["PARSED", "PARTIALLY_PARSED", "UNSUPPORTED_LAYOUT", "UNPARSEABLE"]
    extractor_version: str = "co-ownership:1.0.0"


class AnalyzeRequest(Schema):
    manual_kind: AnalysisKind | None = None
    evaluation_date: date | None = None


class AnalysisOut(Schema):
    id: UUID
    workspace_id: UUID
    document_id: UUID
    generation: int
    status: ExtractionStatus
    automated_classification: Classification
    manual_classification: AnalysisKind | None
    correction_recorded: bool
    effective_classification: AnalysisKind
    asbestos_variant: AsbestosVariant = AsbestosVariant.UNSPECIFIED
    co_metadata: CoMetadata | None = None
    association: Association
    fields: list[ExtractedField]
    evidence_ids: list[UUID]
    page_count: int
    parser_version: str
    source_sha256: str
    failure_code: str | None
    retry_eligible: bool
    created_at: datetime
    completed_at: datetime | None


class AnalysisReport(Schema):
    current: AnalysisOut
    history: list[AnalysisOut] = Field(default_factory=list)


class Applicability(StrEnum):
    REQUIRED = "REQUIRED"
    CONDITIONAL = "CONDITIONAL"
    NOT_REQUIRED = "NOT_REQUIRED"
    UNKNOWN = "UNKNOWN"
    NOT_YET_EFFECTIVE = "NOT_YET_EFFECTIVE"


class Presence(StrEnum):
    PRESENT = "PRESENT"
    MISSING = "MISSING"
    UNUSABLE = "UNUSABLE"
    EXPIRED = "EXPIRED"
    MISMATCHED = "MISMATCHED"
    OCR_REQUIRED = "OCR_REQUIRED"


class RuleMetadata(Schema):
    code: str
    version: str = "1.0.0"
    jurisdiction: str = "BE-VLG"
    effective_from: date
    effective_to: date | None = None
    reviewed_at: date = date(2026, 11, 12)
    official_source_name: str
    official_source_reference: str


class Requirement(Schema):
    kind: AnalysisKind
    variant: AsbestosVariant | None = None
    rule: RuleMetadata
    applicability: Applicability
    presence: Presence
    validity_status: Literal["EXPLICIT_CURRENT", "EXPIRED", "UNVERIFIED"] = "UNVERIFIED"
    reason: str
    evidence_ids: list[UUID] = Field(default_factory=list)
    document_ids: list[UUID] = Field(default_factory=list)
    missing_parcels: list[str] = Field(default_factory=list)
    evaluation_date: date


class EvaluationRequest(Schema):
    evaluation_date: date | None = None


class EvaluationOut(Schema):
    id: UUID
    workspace_id: UUID
    evaluation_date: date
    input_hash: str
    identity_revision: str | None
    requirements: list[Requirement]
    finding_ids: list[UUID]
    rules: list[RuleMetadata]
    # Reproducible normalized inputs, never full text or storage references.
    inputs: dict[str, JsonValue]
    created_at: datetime
