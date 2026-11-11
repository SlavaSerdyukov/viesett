import hashlib
import secrets
from datetime import timedelta
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from viesett.db.models import Account, ApiToken, utcnow


async def provision_account(db: AsyncSession, lifetime_hours: int = 24) -> tuple[Account, str]:
    account = Account()
    db.add(account)
    await db.flush()
    token = secrets.token_urlsafe(48)
    db.add(
        ApiToken(
            user_id=account.id,
            token_hash=hashlib.sha256(token.encode()).hexdigest(),
            expires_at=utcnow() + timedelta(hours=lifetime_hours),
        )
    )
    await db.commit()
    return account, token


async def authenticate(db: AsyncSession, token: str | None) -> UUID:
    if token is None or not 40 <= len(token) <= 128:
        raise HTTPException(401, "Authentication required", headers={"WWW-Authenticate": "Bearer"})
    user = await db.scalar(
        select(ApiToken.user_id)
        .join(Account)
        .where(
            ApiToken.token_hash == hashlib.sha256(token.encode()).hexdigest(),
            ApiToken.expires_at > utcnow(),
        )
    )
    if user is None:
        raise HTTPException(401, "Authentication required", headers={"WWW-Authenticate": "Bearer"})
    return user
