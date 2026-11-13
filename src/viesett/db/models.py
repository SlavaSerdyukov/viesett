from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import JsonValue
from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    MetaData,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from viesett.domain.types import (
    Authority,
    DocumentKind,
    DocumentStatus,
    PolicyType,
    Region,
    Severity,
    SourceType,
    WorkspaceStatus,
)


def utcnow() -> datetime:
    return datetime.now(UTC)


def enum_column(enum: type[StrEnum]) -> Enum:
    return Enum(enum, native_enum=False, create_constraint=True)


class Base(DeclarativeBase):
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(column_0_label)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )


class Identity:
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Account(Identity, Base):
    __tablename__ = "accounts"


class ApiToken(Identity, Base):
    __tablename__ = "api_tokens"
    __table_args__ = (UniqueConstraint("id", "user_id"),)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class PropertyWorkspace(Identity, Base):
    __tablename__ = "property_workspaces"
    owner_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[WorkspaceStatus] = mapped_column(
        enum_column(WorkspaceStatus), default=WorkspaceStatus.ACTIVE
    )
    canonical_address: Mapped[str | None] = mapped_column(String(500))
    region: Mapped[Region] = mapped_column(enum_column(Region), default=Region.FLANDERS)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PropertyDocument(Identity, Base):
    __tablename__ = "property_documents"
    __table_args__ = (
        UniqueConstraint("id", "workspace_id"),
        Index(
            "uq_document_live_hash",
            "workspace_id",
            "sha256",
            unique=True,
            postgresql_where=text("status != 'DELETED'"),
        ),
        CheckConstraint("size_bytes > 0", name="positive_size"),
        ForeignKeyConstraint(
            ["supersedes_document_id", "workspace_id"],
            ["property_documents.id", "property_documents.workspace_id"],
        ),
    )
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("property_workspaces.id", ondelete="CASCADE"), index=True
    )
    original_filename: Mapped[str] = mapped_column(String(180))
    media_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    document_kind: Mapped[DocumentKind] = mapped_column(enum_column(DocumentKind))
    status: Mapped[DocumentStatus] = mapped_column(enum_column(DocumentStatus))
    safety_reason: Mapped[str] = mapped_column(String(80))
    storage_key: Mapped[str] = mapped_column(String(64), unique=True)
    supersedes_document_id: Mapped[UUID | None] = mapped_column()


class EvidenceItem(Identity, Base):
    __tablename__ = "evidence_items"
    __table_args__ = (
        UniqueConstraint("id", "workspace_id"),
        ForeignKeyConstraint(
            ["document_id", "workspace_id"],
            ["property_documents.id", "property_documents.workspace_id"],
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)", name="confidence_range"
        ),
        CheckConstraint("source_type != 'AI' OR authority = 'INFERRED'", name="ai_inferred"),
        CheckConstraint(
            "authority != 'UNVERIFIED' OR (source_type = 'MANUAL' "
            "AND document_id IS NULL AND provider IS NULL)",
            name="user_context_unverified",
        ),
        ForeignKeyConstraint(
            ["supersedes_evidence_id", "workspace_id"],
            ["evidence_items.id", "evidence_items.workspace_id"],
            ondelete="CASCADE",
        ),
        Index(
            "uq_current_official_fact",
            "workspace_id",
            "provider",
            "fact_identifier",
            unique=True,
            postgresql_where=text("provider IS NOT NULL AND superseded_at IS NULL"),
        ),
        CheckConstraint(
            "provider IS NULL OR (authority = 'OFFICIAL' AND source_type = 'PUBLIC_REGISTRY')",
            name="provider_authority",
        ),
        CheckConstraint(
            "provider IS NULL OR (provider IN ('GRAR', 'HERITAGE') "
            "AND fact_identifier IS NOT NULL AND source_uri IS NOT NULL "
            "AND source_retrieved_at IS NOT NULL AND last_seen_at IS NOT NULL)",
            name="official_provenance_complete",
        ),
        CheckConstraint(
            "source_version IS NULL OR source_version NOT LIKE 'document-extractor:%' OR "
            "(authority = 'DOCUMENTED' AND source_type = 'DOCUMENT' AND document_id IS NOT NULL "
            "AND source_locator ->> 'document_id' IS NOT NULL "
            "AND source_locator ->> 'document_id' = document_id::text "
            "AND source_locator ->> 'page' IS NOT NULL "
            "AND source_locator ->> 'parser_version' IS NOT NULL)",
            name="document_extractor_provenance",
        ),
    )
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("property_workspaces.id", ondelete="CASCADE"), index=True
    )
    document_id: Mapped[UUID | None] = mapped_column()
    key: Mapped[str] = mapped_column(String(120))
    typed_value: Mapped[dict[str, JsonValue]] = mapped_column(JSON)
    source_type: Mapped[SourceType] = mapped_column(enum_column(SourceType))
    source_locator: Mapped[dict[str, JsonValue]] = mapped_column(JSON)
    authority: Mapped[Authority] = mapped_column(enum_column(Authority))
    confidence: Mapped[float | None]
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    provider: Mapped[str | None] = mapped_column(String(40))
    fact_identifier: Mapped[str | None] = mapped_column(String(250))
    source_uri: Mapped[str | None] = mapped_column(String(500))
    source_version: Mapped[str | None] = mapped_column(String(100))
    source_retrieved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    supersedes_evidence_id: Mapped[UUID | None] = mapped_column()


class Finding(Identity, Base):
    __tablename__ = "findings"
    __table_args__ = (UniqueConstraint("id", "workspace_id"),)
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("property_workspaces.id", ondelete="CASCADE"), index=True
    )
    code: Mapped[str] = mapped_column(String(120))
    severity: Mapped[Severity] = mapped_column(enum_column(Severity))
    summary: Mapped[str] = mapped_column(String(500))
    details: Mapped[str | None] = mapped_column(String(4000))
    provenance: Mapped[dict[str, JsonValue]] = mapped_column(JSON)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class FindingEvidence(Base):
    __tablename__ = "finding_evidence"
    __table_args__ = (
        ForeignKeyConstraint(
            ["finding_id", "workspace_id"],
            ["findings.id", "findings.workspace_id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["evidence_id", "workspace_id"],
            ["evidence_items.id", "evidence_items.workspace_id"],
            ondelete="CASCADE",
        ),
    )
    finding_id: Mapped[UUID] = mapped_column(primary_key=True)
    evidence_id: Mapped[UUID] = mapped_column(primary_key=True)
    workspace_id: Mapped[UUID] = mapped_column()


class DocumentRequestDraft(Identity, Base):
    __tablename__ = "document_request_drafts"
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("property_workspaces.id", ondelete="CASCADE"), index=True
    )
    requested_document_types: Mapped[list[str]] = mapped_column(JSON)
    generated_text: Mapped[str] = mapped_column(String(2000))
    language: Mapped[str] = mapped_column(String(2))


class PolicyVersion(Identity, Base):
    __tablename__ = "policy_versions"
    __table_args__ = (
        UniqueConstraint("policy_type", "version"),
        Index(
            "uq_policy_current", "policy_type", unique=True, postgresql_where=text("current = true")
        ),
    )
    policy_type: Mapped[PolicyType] = mapped_column(enum_column(PolicyType))
    version: Mapped[str] = mapped_column(String(40))
    text: Mapped[str] = mapped_column(String(10000))
    current: Mapped[bool] = mapped_column(Boolean, default=True)


class UserPolicyAcknowledgement(Identity, Base):
    __tablename__ = "user_policy_acknowledgements"
    __table_args__ = (UniqueConstraint("user_id", "policy_version_id"),)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), index=True)
    policy_version_id: Mapped[UUID] = mapped_column(ForeignKey("policy_versions.id"))
    acknowledged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Processor(Identity, Base):
    __tablename__ = "processors"
    name: Mapped[str] = mapped_column(String(120), unique=True)
    purpose: Mapped[str] = mapped_column(String(200))
    data_categories: Mapped[list[str]] = mapped_column(JSON)
    region: Mapped[str] = mapped_column(String(80))
    dpa_reviewed: Mapped[bool] = mapped_column(Boolean, default=False)
    training_use_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    international_transfer_mechanism: Mapped[str | None] = mapped_column(String(200))
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    __table_args__ = (CheckConstraint("training_use_allowed = false", name="no_training"),)


class ObjectDeletionTask(Identity, Base):
    """Transactional outbox: retry deletion after crashes without retaining user content."""

    __tablename__ = "object_deletion_tasks"
    storage_key: Mapped[str] = mapped_column(String(64), unique=True)
    not_before: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
