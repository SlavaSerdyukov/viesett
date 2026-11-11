import os
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from viesett.api.app import create_app
from viesett.core.config import Settings
from viesett.db.session import create_engine, session_factory
from viesett.services.auth import provision_account


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    database = os.environ.get("VIESETT_TEST_DATABASE_URL")
    if not database:
        pytest.fail(
            "Set VIESETT_TEST_DATABASE_URL to a migrated, dedicated PostgreSQL test database"
        )
    return Settings(
        environment="test",
        database_url=SecretStr(database),
        storage_root=tmp_path,
        allow_development_safety=True,
        max_upload_bytes=1024,
        max_request_bytes=2048,
    )


@pytest.fixture
async def db(settings: Settings) -> AsyncIterator[AsyncSession]:
    engine = create_engine(settings)
    async with engine.begin() as connection:
        await connection.execute(
            text("TRUNCATE accounts, object_deletion_tasks, processors CASCADE")
        )
        await connection.execute(text("DELETE FROM policy_versions WHERE version != '2026-11-11'"))
        await connection.execute(text("UPDATE policy_versions SET current = true"))
    async with session_factory(engine)() as session:
        yield session
    await engine.dispose()


@pytest.fixture
async def client(settings: Settings, db: AsyncSession) -> AsyncIterator[AsyncClient]:
    _, token = await provision_account(db)
    app = create_app(settings)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"Authorization": f"Bearer {token}"},
    ) as result:
        yield result
    await app.state.engine.dispose()


@pytest.fixture
async def other_client(settings: Settings, db: AsyncSession) -> AsyncIterator[AsyncClient]:
    _, token = await provision_account(db)
    app = create_app(settings)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"Authorization": f"Bearer {token}"},
    ) as result:
        yield result
    await app.state.engine.dispose()
