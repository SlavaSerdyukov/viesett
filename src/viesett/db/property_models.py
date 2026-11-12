from datetime import datetime
from uuid import UUID

from pydantic import JsonValue
from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from viesett.db.models import Base, Identity, enum_column, utcnow
from viesett.domain.property import EnrichmentStatus, ResolutionStatus, SourceProvider


class PropertyResolution(Identity, Base):
    __tablename__ = "property_resolutions"
    __table_args__ = (UniqueConstraint("workspace_id", "generation"),)
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("property_workspaces.id", ondelete="CASCADE"), index=True
    )
    input_address_query: Mapped[str] = mapped_column(String(500))
    generation: Mapped[int]
    status: Mapped[ResolutionStatus] = mapped_column(enum_column(ResolutionStatus))
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    applied_to_snapshot: Mapped[bool] = mapped_column(Boolean, default=False)
    # Validated exceptional choices and result, never arbitrary provider JSON.
    result: Mapped[dict[str, JsonValue]] = mapped_column(JSON, default=dict)


class OfficialSourceFields:
    official_id: Mapped[str] = mapped_column(String(100))
    source_uri: Mapped[str] = mapped_column(String(500))
    source_version: Mapped[str | None] = mapped_column(String(100))
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(80))
    native_geometry: Mapped[dict[str, JsonValue] | None] = mapped_column(JSON)


class PropertyIdentity(OfficialSourceFields, Base):
    """Normalized current official address identity; history lives in evidence/attempts."""

    __tablename__ = "property_identities"
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("property_workspaces.id", ondelete="CASCADE"), primary_key=True
    )
    input_address_query: Mapped[str] = mapped_column(String(500))
    property_key: Mapped[str] = mapped_column(String(150))
    revision: Mapped[str] = mapped_column(String(64))
    resolved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    resolution_status: Mapped[ResolutionStatus] = mapped_column(enum_column(ResolutionStatus))
    selected_unit_official_id: Mapped[str | None] = mapped_column(String(100))
    canonical_address: Mapped[str] = mapped_column(String(500))
    street_name: Mapped[str] = mapped_column(String(200))
    house_number: Mapped[str] = mapped_column(String(30))
    box_number: Mapped[str | None] = mapped_column(String(30))
    postal_code: Mapped[str | None] = mapped_column(String(10))
    municipality: Mapped[str] = mapped_column(String(200))
    municipality_code: Mapped[str | None] = mapped_column(String(10))


class PropertyBuildingUnit(OfficialSourceFields, Identity, Base):
    __tablename__ = "property_building_units"
    __table_args__ = (UniqueConstraint("workspace_id", "official_id"),)
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("property_identities.workspace_id", ondelete="CASCADE"), index=True
    )
    function: Mapped[str | None] = mapped_column(String(80))
    building_official_id: Mapped[str] = mapped_column(String(100))
    address_official_ids: Mapped[list[str]] = mapped_column(JSON)


class PropertyBuilding(OfficialSourceFields, Identity, Base):
    __tablename__ = "property_buildings"
    __table_args__ = (UniqueConstraint("workspace_id", "official_id"),)
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("property_identities.workspace_id", ondelete="CASCADE"), index=True
    )
    unit_official_ids: Mapped[list[str]] = mapped_column(JSON)


class PropertyParcel(OfficialSourceFields, Identity, Base):
    __tablename__ = "property_parcels"
    __table_args__ = (UniqueConstraint("workspace_id", "official_id"),)
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("property_identities.workspace_id", ondelete="CASCADE"), index=True
    )
    capakey: Mapped[str] = mapped_column(String(30))
    address_official_ids: Mapped[list[str]] = mapped_column(JSON)


class PublicEnrichmentRun(Identity, Base):
    __tablename__ = "public_enrichment_runs"
    __table_args__ = (UniqueConstraint("id", "workspace_id"),)
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("property_workspaces.id", ondelete="CASCADE"), index=True
    )
    provider: Mapped[SourceProvider] = mapped_column(enum_column(SourceProvider))
    status: Mapped[EnrichmentStatus] = mapped_column(enum_column(EnrichmentStatus))
    property_key: Mapped[str | None] = mapped_column(String(150))
    identity_revision: Mapped[str | None] = mapped_column(String(64))
    attempted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    retrieved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(100))
    source_crs: Mapped[str | None] = mapped_column(String(30))
    target_crs: Mapped[str | None] = mapped_column(String(30))
    attribution_text: Mapped[str] = mapped_column(String(200))
    source_reference: Mapped[str] = mapped_column(String(500))
    terms_reference: Mapped[str] = mapped_column(String(500))


class HeritageObservation(Identity, Base):
    __tablename__ = "heritage_observations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["run_id", "workspace_id"],
            ["public_enrichment_runs.id", "public_enrichment_runs.workspace_id"],
            ondelete="CASCADE",
        ),
        UniqueConstraint("run_id", "source_uri"),
    )
    run_id: Mapped[UUID] = mapped_column()
    workspace_id: Mapped[UUID] = mapped_column(index=True)
    official_id: Mapped[str] = mapped_column(String(100))
    source_uri: Mapped[str] = mapped_column(String(500))
    title: Mapped[str] = mapped_column(String(500))
    category: Mapped[str] = mapped_column(String(80))
    type_uri: Mapped[str] = mapped_column(String(500))
    type_label: Mapped[str] = mapped_column(String(200))
    classification: Mapped[str] = mapped_column(String(30))
    designation_status: Mapped[str | None] = mapped_column(String(200))
    match_basis: Mapped[str] = mapped_column(String(200))
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
