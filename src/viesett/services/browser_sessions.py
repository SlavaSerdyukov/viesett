"""Opaque server sessions backed by the existing expiring API-token authority."""

import hashlib
import secrets
from datetime import timedelta

from fastapi import HTTPException, Request, Response
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from viesett.core.config import Settings
from viesett.db.beta_models import BrowserSession
from viesett.db.models import Account, ApiToken, utcnow


def cookie_name(settings: Settings) -> str:
    return "__Host-viesett-session" if settings.browser_cookie_secure else "viesett-session"


def require_origin(request: Request, settings: Settings) -> None:
    if request.headers.get("origin") not in settings.web_origins:
        raise HTTPException(403, "Browser origin not permitted")
    if request.headers.get("sec-fetch-site") == "cross-site":
        raise HTTPException(403, "Browser origin not permitted")


async def current_session(db: AsyncSession, request: Request, settings: Settings) -> BrowserSession:
    secret = request.cookies.get(cookie_name(settings))
    if not settings.browser_sessions_enabled or secret is None or not 40 <= len(secret) <= 128:
        raise HTTPException(401, "Authentication required")
    row = await db.scalar(
        select(BrowserSession)
        .join(
            ApiToken,
            (ApiToken.id == BrowserSession.api_token_id)
            & (ApiToken.user_id == BrowserSession.user_id),
        )
        .join(Account, Account.id == BrowserSession.user_id)
        .where(
            BrowserSession.secret_hash == hashlib.sha256(secret.encode()).hexdigest(),
            BrowserSession.expires_at > utcnow(),
            BrowserSession.revoked_at.is_(None),
            ApiToken.expires_at > utcnow(),
        )
    )
    if row is None:
        raise HTTPException(401, "Authentication required")
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        require_origin(request, settings)
        supplied = request.headers.get("x-csrf-token", "")
        if (
            not 40 <= len(supplied) <= 64
            or not supplied.isascii()
            or not secrets.compare_digest(supplied, row.csrf_token)
        ):
            raise HTTPException(403, "Browser request could not be verified")
    elif request.headers.get("origin") is not None:
        require_origin(request, settings)
    elif request.headers.get("sec-fetch-site") == "cross-site":
        raise HTTPException(403, "Browser origin not permitted")
    return row


async def exchange(
    db: AsyncSession, token: str | None, response: Response, settings: Settings
) -> BrowserSession:
    if token is None or not 40 <= len(token) <= 128:
        raise HTTPException(401, "Authentication required")
    authority = await db.scalar(
        select(ApiToken)
        .where(
            ApiToken.token_hash == hashlib.sha256(token.encode()).hexdigest(),
            ApiToken.expires_at > utcnow(),
        )
        .with_for_update()
    )
    if authority is None:
        raise HTTPException(401, "Authentication required")
    # Exchange rotates the browser credential. Existing API bearer access is
    # unchanged; parent revocation/expiry also invalidates every child session.
    await db.execute(
        update(BrowserSession)
        .where(BrowserSession.api_token_id == authority.id, BrowserSession.revoked_at.is_(None))
        .values(revoked_at=utcnow())
    )
    secret = secrets.token_urlsafe(48)
    expires = min(authority.expires_at, utcnow() + timedelta(hours=settings.browser_session_hours))
    row = BrowserSession(
        user_id=authority.user_id,
        api_token_id=authority.id,
        secret_hash=hashlib.sha256(secret.encode()).hexdigest(),
        csrf_token=secrets.token_urlsafe(32),
        expires_at=expires,
    )
    db.add(row)
    await db.commit()
    response.set_cookie(
        cookie_name(settings),
        secret,
        max_age=max(0, int((expires - utcnow()).total_seconds())),
        expires=expires,
        path="/",
        secure=settings.browser_cookie_secure,
        httponly=True,
        samesite="strict",
    )
    return row


def clear_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        cookie_name(settings),
        path="/",
        secure=settings.browser_cookie_secure,
        httponly=True,
        samesite="strict",
    )
