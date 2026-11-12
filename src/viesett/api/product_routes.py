import hashlib
from typing import Annotated
from urllib.parse import unquote
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel

from viesett.api.dependencies import Db, UserId, runtime
from viesett.domain.product import (
    DossierSnapshotResponse,
    PreviewResponse,
    SessionResponse,
    WebConfigResponse,
)
from viesett.domain.property import ResolutionRequest
from viesett.services.auth import provision_account
from viesett.services.dossier import dossier
from viesett.services.ownership import owned_workspace
from viesett.services.product_actions import create_dossier, intake, seed_demo
from viesett.services.product_preview import property_preview
from viesett.services.public_enrichment import refresh_enrichment

router = APIRouter(prefix="/api/v1")


@router.get("/web-config", response_model=WebConfigResponse)
async def config(request: Request) -> WebConfigResponse:
    settings = runtime(request).settings
    return WebConfigResponse(
        development_session=settings.allow_development_web_sessions,
        demo=settings.demo_mode,
        max_upload_bytes=settings.max_upload_bytes,
    )


@router.post("/property-preview", response_model=PreviewResponse)
async def preview(data: ResolutionRequest, request: Request) -> PreviewResponse:
    limiter = request.app.state.preview_limiter
    client = request.client.host if request.client else "unknown"
    if not limiter.allow(hashlib.sha256(client.encode()).hexdigest()):
        raise HTTPException(429, "Preview limit reached; try again shortly")
    context = runtime(request)
    return await property_preview(data, context.sources, context.settings)


def local_session_allowed(request: Request) -> None:
    settings = runtime(request).settings
    if (
        not settings.allow_development_web_sessions
        or settings.environment == "production"
        or not request.client
        or request.client.host not in {"127.0.0.1", "::1"}
    ):
        raise HTTPException(404, "Not found")
    if request.headers.get("origin") not in settings.web_origins:
        raise HTTPException(403, "Web origin not permitted")
    if not request.app.state.session_limiter.allow("session-bootstrap"):
        raise HTTPException(429, "Session limit reached")


@router.post("/development/session", response_model=SessionResponse)
async def local_session(request: Request, db: Db) -> SessionResponse:
    local_session_allowed(request)
    _, token = await provision_account(db, 1)
    return SessionResponse(token=token, expires_in_seconds=3600)


@router.post("/dossiers", response_model=DossierSnapshotResponse, status_code=201)
async def create(
    data: ResolutionRequest, request: Request, db: Db, user: UserId
) -> DossierSnapshotResponse:
    wid = await create_dossier(db, user, data, runtime(request))
    return await dossier(db, user, wid)


@router.get("/workspaces/{workspace_id}/dossier", response_model=DossierSnapshotResponse)
async def get_dossier(workspace_id: UUID, db: Db, user: UserId) -> DossierSnapshotResponse:
    return await dossier(db, user, workspace_id)


class RefreshRequest(BaseModel):
    public_sources: bool = False


@router.post("/workspaces/{workspace_id}/refresh", response_model=DossierSnapshotResponse)
async def refresh(
    workspace_id: UUID, data: RefreshRequest, request: Request, db: Db, user: UserId
) -> DossierSnapshotResponse:
    await owned_workspace(db, user, workspace_id)
    if data.public_sources:
        await refresh_enrichment(
            db, user, workspace_id, runtime(request).sources, runtime(request).settings
        )
    return await dossier(db, user, workspace_id)


@router.post("/workspaces/{workspace_id}/document-intake", response_model=DossierSnapshotResponse)
async def upload(
    workspace_id: UUID,
    request: Request,
    db: Db,
    user: UserId,
    filename: Annotated[str, Header(alias="X-Filename", max_length=2160)] = "document.pdf",
) -> DossierSnapshotResponse:
    await intake(
        db,
        user,
        workspace_id,
        await request.body(),
        unquote(filename),
        request.headers.get("content-type", ""),
        runtime(request),
    )
    return await dossier(db, user, workspace_id)


@router.post("/development/demo-dossier", response_model=DossierSnapshotResponse, status_code=201)
async def demo(request: Request, db: Db, user: UserId) -> DossierSnapshotResponse:
    if not runtime(request).settings.demo_mode:
        raise HTTPException(404, "Not found")
    wid = await seed_demo(db, user, runtime(request))
    return await dossier(db, user, wid)
