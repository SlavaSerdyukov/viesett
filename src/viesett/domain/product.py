"""Explicit bounded product contracts; projections never confer evidence authority."""

from datetime import date as Date
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from viesett.domain.base import Schema
from viesett.domain.coownership import (
    CapitalCall,
    CoOwnershipIdentity,
    Exposure,
    Litigation,
    MoneyObservation,
    PackageComponent,
    PlannedWork,
)
from viesett.domain.intelligence import AnalysisKind, Requirement
from viesett.domain.property import FloodResult, HeritageMatch, SourceAttribution, SourceState
from viesett.domain.schemas import WorkspaceOut
from viesett.domain.types import Authority, Severity


class PropertyView(Schema):
    status: str
    query: str | None = None
    address: str | None = None
    address_id: str | None = None
    unit_id: str | None = None
    box: str | None = None
    parcels: list[str] = Field(default_factory=list)
    last_refreshed: datetime | None = None
    stale: bool = False
    flood: FloodResult
    heritage: list[HeritageMatch] = Field(default_factory=list)
    sources: list[SourceAttribution] = Field(default_factory=list)
    source_states: list[SourceState] = Field(default_factory=list)


class PreviewChoice(Schema):
    address_id: str
    unit_id: str | None = None
    label: str


class PreviewResponse(Schema):
    status: Literal["RESOLVED", "NEEDS_SELECTION", "NOT_FOUND", "UPSTREAM_UNAVAILABLE"]
    property: PropertyView
    choices: list[PreviewChoice] = Field(default_factory=list)
    truncated: bool = False
    is_demo: bool = False


class CitationResponse(Schema):
    label: str
    document_id: UUID | None = None
    page: int | None = None
    uri: str | None = None
    retrieved_at: datetime | None = None


class EvidenceResponse(Schema):
    id: UUID
    label: str
    value: str
    authority: Authority
    date: datetime | None
    effective_date: Date | None = None
    sources: list[CitationResponse]


class DocumentSummaryResponse(Schema):
    id: UUID
    filename: str
    kind: str
    status: str
    association: str
    created_at: datetime
    analysis_id: UUID | None = None
    summary: list[str] = Field(default_factory=list)
    can_view: bool
    can_retry: bool = False
    supported_kinds: list[AnalysisKind] = Field(default_factory=lambda: list(AnalysisKind))


class FindingResponse(Schema):
    id: UUID
    code: str
    group: str
    severity: Severity
    title: str
    explanation: str
    next_step: str
    sources: list[CitationResponse]
    rule_version: str | None = None


class QuestionResponse(Schema):
    key: str
    target_role: str
    question_text: str
    reason: str
    sources: list[CitationResponse]


class CompletenessResponse(Schema):
    state: Literal["COMPLETE", "INCOMPLETE", "BLOCKED_BY_MISSING_DATA", "IN_PROGRESS"]
    completed_count: int
    applicable_count: int
    percentage: int | None
    conditional_count: int
    basis: str = "Unweighted applicable required information checks; not a property risk score."


class CoOwnershipSummaryResponse(Schema):
    co_ownership_status: str
    identity: CoOwnershipIdentity | None
    article_3_94_completeness: list[PackageComponent]
    current_working_capital: MoneyObservation | None
    current_reserve_capital: MoneyObservation | None
    planned_works: list[PlannedWork]
    capital_calls: list[CapitalCall]
    pending_litigation: list[Litigation]
    financial_exposure_estimates: list[Exposure]


class DossierSnapshotResponse(Schema):
    schema_version: str = "buyer-dossier:1.0.0"
    workspace: WorkspaceOut
    is_demo: bool
    property: PropertyView
    completeness: CompletenessResponse
    requirements: list[Requirement]
    documents: list[DocumentSummaryResponse]
    findings: list[FindingResponse]
    findings_summary: dict[str, int]
    co_ownership: CoOwnershipSummaryResponse | None
    questions: list[QuestionResponse]
    evidence: list[EvidenceResponse]
    evidence_total: int
    truncated: bool
    last_updated: datetime


class WebConfigResponse(Schema):
    development_session: bool
    demo: bool
    max_upload_bytes: int


class SessionResponse(Schema):
    token: str
    expires_in_seconds: int
