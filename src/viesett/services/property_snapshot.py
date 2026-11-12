from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from viesett.db.property_models import (
    HeritageObservation,
    PropertyBuilding,
    PropertyBuildingUnit,
    PropertyIdentity,
    PropertyParcel,
    PropertyResolution,
    PublicEnrichmentRun,
)
from viesett.domain.property import (
    EnrichmentStatus,
    HeritageMatch,
    OfficialAddress,
    OfficialBuilding,
    OfficialBuildingUnit,
    OfficialParcel,
    PropertySnapshot,
    ResolutionOut,
    ResolutionResult,
    SourceAttribution,
    SourceProvider,
    SourceState,
)
from viesett.integrations.sources import ATTRIBUTIONS, flood_lookup
from viesett.services.ownership import owned_workspace


def resolution_out(row: PropertyResolution) -> ResolutionOut:
    result = (
        ResolutionResult.model_validate(row.result)
        if row.result
        else ResolutionResult(status=row.status)
    )
    return ResolutionOut(
        **result.model_dump(),
        id=row.id,
        workspace_id=row.workspace_id,
        input_address_query=row.input_address_query,
        generation=row.generation,
        requested_at=row.requested_at,
        completed_at=row.completed_at,
        applied_to_snapshot=row.applied_to_snapshot,
    )


async def latest_resolution(db: AsyncSession, workspace_id: UUID) -> PropertyResolution | None:
    row: PropertyResolution | None = await db.scalar(
        select(PropertyResolution)
        .where(
            PropertyResolution.workspace_id == workspace_id,
        )
        .order_by(PropertyResolution.generation.desc())
        .limit(1)
    )
    return row


def address_out(row: PropertyIdentity) -> OfficialAddress:
    # Response allowlist is intentionally separate from persistence metadata.
    return OfficialAddress.model_validate(
        {field: getattr(row, field) for field in OfficialAddress.model_fields}
    )


async def snapshot(db: AsyncSession, workspace_id: UUID, user_id: UUID) -> PropertySnapshot:
    # Serialize the multi-table read with mutations under READ COMMITTED.
    await owned_workspace(db, user_id, workspace_id, lock=True)
    latest = await latest_resolution(db, workspace_id)
    identity = await db.get(PropertyIdentity, workspace_id, populate_existing=True)
    parcel_rows = (
        await db.scalars(
            select(PropertyParcel)
            .where(
                PropertyParcel.workspace_id == workspace_id,
            )
            .order_by(PropertyParcel.official_id)
        )
    ).all()
    parcels = [OfficialParcel.model_validate(p) for p in parcel_rows]
    building = await db.scalar(
        select(PropertyBuilding).where(PropertyBuilding.workspace_id == workspace_id)
    )
    unit = await db.scalar(
        select(PropertyBuildingUnit).where(
            PropertyBuildingUnit.workspace_id == workspace_id,
            PropertyBuildingUnit.official_id
            == (identity.selected_unit_official_id if identity else None),
        )
    )
    runs = list(
        (
            await db.scalars(
                select(PublicEnrichmentRun)
                .where(
                    PublicEnrichmentRun.workspace_id == workspace_id,
                    PublicEnrichmentRun.property_key
                    == (identity.property_key if identity else None),
                )
                .order_by(PublicEnrichmentRun.attempted_at.desc(), PublicEnrichmentRun.id.desc())
            )
        ).all()
    )
    sources = []
    states = []
    heritage = []
    for provider in SourceProvider:
        attempts = [run for run in runs if run.provider == provider]
        recent = attempts[0] if attempts else None
        successful = next((run for run in attempts if run.status == EnrichmentStatus.SUCCESS), None)
        stale = bool(
            successful
            and (
                recent is not successful
                or (identity and successful.identity_revision != identity.revision)
            )
        )
        if provider == SourceProvider.GRAR and latest and not latest.applied_to_snapshot:
            stale = identity is not None
        states.append(
            SourceState(
                provider=provider,
                current_refresh_status=recent.status if recent else None,
                last_attempt_at=recent.attempted_at if recent else None,
                last_successful_retrieval=successful.retrieved_at if successful else None,
                stale=stale,
                error_code=recent.error_code if recent else None,
            )
        )
        if successful and successful.retrieved_at:
            sources.append(
                SourceAttribution(
                    provider=provider,
                    provider_name=ATTRIBUTIONS[provider][0],
                    attribution_text=successful.attribution_text,
                    source_reference=successful.source_reference,
                    terms_reference=successful.terms_reference,
                    retrieved_at=successful.retrieved_at,
                )
            )
        if provider == SourceProvider.HERITAGE and successful:
            heritage = [
                HeritageMatch.model_validate(h)
                for h in (
                    await db.scalars(
                        select(HeritageObservation)
                        .where(
                            HeritageObservation.run_id == successful.id,
                            HeritageObservation.workspace_id == workspace_id,
                        )
                        .order_by(
                            HeritageObservation.source_uri,
                        )
                    )
                ).all()
            ]
    return PropertySnapshot(
        workspace_id=workspace_id,
        resolution_status=latest.status if latest else None,
        latest_input_address_query=latest.input_address_query if latest else None,
        snapshot_input_address_query=identity.input_address_query if identity else None,
        property_key=identity.property_key if identity else None,
        identity_revision=identity.revision if identity else None,
        last_successful_retrieval=identity.retrieved_at if identity else None,
        stale=bool(identity and latest and not latest.applied_to_snapshot),
        address=address_out(identity) if identity else None,
        selected_building_unit=OfficialBuildingUnit.model_validate(unit) if unit else None,
        building=OfficialBuilding.model_validate(building) if building else None,
        parcels=parcels,
        heritage=heritage,
        flood=flood_lookup(parcels),
        sources=sources,
        source_states=states,
    )
