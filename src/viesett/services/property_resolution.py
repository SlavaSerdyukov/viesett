import asyncio
import hashlib
import json
from uuid import UUID

from fastapi import HTTPException
from pydantic import JsonValue
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from viesett.core.config import Settings
from viesett.db.models import utcnow
from viesett.db.property_models import (
    PropertyBuilding,
    PropertyBuildingUnit,
    PropertyIdentity,
    PropertyParcel,
    PropertyResolution,
    PublicEnrichmentRun,
)
from viesett.domain.property import (
    EnrichmentStatus,
    ResolutionOut,
    ResolutionRequest,
    ResolutionResult,
    ResolutionStatus,
    SourceProvider,
)
from viesett.domain.types import WorkspaceStatus
from viesett.integrations.sources import PublicSources, attribution
from viesett.services.official_evidence import grar_facts, synchronize_official_evidence
from viesett.services.ownership import owned_workspace
from viesett.services.property_snapshot import resolution_out

SUCCESSFUL_RESOLUTIONS = {ResolutionStatus.RESOLVED, ResolutionStatus.PARTIALLY_RESOLVED}


def without_retrieval_times(value: JsonValue) -> JsonValue:
    if isinstance(value, dict):
        return {
            key: without_retrieval_times(item)
            for key, item in value.items()
            if key != "retrieved_at"
        }
    if isinstance(value, list):
        return [without_retrieval_times(item) for item in value]
    return value


def identity_revision(result: ResolutionResult) -> str:
    normalized = without_retrieval_times(result.model_dump(mode="json"))
    return hashlib.sha256(
        json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def make_run(
    workspace_id: UUID,
    provider: SourceProvider,
    status: EnrichmentStatus,
    identity: PropertyIdentity | None,
    *,
    error_code: str | None = None,
) -> PublicEnrichmentRun:
    now = utcnow()
    credit = attribution(provider, now)
    return PublicEnrichmentRun(
        workspace_id=workspace_id,
        provider=provider,
        status=status,
        property_key=identity.property_key if identity else None,
        identity_revision=identity.revision if identity else None,
        retrieved_at=now if status == EnrichmentStatus.SUCCESS else None,
        error_code=error_code,
        attribution_text=credit.attribution_text,
        source_reference=credit.source_reference,
        terms_reference=credit.terms_reference,
    )


async def store_identity(
    db: AsyncSession,
    user_id: UUID,
    workspace_id: UUID,
    request: ResolutionRequest,
    result: ResolutionResult,
) -> PropertyIdentity:
    address = result.address
    if address is None:
        raise ValueError("A successful resolution requires an official address")
    row = await db.get(PropertyIdentity, workspace_id, populate_existing=True)
    revision = identity_revision(result)
    if row is not None and row.revision != revision:
        await synchronize_official_evidence(
            db, user_id, workspace_id, SourceProvider.HERITAGE, [], utcnow()
        )
    values = address.model_dump()
    unit = result.selected_building_unit
    values.update(
        {
            "input_address_query": request.query,
            "property_key": f"grar:{address.official_id}:{unit.official_id if unit else '-'}",
            "revision": revision,
            "resolved_at": utcnow(),
            "resolution_status": result.status,
            "selected_unit_official_id": unit.official_id if unit else None,
        }
    )
    if row is None:
        row = PropertyIdentity(workspace_id=workspace_id, **values)
        db.add(row)
    else:
        for name, value in values.items():
            setattr(row, name, value)
    await db.flush()
    await db.execute(
        delete(PropertyBuildingUnit).where(PropertyBuildingUnit.workspace_id == workspace_id)
    )
    await db.execute(delete(PropertyBuilding).where(PropertyBuilding.workspace_id == workspace_id))
    await db.execute(delete(PropertyParcel).where(PropertyParcel.workspace_id == workspace_id))
    if unit:
        db.add(PropertyBuildingUnit(workspace_id=workspace_id, **unit.model_dump()))
    if result.building:
        db.add(PropertyBuilding(workspace_id=workspace_id, **result.building.model_dump()))
    for parcel in result.parcels:
        db.add(PropertyParcel(workspace_id=workspace_id, **parcel.model_dump()))
    await db.flush()
    await synchronize_official_evidence(
        db, user_id, workspace_id, SourceProvider.GRAR, grar_facts(result), row.retrieved_at
    )
    return row


async def resolve_property(
    db: AsyncSession,
    user_id: UUID,
    workspace_id: UUID,
    request: ResolutionRequest,
    sources: PublicSources,
    settings: Settings,
) -> ResolutionOut:
    workspace = await owned_workspace(db, user_id, workspace_id, lock=True)
    if workspace.status != WorkspaceStatus.ACTIVE:
        raise HTTPException(409, "Workspace is archived")
    generation = (
        await db.scalar(
            select(func.max(PropertyResolution.generation)).where(
                PropertyResolution.workspace_id == workspace_id,
            )
        )
        or 0
    ) + 1
    attempt = PropertyResolution(
        workspace_id=workspace_id,
        input_address_query=request.query,
        generation=generation,
        status=ResolutionStatus.IN_PROGRESS,
    )
    db.add(attempt)
    await db.commit()  # No database locks are held during official network calls.
    if not sources.enabled:
        result = ResolutionResult(
            status=ResolutionStatus.UPSTREAM_UNAVAILABLE,
            error_code="official_sources_disabled_or_unreviewed",
        )
    else:
        try:
            async with asyncio.timeout(settings.source_operation_timeout):
                result = await sources.grar.resolve(request)
        except TimeoutError:
            result = ResolutionResult(
                status=ResolutionStatus.UPSTREAM_UNAVAILABLE, error_code="source_operation_timeout"
            )
    workspace = await owned_workspace(db, user_id, workspace_id, lock=True)
    if workspace.status != WorkspaceStatus.ACTIVE:
        abandoned = await db.get(PropertyResolution, attempt.id, populate_existing=True)
        if abandoned:
            abandoned.status = ResolutionStatus.UPSTREAM_UNAVAILABLE
            abandoned.completed_at = utcnow()
            abandoned.result = ResolutionResult(
                status=ResolutionStatus.UPSTREAM_UNAVAILABLE,
                error_code="workspace_archived_during_resolution",
            ).model_dump(mode="json")
            await db.commit()
        raise HTTPException(409, "Workspace was archived during resolution")
    refreshed = await db.get(PropertyResolution, attempt.id, populate_existing=True)
    if refreshed is None:
        raise HTTPException(404, "Not found")
    attempt = refreshed
    latest_generation = await db.scalar(
        select(func.max(PropertyResolution.generation)).where(
            PropertyResolution.workspace_id == workspace_id,
        )
    )
    current = attempt.generation == latest_generation
    attempt.status = result.status
    attempt.result = result.model_dump(mode="json")
    attempt.completed_at = utcnow()
    identity = await db.get(PropertyIdentity, workspace_id, populate_existing=True)
    if current and result.status in SUCCESSFUL_RESOLUTIONS:
        identity = await store_identity(db, user_id, workspace_id, request, result)
        workspace.canonical_address = identity.canonical_address
        attempt.applied_to_snapshot = True
    state = (
        EnrichmentStatus.SUCCESS
        if result.status in SUCCESSFUL_RESOLUTIONS
        else EnrichmentStatus.INVALID_SOURCE_RESPONSE
        if result.status == ResolutionStatus.INVALID_SOURCE_RESPONSE
        else EnrichmentStatus.SOURCE_UNAVAILABLE
        if result.status == ResolutionStatus.UPSTREAM_UNAVAILABLE
        else EnrichmentStatus.NOT_APPLICABLE
    )
    run = make_run(workspace_id, SourceProvider.GRAR, state, identity, error_code=result.error_code)
    if result.status in SUCCESSFUL_RESOLUTIONS and result.address:
        unit_id = (
            result.selected_building_unit.official_id if result.selected_building_unit else "-"
        )
        run.property_key = f"grar:{result.address.official_id}:{unit_id}"
        run.identity_revision = identity_revision(result)
    run.attempted_at = attempt.requested_at
    db.add(run)
    await db.commit()
    return resolution_out(attempt)
