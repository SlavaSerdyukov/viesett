import math
import unicodedata
from datetime import datetime
from enum import StrEnum
from typing import Literal, Self, cast
from uuid import UUID

from pydantic import Field, model_validator

from viesett.domain.base import Schema


class ResolutionStatus(StrEnum):
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"
    PARTIALLY_RESOLVED = "PARTIALLY_RESOLVED"
    NEEDS_SELECTION = "NEEDS_SELECTION"
    NOT_FOUND = "NOT_FOUND"
    UPSTREAM_UNAVAILABLE = "UPSTREAM_UNAVAILABLE"
    INVALID_SOURCE_RESPONSE = "INVALID_SOURCE_RESPONSE"


class SourceProvider(StrEnum):
    GRAR = "GRAR"
    HERITAGE = "HERITAGE"
    FLOOD = "FLOOD"


class EnrichmentStatus(StrEnum):
    IN_PROGRESS = "IN_PROGRESS"
    SUCCESS = "SUCCESS"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"
    MANUAL_OFFICIAL_LOOKUP_REQUIRED = "MANUAL_OFFICIAL_LOOKUP_REQUIRED"
    INVALID_SOURCE_RESPONSE = "INVALID_SOURCE_RESPONSE"


Position = tuple[float, float]
PolygonCoordinates = list[list[Position]]
MultiPolygonCoordinates = list[PolygonCoordinates]


class Geometry(Schema):
    type: Literal["Point", "Polygon", "MultiPolygon"]
    crs: Literal["EPSG:31370", "EPSG:3812", "EPSG:4326"]
    coordinates: Position | PolygonCoordinates | MultiPolygonCoordinates

    @model_validator(mode="after")
    def valid_geometry(self) -> Self:
        if self.type == "Point":
            if not isinstance(self.coordinates, tuple):
                raise ValueError("Point coordinates required")
            points = [self.coordinates]
        else:
            polygons = [self.coordinates] if self.type == "Polygon" else self.coordinates
            points = []
            if not polygons:
                raise ValueError("Empty geometry")
            for polygon in cast(MultiPolygonCoordinates, polygons):
                if not polygon:
                    raise ValueError("Empty polygon")
                for ring in polygon:
                    if len(ring) < 4 or ring[0] != ring[-1]:
                        raise ValueError("Polygon rings must be closed")
                    points.extend(ring)
        if len(points) > 2000 or any(not math.isfinite(v) for p in points for v in p):
            raise ValueError("Invalid or excessive geometry")
        if self.crs == "EPSG:4326" and any(
            not (-180 <= x <= 180 and -90 <= y <= 90) for x, y in points
        ):
            raise ValueError("Invalid WGS84 coordinates")
        return self


class OfficialObject(Schema):
    official_id: str = Field(min_length=1, max_length=100)
    source_uri: str = Field(min_length=1, max_length=500)
    source_version: str | None = Field(default=None, max_length=100)
    retrieved_at: datetime
    status: str = Field(min_length=1, max_length=80)


class OfficialAddress(OfficialObject):
    canonical_address: str = Field(min_length=1, max_length=500)
    street_name: str = Field(min_length=1, max_length=200)
    house_number: str = Field(min_length=1, max_length=30)
    box_number: str | None = Field(default=None, max_length=30)
    postal_code: str | None = Field(default=None, max_length=10)
    municipality: str = Field(min_length=1, max_length=200)
    municipality_code: str | None = Field(default=None, max_length=10)
    native_geometry: Geometry | None = None


class OfficialBuildingUnit(OfficialObject):
    function: str | None = Field(default=None, max_length=80)
    building_official_id: str = Field(min_length=1, max_length=100)
    address_official_ids: list[str] = Field(max_length=200)
    native_geometry: Geometry | None = None


class OfficialBuilding(OfficialObject):
    native_geometry: Geometry | None = None
    unit_official_ids: list[str] = Field(default_factory=list, max_length=500)


class OfficialParcel(OfficialObject):
    capakey: str = Field(min_length=1, max_length=30)
    address_official_ids: list[str] = Field(max_length=200)
    native_geometry: Geometry | None = None


class ResolutionRequest(Schema):
    query: str = Field(min_length=3, max_length=500)
    selected_address_object_id: str | None = Field(default=None, pattern=r"^[1-9][0-9]{0,15}$")
    selected_building_unit_object_id: str | None = Field(
        default=None, pattern=r"^[1-9][0-9]{0,15}$"
    )

    @model_validator(mode="after")
    def normalize_query(self) -> Self:
        self.query = " ".join(unicodedata.normalize("NFC", self.query).split())
        if len(self.query) < 3:
            raise ValueError("An address query is required")
        if self.selected_building_unit_object_id and not self.selected_address_object_id:
            raise ValueError("A selected unit requires a selected address")
        return self


class ResolutionResult(Schema):
    status: ResolutionStatus
    address: OfficialAddress | None = None
    selected_building_unit: OfficialBuildingUnit | None = None
    building: OfficialBuilding | None = None
    parcels: list[OfficialParcel] = Field(default_factory=list)
    address_candidates: list[OfficialAddress] = Field(default_factory=list)
    building_unit_candidates: list[OfficialBuildingUnit] = Field(default_factory=list)
    candidates_truncated: bool = False
    missing_relationships: list[str] = Field(default_factory=list)
    error_code: str | None = None


class ResolutionOut(ResolutionResult):
    id: UUID
    workspace_id: UUID
    input_address_query: str
    generation: int
    requested_at: datetime
    completed_at: datetime | None
    applied_to_snapshot: bool


class HeritageMatch(Schema):
    official_id: str = Field(min_length=1, max_length=100)
    source_uri: str = Field(min_length=1, max_length=500)
    title: str = Field(min_length=1, max_length=500)
    category: str = Field(min_length=1, max_length=80)
    type_uri: str = Field(min_length=1, max_length=500)
    type_label: str = Field(min_length=1, max_length=200)
    classification: Literal["DESIGNATION", "INVENTORY_ONLY", "OTHER"]
    designation_status: str | None = None
    match_basis: str = Field(min_length=1, max_length=200)
    retrieved_at: datetime


class SourceAttribution(Schema):
    provider: SourceProvider
    provider_name: str
    attribution_text: str
    source_reference: str
    terms_reference: str
    retrieved_at: datetime


class SourceRunOut(Schema):
    id: UUID
    workspace_id: UUID
    provider: SourceProvider
    status: EnrichmentStatus
    property_key: str | None
    identity_revision: str | None
    attempted_at: datetime
    retrieved_at: datetime | None
    error_code: str | None
    source_crs: str | None
    target_crs: str | None
    attribution_text: str
    source_reference: str
    terms_reference: str


class SourceState(Schema):
    provider: SourceProvider
    current_refresh_status: EnrichmentStatus | None
    last_attempt_at: datetime | None
    last_successful_retrieval: datetime | None
    stale: bool
    error_code: str | None = None


class FloodResult(Schema):
    # No automatic score contract is approved for this milestone. The schema cannot
    # accept a score or AVAILABLE result from a caller/test double by accident.
    status: Literal["MANUAL_OFFICIAL_LOOKUP_REQUIRED", "SOURCE_UNAVAILABLE", "NOT_APPLICABLE"]
    p_score: None = None
    g_score: None = None
    official_reference: str = "https://waterinfo.vlaanderen.be/informatieplicht"
    parcel_references: dict[str, str] = Field(default_factory=dict)


class PropertySnapshot(Schema):
    workspace_id: UUID
    resolution_status: ResolutionStatus | None
    latest_input_address_query: str | None
    snapshot_input_address_query: str | None
    property_key: str | None
    identity_revision: str | None
    last_successful_retrieval: datetime | None
    stale: bool
    address: OfficialAddress | None = None
    selected_building_unit: OfficialBuildingUnit | None = None
    building: OfficialBuilding | None = None
    parcels: list[OfficialParcel] = Field(default_factory=list)
    heritage: list[HeritageMatch] = Field(default_factory=list)
    flood: FloodResult
    sources: list[SourceAttribution] = Field(default_factory=list)
    source_states: list[SourceState] = Field(default_factory=list)
