import hashlib
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Annotated, cast
from uuid import UUID

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from viesett.core.config import Settings
from viesett.core.security import RateLimiter
from viesett.document_safety.pipeline import SafetyPipeline
from viesett.integrations.sources import PublicSources
from viesett.services.auth import authenticate
from viesett.services.browser_sessions import current_session
from viesett.storage.private import PrivateObjectStorage


@dataclass
class Runtime:
    settings: Settings
    engine: AsyncEngine
    sessions: async_sessionmaker[AsyncSession]
    storage: PrivateObjectStorage
    pipeline: SafetyPipeline
    limiter: RateLimiter
    sources: PublicSources


def runtime(request: Request) -> Runtime:
    return cast(Runtime, request.app.state.runtime)


async def session(request: Request) -> AsyncIterator[AsyncSession]:
    async with runtime(request).sessions() as db:
        yield db


Db = Annotated[AsyncSession, Depends(session)]
bearer = HTTPBearer(auto_error=False)


async def require_user(
    request: Request,
    db: Db,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> UUID:
    token = credentials.credentials if credentials else None
    if (
        not token
        and request.headers.get("authorization") is None
        and runtime(request).settings.browser_sessions_enabled
    ):
        row = await current_session(db, request, runtime(request).settings)
        if not runtime(request).limiter.allow("browser:" + row.secret_hash):
            raise HTTPException(429, "Rate limit exceeded")
        return row.user_id
    if token:
        key = "credential:" + hashlib.sha256(token.encode()).hexdigest()
        if not runtime(request).limiter.allow(key):
            raise HTTPException(429, "Rate limit exceeded")
    return await authenticate(db, token)


UserId = Annotated[UUID, Depends(require_user)]
