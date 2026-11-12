import asyncio
from uuid import UUID

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from viesett.core.config import Settings
from viesett.db.models import utcnow
from viesett.db.property_models import (
    HeritageObservation,
    PropertyBuilding,
    PropertyIdentity,
    PropertyParcel,
    PublicEnrichmentRun,
)
from viesett.domain.property import (
    EnrichmentStatus,
    Geometry,
    HeritageMatch,
    PropertySnapshot,
    ResolutionStatus,
    SourceProvider,
)
from viesett.domain.types import WorkspaceStatus
from viesett.integrations.http import SourceError
from viesett.integrations.sources import PublicSources
from viesett.services.official_evidence import heritage_facts, synchronize_official_evidence
from viesett.services.ownership import owned_workspace
from viesett.services.property_resolution import make_run
from viesett.services.property_snapshot import latest_resolution, snapshot


async def refresh_enrichment(
    db: AsyncSession,
    user_id: UUID,
    workspace_id: UUID,
    sources: PublicSources,
    settings: Settings,
) -> PropertySnapshot:
    workspace = await owned_workspace(db, user_id, workspace_id, lock=True)
    if workspace.status != WorkspaceStatus.ACTIVE:
        raise HTTPException(409, "Workspace is archived")
    identity = await db.get(PropertyIdentity, workspace_id, populate_existing=True)
    latest = await latest_resolution(db, workspace_id)
    if identity is None or latest is None:
        raise HTTPException(409, "Resolve an official property before enrichment")
    if latest.input_address_query != identity.input_address_query or latest.status in {
        ResolutionStatus.IN_PROGRESS,
        ResolutionStatus.NEEDS_SELECTION,
        ResolutionStatus.NOT_FOUND,
        ResolutionStatus.INVALID_SOURCE_RESPONSE,
    }:
        raise HTTPException(409, "Resolve the current property selection before enrichment")
    building = await db.scalar(
        select(PropertyBuilding).where(
            PropertyBuilding.workspace_id == workspace_id,
        )
    )
    geometry = (
        Geometry.model_validate(building.native_geometry)
        if building and building.native_geometry
        else None
    )
    revision, property_key = identity.revision, identity.property_key
    run = make_run(workspace_id, SourceProvider.HERITAGE, EnrichmentStatus.IN_PROGRESS, identity)
    db.add(run)
    await db.commit()
    matches: list[HeritageMatch] = []
    state = EnrichmentStatus.SUCCESS
    code = None
    if not sources.enabled:
        state, code = EnrichmentStatus.SOURCE_UNAVAILABLE, "official_sources_disabled_or_unreviewed"
    elif geometry is None or geometry.type == "Point":
        state, code = EnrichmentStatus.NOT_APPLICABLE, "precise_property_area_unavailable"
    else:
        try:
            async with asyncio.timeout(settings.source_operation_timeout):
                matches = await sources.heritage.lookup(geometry)
        except SourceError as error:
            state = (
                EnrichmentStatus.INVALID_SOURCE_RESPONSE
                if error.invalid
                else EnrichmentStatus.SOURCE_UNAVAILABLE
            )
            code = error.code
        except ValidationError:
            state, code = EnrichmentStatus.INVALID_SOURCE_RESPONSE, "invalid_heritage_contract"
        except (TimeoutError, ValueError):
            state, code = EnrichmentStatus.SOURCE_UNAVAILABLE, "heritage_operation_unavailable"
    workspace = await owned_workspace(db, user_id, workspace_id, lock=True)
    current = await db.get(PropertyIdentity, workspace_id, populate_existing=True)
    if (
        workspace.status != WorkspaceStatus.ACTIVE
        or current is None
        or current.revision != revision
    ):
        abandoned = await db.get(PublicEnrichmentRun, run.id, populate_existing=True)
        if abandoned:
            abandoned.status = EnrichmentStatus.NOT_APPLICABLE
            abandoned.error_code = "property_changed_during_enrichment"
            await db.commit()
        raise HTTPException(409, "Property changed during enrichment; refresh again")
    refreshed = await db.get(PublicEnrichmentRun, run.id, populate_existing=True)
    if refreshed is None:
        raise HTTPException(404, "Not found")
    run = refreshed
    run.status, run.error_code = state, code
    run.retrieved_at = utcnow() if state == EnrichmentStatus.SUCCESS else None
    run.source_crs = geometry.crs if geometry else None
    run.target_crs = "EPSG:4326" if geometry else None
    newest = await db.scalar(
        select(PublicEnrichmentRun.id)
        .where(
            PublicEnrichmentRun.workspace_id == workspace_id,
            PublicEnrichmentRun.provider == SourceProvider.HERITAGE,
            PublicEnrichmentRun.property_key == property_key,
        )
        .order_by(PublicEnrichmentRun.attempted_at.desc(), PublicEnrichmentRun.id.desc())
        .limit(1)
    )
    if state == EnrichmentStatus.SUCCESS:
        for match in matches:
            db.add(
                HeritageObservation(run_id=run.id, workspace_id=workspace_id, **match.model_dump())
            )
        if newest == run.id:
            await synchronize_official_evidence(
                db,
                user_id,
                workspace_id,
                SourceProvider.HERITAGE,
                heritage_facts(matches),
                utcnow(),
            )
    # This is a verification path, never an automatically obtained flood score.
    has_parcel = await db.scalar(
        select(PropertyParcel.id).where(PropertyParcel.workspace_id == workspace_id).limit(1)
    )
    flood_state = (
        EnrichmentStatus.MANUAL_OFFICIAL_LOOKUP_REQUIRED
        if has_parcel
        else EnrichmentStatus.NOT_APPLICABLE
    )
    db.add(make_run(workspace_id, SourceProvider.FLOOD, flood_state, current))
    await db.commit()
    return await snapshot(db, workspace_id, user_id)
