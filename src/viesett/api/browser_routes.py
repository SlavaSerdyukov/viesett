import hashlib
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.security import HTTPAuthorizationCredentials

from viesett.api.dependencies import Db, bearer, runtime
from viesett.db.models import utcnow
from viesett.domain.base import Schema
from viesett.services.browser_sessions import (
    clear_cookie,
    current_session,
    exchange,
    require_origin,
)

router = APIRouter(prefix="/api/v1/browser-session")


class BrowserSessionResponse(Schema):
    authenticated: bool = True
    csrf_token: str
    expires_at: datetime


def enabled(request: Request) -> None:
    if not runtime(request).settings.browser_sessions_enabled:
        raise HTTPException(404, "Not found")


@router.post("/exchange", response_model=BrowserSessionResponse)
async def create_browser_session(
    request: Request,
    response: Response,
    db: Db,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> BrowserSessionResponse:
    enabled(request)
    config = runtime(request).settings
    require_origin(request, config)
    peer = request.client.host if request.client else "unknown"
    if not request.app.state.browser_limiter.allow(hashlib.sha256(peer.encode()).hexdigest()):
        raise HTTPException(429, "Session limit reached")
    row = await exchange(db, credentials.credentials if credentials else None, response, config)
    return BrowserSessionResponse(csrf_token=row.csrf_token, expires_at=row.expires_at)


@router.get("", response_model=BrowserSessionResponse)
async def restore(request: Request, db: Db) -> BrowserSessionResponse:
    enabled(request)
    row = await current_session(db, request, runtime(request).settings)
    return BrowserSessionResponse(csrf_token=row.csrf_token, expires_at=row.expires_at)


@router.post("/logout", status_code=204)
async def logout(request: Request, response: Response, db: Db) -> None:
    enabled(request)
    row = await current_session(db, request, runtime(request).settings)
    row.revoked_at = utcnow()
    await db.commit()
    clear_cookie(response, runtime(request).settings)
