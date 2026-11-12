from datetime import date, datetime
from uuid import UUID

from pydantic import JsonValue
from sqlalchemy import (
    JSON,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from viesett.db.models import Base, Identity, utcnow


class CoOwnershipEvaluation(Identity, Base):
    __tablename__ = "co_ownership_evaluations"
    __table_args__ = (UniqueConstraint("id", "workspace_id"),)
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("property_workspaces.id", ondelete="CASCADE"), index=True
    )
    evaluation_date: Mapped[date] = mapped_column(Date)
    input_hash: Mapped[str] = mapped_column(String(64))
    identity_revision: Mapped[str | None] = mapped_column(String(64))
    result: Mapped[dict[str, JsonValue]] = mapped_column(JSON)
    inputs: Mapped[dict[str, JsonValue]] = mapped_column(JSON)


class CoOwnershipIdentityRecord(Base):
    __tablename__ = "co_ownership_identities"
    __table_args__ = (
        ForeignKeyConstraint(
            ["evaluation_id", "workspace_id"],
            ["co_ownership_evaluations.id", "co_ownership_evaluations.workspace_id"],
            ondelete="CASCADE",
        ),
    )
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("property_workspaces.id", ondelete="CASCADE"), primary_key=True
    )
    evaluation_id: Mapped[UUID]
    association_name: Mapped[str | None] = mapped_column(String(200))
    enterprise_number: Mapped[str | None] = mapped_column(String(10))
    building_address: Mapped[str | None] = mapped_column(String(300))
    syndic_name: Mapped[str | None] = mapped_column(String(200))
    syndic_enterprise_number: Mapped[str | None] = mapped_column(String(10))
    lot_identifier: Mapped[str | None] = mapped_column(String(60))
    private_unit_designation: Mapped[str | None] = mapped_column(String(100))
    ownership_share: Mapped[dict[str, JsonValue] | None] = mapped_column(JSON)
    attached_lots: Mapped[list[str]] = mapped_column(JSON)
    source_document_ids: Mapped[list[str]] = mapped_column(JSON)
    evidence_ids: Mapped[list[str]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PlannedWorkRecord(Identity, Base):
    __tablename__ = "planned_works"
    __table_args__ = (
        ForeignKeyConstraint(
            ["evaluation_id", "workspace_id"],
            ["co_ownership_evaluations.id", "co_ownership_evaluations.workspace_id"],
            ondelete="CASCADE",
        ),
    )
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("property_workspaces.id", ondelete="CASCADE"), index=True
    )
    evaluation_id: Mapped[UUID]
    work_key: Mapped[str] = mapped_column(String(80))
    decision_status: Mapped[str] = mapped_column(String(30))
    result: Mapped[dict[str, JsonValue]] = mapped_column(JSON)
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
