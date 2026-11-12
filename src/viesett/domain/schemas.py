from datetime import date, datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import Field, model_validator

from viesett.domain.base import Schema as Schema
from viesett.domain.intelligence import AnalysisOut, EvaluationOut
from viesett.domain.property import PropertySnapshot, ResolutionOut, SourceRunOut
from viesett.domain.types import (
    Authority,
    DocumentKind,
    DocumentStatus,
    EpcLabel,
    PolicyType,
    Region,
    Severity,
    SourceType,
    WorkspaceStatus,
)


class WorkspaceCreate(Schema):
    canonical_address: str | None = Field(default=None, min_length=1, max_length=500)


class WorkspaceOut(Schema):
    id: UUID
    owner_user_id: UUID
    status: WorkspaceStatus
    canonical_address: str | None
    region: Region
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None


class WorkspaceUpdate(Schema):
    status: WorkspaceStatus


class DocumentOut(Schema):
    id: UUID
    workspace_id: UUID
    original_filename: str
    media_type: str
    size_bytes: int
    sha256: str
    document_kind: DocumentKind
    status: DocumentStatus
    safety_reason: str
    created_at: datetime
    supersedes_document_id: UUID | None


class SourceLocator(Schema):
    document_id: UUID | None = None
    page: int | None = Field(default=None, ge=1)
    section: str | None = Field(default=None, max_length=200)
    source_identifier: str | None = Field(default=None, max_length=200)
    registry: str | None = Field(default=None, max_length=100)
    uri: str | None = Field(default=None, max_length=500)
    start_offset: int | None = Field(default=None, ge=0)
    end_offset: int | None = Field(default=None, gt=0)
    parser_version: str | None = Field(default=None, max_length=80)

    @model_validator(mode="after")
    def nonempty(self) -> Self:
        if not any(self.model_dump().values()):
            raise ValueError("A source locator is required")
        if self.start_offset is not None and (
            self.end_offset is None or self.end_offset <= self.start_offset
        ):
            raise ValueError("Invalid source text span")
        return self


class TypedValue(Schema):
    kind: Literal["text", "integer", "decimal", "boolean", "date", "epc_label"]
    value: str | int | float | bool

    @model_validator(mode="after")
    def matches_kind(self) -> Self:
        expected: dict[str, tuple[type, ...]] = {
            "text": (str,),
            "integer": (int,),
            "decimal": (float, int),
            "boolean": (bool,),
            "date": (str,),
            "epc_label": (str,),
        }
        if type(self.value) not in expected[self.kind]:
            raise ValueError("Value must match its declared type")
        if self.kind == "date":
            date.fromisoformat(str(self.value))
        if self.kind == "epc_label":
            EpcLabel(str(self.value))
        if isinstance(self.value, str) and len(self.value) > 2000:
            raise ValueError("Evidence values must be bounded")
        return self


class EvidenceCreate(Schema):
    document_id: UUID | None = None
    key: str = Field(min_length=1, max_length=120, pattern=r"^[a-z][a-z0-9_.]*$")
    typed_value: TypedValue
    source_type: SourceType
    source_locator: SourceLocator
    authority: Authority
    confidence: float | None = Field(default=None, ge=0, le=1)
    observed_at: datetime | None = None

    @model_validator(mode="after")
    def provenance(self) -> Self:
        if self.source_type == SourceType.AI and self.authority != Authority.INFERRED:
            raise ValueError("AI evidence must be inferred")
        if self.source_type == SourceType.DOCUMENT and self.document_id is None:
            raise ValueError("Document evidence requires a document")
        if self.authority == Authority.OFFICIAL and self.source_type != SourceType.PUBLIC_REGISTRY:
            raise ValueError("Official authority requires an official registry source")
        if self.authority == Authority.DOCUMENTED and self.document_id is None:
            raise ValueError("Documented authority requires a document")
        return self


class EvidenceOut(EvidenceCreate):
    id: UUID
    workspace_id: UUID
    created_at: datetime
    provider: str | None = None
    fact_identifier: str | None = None
    source_uri: str | None = None
    source_version: str | None = None
    source_retrieved_at: datetime | None = None
    last_seen_at: datetime | None = None
    superseded_at: datetime | None = None
    supersedes_evidence_id: UUID | None = None


class FindingProvenance(Schema):
    method: Literal["deterministic", "manual", "ai"]
    source: str = Field(min_length=1, max_length=120)
    version: str = Field(min_length=1, max_length=40)
    rule_code: str | None = None
    evaluation_id: UUID | None = None
    evaluation_date: date | None = None
    input_hash: str | None = None
    jurisdiction: str | None = None
    effective_from: date | None = None
    effective_to: date | None = None
    reviewed_at: date | None = None
    official_source_name: str | None = None
    official_source_reference: str | None = None


class FindingCreate(Schema):
    code: str = Field(min_length=1, max_length=120)
    severity: Severity
    summary: str = Field(min_length=1, max_length=500)
    details: str | None = Field(default=None, max_length=4000)
    evidence_ids: list[UUID] = Field(default_factory=list, max_length=100)
    provenance: FindingProvenance


class FindingOut(FindingCreate):
    id: UUID
    workspace_id: UUID
    created_at: datetime
    resolved_at: datetime | None


class DraftCreate(Schema):
    requested_document_types: list[DocumentKind] = Field(min_length=1, max_length=11)
    language: Literal["en", "nl"] = "en"


class DraftOut(DraftCreate):
    id: UUID
    workspace_id: UUID
    generated_text: str
    created_at: datetime


class PolicyOut(Schema):
    id: UUID
    policy_type: PolicyType
    version: str
    text: str
    current: bool
    created_at: datetime


class AcknowledgementCreate(Schema):
    policy_version_id: UUID


class AcknowledgementOut(Schema):
    policy_version_id: UUID
    policy_type: PolicyType
    policy_version: str
    acknowledged_at: datetime


class AccountOut(Schema):
    id: UUID
    created_at: datetime


class ExportOut(Schema):
    account: AccountOut
    policy_acknowledgements: list[AcknowledgementOut]
    workspaces: list[WorkspaceOut]
    documents: list[DocumentOut]
    evidence: list[EvidenceOut]
    findings: list[FindingOut]
    document_request_drafts: list[DraftOut]
    property_resolutions: list[ResolutionOut] = Field(default_factory=list)
    property_snapshots: list[PropertySnapshot] = Field(default_factory=list)
    public_enrichment_runs: list[SourceRunOut] = Field(default_factory=list)
    document_analyses: list[AnalysisOut] = Field(default_factory=list)
    due_diligence_evaluations: list[EvaluationOut] = Field(default_factory=list)
