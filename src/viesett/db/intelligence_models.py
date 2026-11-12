from datetime import date, datetime
from uuid import UUID

from pydantic import JsonValue
from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from viesett.db.models import Base, Identity, enum_column
from viesett.domain.intelligence import AnalysisKind, AsbestosVariant, ExtractionStatus


class DocumentAnalysis(Identity, Base):
    __tablename__ = "document_analyses"
    __table_args__ = (
        ForeignKeyConstraint(
            ["document_id", "workspace_id"],
            ["property_documents.id", "property_documents.workspace_id"],
            ondelete="CASCADE",
        ),
        UniqueConstraint("id", "workspace_id"),
        UniqueConstraint("id", "document_id", "workspace_id", name="uq_analysis_source"),
        UniqueConstraint("document_id", "generation"),
        CheckConstraint("generation > 0 AND page_count >= 0", name="analysis_bounds"),
    )
    document_id: Mapped[UUID]
    workspace_id: Mapped[UUID] = mapped_column(index=True)
    generation: Mapped[int]
    status: Mapped[ExtractionStatus] = mapped_column(enum_column(ExtractionStatus))
    automated_classification: Mapped[dict[str, JsonValue]] = mapped_column(JSON)
    co_metadata: Mapped[dict[str, JsonValue] | None] = mapped_column(JSON)
    manual_classification: Mapped[AnalysisKind | None] = mapped_column(
        Enum(AnalysisKind, name="manualclassification", native_enum=False, create_constraint=True)
    )
    correction_recorded: Mapped[bool]
    effective_classification: Mapped[AnalysisKind] = mapped_column(enum_column(AnalysisKind))
    association: Mapped[dict[str, JsonValue]] = mapped_column(JSON)
    fields: Mapped[list[dict[str, JsonValue]]] = mapped_column(JSON)
    evidence_ids: Mapped[list[str]] = mapped_column(JSON)
    page_count: Mapped[int]
    parser_version: Mapped[str] = mapped_column(String(80))
    source_sha256: Mapped[str] = mapped_column(String(64))
    # Reserved durably before parsing; intentionally excluded from every API DTO.
    artifact_storage_key: Mapped[str | None] = mapped_column(String(64))
    failure_code: Mapped[str | None] = mapped_column(String(80))
    retry_eligible: Mapped[bool]
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    @property
    def asbestos_variant(self) -> AsbestosVariant:
        value = next(
            (f.get("value") for f in self.fields if f.get("key") == "document.asbestos.variant"),
            None,
        )
        return AsbestosVariant(value) if isinstance(value, str) else AsbestosVariant.UNSPECIFIED


class DocumentTextArtifact(Identity, Base):
    __tablename__ = "document_text_artifacts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["analysis_id", "document_id", "workspace_id"],
            [
                "document_analyses.id",
                "document_analyses.document_id",
                "document_analyses.workspace_id",
            ],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["document_id", "workspace_id"],
            ["property_documents.id", "property_documents.workspace_id"],
            ondelete="CASCADE",
        ),
        UniqueConstraint("analysis_id"),
        CheckConstraint("page_count > 0", name="artifact_pages"),
    )
    document_id: Mapped[UUID]
    workspace_id: Mapped[UUID] = mapped_column(index=True)
    analysis_id: Mapped[UUID]
    parser_name: Mapped[str] = mapped_column(String(80))
    parser_version: Mapped[str] = mapped_column(String(80))
    page_count: Mapped[int]
    content_hash: Mapped[str] = mapped_column(String(64))
    storage_key: Mapped[str] = mapped_column(String(64), unique=True)


class DueDiligenceEvaluation(Identity, Base):
    __tablename__ = "due_diligence_evaluations"
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("property_workspaces.id", ondelete="CASCADE"), index=True
    )
    evaluation_date: Mapped[date] = mapped_column(Date)
    input_hash: Mapped[str] = mapped_column(String(64))
    identity_revision: Mapped[str | None] = mapped_column(String(64))
    requirements: Mapped[list[dict[str, JsonValue]]] = mapped_column(JSON)
    finding_ids: Mapped[list[str]] = mapped_column(JSON)
    rules: Mapped[list[dict[str, JsonValue]]] = mapped_column(JSON)
    inputs: Mapped[dict[str, JsonValue]] = mapped_column(JSON)
