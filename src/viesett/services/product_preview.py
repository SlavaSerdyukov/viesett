import asyncio

from viesett.core.config import Settings
from viesett.db.models import utcnow
from viesett.domain.product import PreviewChoice, PreviewResponse, PropertyView
from viesett.domain.property import (
    ResolutionRequest,
    ResolutionResult,
    ResolutionStatus,
    SourceProvider,
)
from viesett.integrations.sources import PublicSources, attribution, flood_lookup


def preview_view(result: ResolutionResult) -> PropertyView:
    return PropertyView(
        status=result.status,
        address=result.address.canonical_address if result.address else None,
        address_id=result.address.official_id if result.address else None,
        unit_id=result.selected_building_unit.official_id
        if result.selected_building_unit
        else None,
        box=result.address.box_number if result.address else None,
        parcels=[p.capakey for p in result.parcels],
        last_refreshed=result.address.retrieved_at if result.address else None,
        flood=flood_lookup(result.parcels),
        sources=[attribution(SourceProvider.GRAR, utcnow())] if result.address else [],
    )


async def property_preview(
    request: ResolutionRequest, sources: PublicSources, settings: Settings
) -> PreviewResponse:
    # No session, account, workspace, cache or persistent preview history.
    if not sources.enabled:
        result = ResolutionResult(status=ResolutionStatus.UPSTREAM_UNAVAILABLE)
    else:
        try:
            async with asyncio.timeout(settings.source_operation_timeout):
                result = await sources.grar.resolve(request)
        except TimeoutError:
            result = ResolutionResult(status=ResolutionStatus.UPSTREAM_UNAVAILABLE)
    choices = [
        PreviewChoice(address_id=a.official_id, label=a.canonical_address)
        for a in result.address_candidates
    ]
    if result.address:
        choices.extend(
            PreviewChoice(
                address_id=result.address.official_id,
                unit_id=u.official_id,
                label=(
                    f"Unit {index + 1} at "
                    + result.address.canonical_address
                    + " — private unit (official register has no separate box label)"
                ),
            )
            for index, u in enumerate(result.building_unit_candidates)
        )
    status = (
        "RESOLVED"
        if result.status in {"RESOLVED", "PARTIALLY_RESOLVED"}
        else "NEEDS_SELECTION"
        if result.status == "NEEDS_SELECTION"
        else "NOT_FOUND"
        if result.status == "NOT_FOUND"
        else "UPSTREAM_UNAVAILABLE"
    )
    return PreviewResponse(
        status=status,
        property=preview_view(result),
        choices=choices,
        truncated=result.candidates_truncated,
        is_demo=settings.demo_mode,
    )
