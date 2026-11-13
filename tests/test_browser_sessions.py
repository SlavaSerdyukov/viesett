import hashlib
from collections.abc import AsyncIterator
from datetime import timedelta

import httpx
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.official_fixtures import OfficialFixtureService
from tests.test_security_policies import ReviewedTestGate, ReviewedTestScanner
from viesett.api.app import create_app
from viesett.core.config import Settings
from viesett.db.beta_models import BrowserSession
from viesett.db.models import ApiToken, PropertyWorkspace, utcnow
from viesett.db.product_models import DemoWorkspace
from viesett.document_safety.pipeline import SafetyPipeline
from viesett.services.auth import provision_account

ORIGIN = "http://testserver"


@pytest.fixture
async def browser_client(
    settings: Settings, db: AsyncSession
) -> AsyncIterator[tuple[AsyncClient, FastAPI]]:
    config = settings.model_copy(
        update={
            "browser_sessions_enabled": True,
            "browser_cookie_secure": False,
            "web_origins": [ORIGIN],
            "source_min_interval": 0,
        }
    )
    app = create_app(config, source_transport=httpx.MockTransport(OfficialFixtureService().handler))
    async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN) as client:
        yield client, app
    await app.state.runtime.sources.aclose()
    await app.state.engine.dispose()


async def login(client: AsyncClient, db: AsyncSession, token: str | None = None) -> tuple[str, str]:
    if token is None:
        _, token = await provision_account(db)
    response = await client.post(
        "/api/v1/browser-session/exchange",
        headers={"Origin": ORIGIN, "Authorization": "Bearer " + token},
    )
    assert response.status_code == 200
    return token, response.json()["csrf_token"]


async def test_exchange_restoration_cookie_and_token_authority(
    browser_client: tuple[AsyncClient, FastAPI], db: AsyncSession
) -> None:
    c, _ = browser_client
    account, token = await provision_account(db, 1)
    response = await c.post(
        "/api/v1/browser-session/exchange",
        headers={"Origin": ORIGIN, "Authorization": "Bearer " + token},
    )
    assert response.status_code == 200
    assert set(response.json()) == {"authenticated", "csrf_token", "expires_at"}
    assert token not in response.text
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie and "SameSite=strict" in cookie and "Path=/" in cookie
    assert "Domain=" not in cookie
    row = await db.scalar(select(BrowserSession))
    assert row and row.user_id == account.id
    assert row.secret_hash == hashlib.sha256(c.cookies["viesett-session"].encode()).hexdigest()
    assert 0 < (row.expires_at - utcnow()).total_seconds() <= 3600
    # New client = page reload, with only the HttpOnly browser cookie retained.
    async with AsyncClient(transport=c._transport, base_url=ORIGIN, cookies=c.cookies) as reloaded:
        restored = await reloaded.get("/api/v1/browser-session")
        assert restored.json()["csrf_token"] == response.json()["csrf_token"]
        assert (await reloaded.get("/api/v1/workspaces")).status_code == 200
    assert (
        await c.get("/api/v1/workspaces", headers={"Authorization": "Bearer " + token})
    ).status_code == 200


@pytest.mark.parametrize("origin", [None, "https://foreign.example", "null"])
async def test_sensitive_exchange_rejects_origin(
    origin: str | None, browser_client: tuple[AsyncClient, FastAPI], db: AsyncSession
) -> None:
    c, _ = browser_client
    _, token = await provision_account(db)
    headers = {"Authorization": "Bearer " + token}
    if origin is not None:
        headers["Origin"] = origin
    assert (await c.post("/api/v1/browser-session/exchange", headers=headers)).status_code == 403
    assert await db.scalar(select(func.count()).select_from(BrowserSession)) == 0


async def test_invalid_bearer_cannot_create_or_fall_back_to_cookie(
    browser_client: tuple[AsyncClient, FastAPI], db: AsyncSession
) -> None:
    c, _ = browser_client
    await login(c, db)
    r = await c.post(
        "/api/v1/browser-session/exchange",
        headers={"Origin": ORIGIN, "Authorization": "Bearer " + "invalid" * 8},
    )
    assert r.status_code == 401 and "set-cookie" not in r.headers
    assert (
        await c.get("/api/v1/workspaces", headers={"Authorization": "Bearer " + "invalid" * 8})
    ).status_code == 401


@pytest.mark.parametrize(
    "origin,csrf",
    [(None, "correct"), (ORIGIN, None), (ORIGIN, "wrong"), ("https://foreign.example", "correct")],
)
async def test_cookie_mutations_need_both_origin_and_synchronizer(
    origin: str | None,
    csrf: str | None,
    browser_client: tuple[AsyncClient, FastAPI],
    db: AsyncSession,
) -> None:
    c, _ = browser_client
    _, secret = await login(c, db)
    headers = {}
    if origin:
        headers["Origin"] = origin
    if csrf:
        headers["X-CSRF-Token"] = secret if csrf == "correct" else csrf
    assert (await c.post("/api/v1/workspaces", json={}, headers=headers)).status_code == 403
    assert (await c.post("/api/v1/browser-session/logout", headers=headers)).status_code == 403


async def test_logout_revokes_server_session_and_clears_cookie(
    browser_client: tuple[AsyncClient, FastAPI], db: AsyncSession
) -> None:
    c, _ = browser_client
    _, csrf = await login(c, db)
    old_cookie = c.cookies["viesett-session"]
    headers = {"Origin": ORIGIN, "X-CSRF-Token": csrf}
    assert (await c.post("/api/v1/workspaces", json={}, headers=headers)).status_code == 201
    response = await c.post("/api/v1/browser-session/logout", headers=headers)
    assert response.status_code == 204 and "Max-Age=0" in response.headers["set-cookie"]
    c.cookies.set("viesett-session", old_cookie)
    assert (await c.get("/api/v1/workspaces")).status_code == 401
    row = await db.scalar(select(BrowserSession))
    assert row is not None and row.revoked_at is not None


@pytest.mark.parametrize("parent", [False, True])
async def test_session_or_parent_expiry_rejects_cookie(
    parent: bool, browser_client: tuple[AsyncClient, FastAPI], db: AsyncSession
) -> None:
    c, _ = browser_client
    await login(c, db)
    row = await db.scalar(select(ApiToken)) if parent else await db.scalar(select(BrowserSession))
    assert row
    row.expires_at = utcnow() - timedelta(seconds=1)
    await db.commit()
    assert (await c.get("/api/v1/browser-session")).status_code == 401
    assert (await c.get("/api/v1/workspaces")).status_code == 401


async def test_rotation_revokes_old_cookie_but_preserves_api_token(
    browser_client: tuple[AsyncClient, FastAPI], db: AsyncSession
) -> None:
    c, _ = browser_client
    token, _ = await login(c, db)
    old = c.cookies["viesett-session"]
    await login(c, db, token)
    assert c.cookies["viesett-session"] != old
    current = c.cookies["viesett-session"]
    c.cookies.clear()
    c.cookies.set("viesett-session", old)
    assert (await c.get("/api/v1/browser-session")).status_code == 401
    c.cookies.set("viesett-session", current)
    assert (await c.get("/api/v1/browser-session")).status_code == 200


async def test_cookie_workspace_isolation_export_and_account_cascade(
    browser_client: tuple[AsyncClient, FastAPI], db: AsyncSession
) -> None:
    c, app = browser_client
    _, csrf = await login(c, db)
    headers = {"Origin": ORIGIN, "X-CSRF-Token": csrf}
    wid = (await c.post("/api/v1/workspaces", json={}, headers=headers)).json()["id"]
    exported = (await c.get("/api/v1/me/export")).text
    assert "csrf_token" not in exported and "secret_hash" not in exported
    async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN) as other:
        await login(other, db)
        assert (await other.get(f"/api/v1/workspaces/{wid}/dossier")).status_code == 404
        assert (
            await other.get(
                f"/api/v1/workspaces/{wid}/documents/00000000-0000-0000-0000-000000000001/content"
            )
        ).status_code == 404
    assert (await c.delete("/api/v1/me", headers=headers)).status_code == 204
    assert (await c.get("/api/v1/workspaces")).status_code == 401


@pytest.mark.parametrize(
    "overrides",
    [
        {"browser_cookie_secure": False},
        {"web_origins": ["http://beta.example.test"]},
        {"web_origins": []},
        {"web_origins": ["https://beta.example.test/path"]},
        {"private_beta": True, "demo_mode": True},
        {"private_beta": True, "application_workers": 2},
        {"private_beta": True, "allow_development_web_sessions": True},
        {"private_beta": True, "official_sources_reviewed": False},
    ],
)
def test_production_browser_configuration_fails_closed(
    settings: Settings, overrides: dict[str, object]
) -> None:
    values = settings.model_dump()
    values.update(
        environment="production",
        allow_development_safety=False,
        browser_sessions_enabled=True,
        browser_cookie_secure=True,
        web_origins=["https://beta.example.test"],
        allowed_hosts=["beta.example.test"],
        official_sources_reviewed=True,
    )
    values.update(overrides)
    with pytest.raises(ValidationError):
        Settings.model_validate(values)


async def test_production_cookie_has_host_prefix_and_secure_flags(
    settings: Settings, db: AsyncSession
) -> None:
    config = settings.model_copy(
        update={
            "environment": "production",
            "browser_sessions_enabled": True,
            "browser_cookie_secure": True,
            "web_origins": ["https://testserver"],
            "allow_development_safety": False,
        }
    )
    app = create_app(config)
    _, token = await provision_account(db)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="https://testserver") as c:
        r = await c.post(
            "/api/v1/browser-session/exchange",
            headers={"Origin": "https://testserver", "Authorization": "Bearer " + token},
        )
        assert r.status_code == 200
        value = r.headers["set-cookie"]
        assert (
            value.startswith("__Host-viesett-session=")
            and "Secure" in value
            and "HttpOnly" in value
            and "SameSite=strict" in value
        )
    await app.state.runtime.sources.aclose()
    await app.state.engine.dispose()


def beta_settings(settings: Settings) -> Settings:
    return Settings(
        environment="production",
        database_url=settings.database_url,
        storage_root=settings.storage_root,
        private_beta=True,
        browser_sessions_enabled=True,
        browser_cookie_secure=True,
        web_origins=["https://beta.example.test"],
        allowed_hosts=["beta.example.test"],
        official_sources_reviewed=True,
    )


async def test_private_beta_rejects_demo_database(settings: Settings, db: AsyncSession) -> None:
    account, _ = await provision_account(db)
    workspace = PropertyWorkspace(owner_user_id=account.id)
    db.add(workspace)
    await db.flush()
    db.add(DemoWorkspace(workspace_id=workspace.id))
    await db.commit()
    app = create_app(
        beta_settings(settings), pipeline=SafetyPipeline(ReviewedTestScanner(), ReviewedTestGate())
    )
    with pytest.raises(RuntimeError, match="separate database"):
        async with app.router.lifespan_context(app):
            pass


async def test_private_beta_enforces_one_worker_with_database_lock(
    settings: Settings, db: AsyncSession
) -> None:
    config = beta_settings(settings)
    first = create_app(config, pipeline=SafetyPipeline(ReviewedTestScanner(), ReviewedTestGate()))
    second = create_app(config, pipeline=SafetyPipeline(ReviewedTestScanner(), ReviewedTestGate()))
    async with first.router.lifespan_context(first):
        with pytest.raises(RuntimeError, match="one application worker"):
            async with second.router.lifespan_context(second):
                pass
    # Closing the owning lifespan releases its lock; a new worker can start.
    replacement = create_app(
        config, pipeline=SafetyPipeline(ReviewedTestScanner(), ReviewedTestGate())
    )
    async with replacement.router.lifespan_context(replacement):
        pass


@pytest.mark.parametrize("csrf", [b"\xff", b"x" * 10000])
async def test_malformed_csrf_is_a_safe_denial(
    csrf: bytes, browser_client: tuple[AsyncClient, FastAPI], db: AsyncSession
) -> None:
    client, _ = browser_client
    await login(client, db)
    response = await client.post(
        "/api/v1/workspaces",
        json={},
        headers=[(b"Origin", ORIGIN.encode()), (b"X-CSRF-Token", csrf)],
    )
    assert response.status_code == 403 and response.json() == {
        "detail": "Browser request could not be verified"
    }
