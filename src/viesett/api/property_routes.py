from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request

from viesett.api.dependencies import Db, UserId, require_user, runtime
from viesett.domain.property import PropertySnapshot, ResolutionOut, ResolutionRequest
from viesett.services.ownership import owned_workspace
from viesett.services.property_resolution import resolve_property
from viesett.services.property_snapshot import latest_resolution, resolution_out, snapshot
from viesett.services.public_enrichment import refresh_enrichment

router = APIRouter(prefix="/api/v1", dependencies=[Depends(require_user)])


@router.post("/workspaces/{workspace_id}/property-resolution", response_model=ResolutionOut)
async def resolve(
    workspace_id: UUID,
    data: ResolutionRequest,
    request: Request,
    db: Db,
    user: UserId,
) -> ResolutionOut:
    context = runtime(request)
    return await resolve_property(db, user, workspace_id, data, context.sources, context.settings)


@router.get("/workspaces/{workspace_id}/property-resolution", response_model=ResolutionOut)
async def get_resolution(workspace_id: UUID, db: Db, user: UserId) -> ResolutionOut:
    await owned_workspace(db, user, workspace_id)
    result = await latest_resolution(db, workspace_id)
    if result is None:
        raise HTTPException(404, "Not found")
    return resolution_out(result)


@router.post(
    "/workspaces/{workspace_id}/public-enrichment/refresh", response_model=PropertySnapshot
)
async def refresh(workspace_id: UUID, request: Request, db: Db, user: UserId) -> PropertySnapshot:
    context = runtime(request)
    return await refresh_enrichment(db, user, workspace_id, context.sources, context.settings)


@router.get("/workspaces/{workspace_id}/property-snapshot", response_model=PropertySnapshot)
async def get_snapshot(workspace_id: UUID, db: Db, user: UserId) -> PropertySnapshot:
    await owned_workspace(db, user, workspace_id)
    return await snapshot(db, workspace_id, user)
