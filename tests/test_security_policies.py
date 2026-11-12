import logging
from collections.abc import AsyncIterator
from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import attest, upload, workspace
from viesett.api.app import create_app
from viesett.core.config import Settings
from viesett.core.security import MemoryRateLimiter
from viesett.db.models import ApiToken, Base, PolicyVersion, PropertyDocument, utcnow
from viesett.document_safety.pipeline import (
    ConservativeSensitiveGate,
    DevelopmentScanner,
    SafetyPipeline,
    sanitize_filename,
)
from viesett.domain.schemas import EvidenceCreate, SourceLocator, TypedValue
from viesett.domain.types import Authority, DocumentStatus, PolicyType, SourceType
from viesett.services.documents import transition


async def test_versioned_acknowledgements_are_not_consent(
    client: AsyncClient,
    db: AsyncSession,
) -> None:
    policies = (await client.get("/api/v1/policies")).json()
    for policy in policies:
        response = await client.post(
            "/api/v1/me/policy-acknowledgements", json={"policy_version_id": policy["id"]}
        )
        assert response.status_code == 204
    await attest(client)  # Repeat acknowledgement is idempotent.
    rows = (await client.get("/api/v1/me/policy-acknowledgements")).json()
    assert len(rows) == 3
    current_versions = {policy["policy_type"]: policy["version"] for policy in policies}
    assert all(
        row["policy_version"] == current_versions[row["policy_type"]] and row["acknowledged_at"]
        for row in rows
    )
    assert not {"gdpr_consent", "marketing_consent"} & rows[0].keys()
    old = await db.scalar(
        select(PolicyVersion).where(PolicyVersion.policy_type == PolicyType.UPLOAD_ATTESTATION)
    )
    assert old is not None
    old.current = False
    await db.flush()
    revised = PolicyVersion(
        policy_type=PolicyType.UPLOAD_ATTESTATION,
        version="test-next",
        text="Updated representation",
    )
    db.add(revised)
    await db.commit()
    wid = await workspace(client)
    assert (await upload(client, wid)).status_code == 409
    assert (
        await client.post(
            "/api/v1/me/policy-acknowledgements", json={"policy_version_id": str(old.id)}
        )
    ).status_code == 409
    await attest(client)
    assert (await upload(client, wid)).status_code == 201


async def test_unknown_policy_and_unexpected_consent_fields_rejected(client: AsyncClient) -> None:
    assert (
        await client.post(
            "/api/v1/me/policy-acknowledgements", json={"policy_version_id": str(uuid4())}
        )
    ).status_code == 409
    response = await client.post("/api/v1/workspaces", json={"gdpr_consent": True})
    assert response.status_code == 422
    assert response.json() == {"detail": "Invalid request"}
    guidance = (await client.get("/api/v1/upload-guidance")).json()
    assert "not used to train" in guidance["training"]


async def test_private_routes_require_auth(client: AsyncClient) -> None:
    for token in [None, "short", "x" * 64]:
        client.headers.pop("Authorization", None)
        if token:
            client.headers["Authorization"] = f"Bearer {token}"
        for path in ["/api/v1/workspaces", "/api/v1/me/export", "/api/v1/policies"]:
            response = await client.get(path)
            assert response.status_code == 401
            assert response.headers["www-authenticate"] == "Bearer"
            assert response.headers["cache-control"] == "private, no-store"


async def test_expired_token(client: AsyncClient, db: AsyncSession) -> None:
    token = await db.scalar(select(ApiToken))
    assert token is not None
    token.expires_at = utcnow() - timedelta(seconds=1)
    await db.commit()
    assert (await client.get("/api/v1/workspaces")).status_code == 401


async def test_health_trusted_hosts_and_safe_errors(
    client: AsyncClient,
    settings: Settings,
    caplog: pytest.LogCaptureFixture,
) -> None:
    assert (await client.get("/health/live")).status_code == 200
    assert (await client.get("/health/ready")).status_code == 200
    blocked = await client.get("/health/live", headers={"Host": "attacker.example"})
    assert blocked.status_code == 400
    assert blocked.headers["cache-control"] == "private, no-store"
    app = create_app(settings)

    @app.get("/crash-test")
    async def crash() -> None:
        raise RuntimeError("RAW_UPLOADED_OR_EXTRACTED_SECRET_99234")

    caplog.set_level(logging.INFO, logger="viesett.http")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as plain:
        response = await plain.get("/crash-test", headers={"X-Correlation-ID": "untrusted-marker"})
        assert response.status_code == 500
        assert response.json() == {"detail": "Internal error"}
        assert UUID(response.headers["x-correlation-id"])
        assert "RAW_UPLOADED_OR_EXTRACTED_SECRET_99234" not in caplog.text + response.text
        assert "untrusted-marker" not in caplog.text + response.headers["x-correlation-id"]
    await app.state.engine.dispose()


async def test_actual_chunked_request_limit(client: AsyncClient) -> None:
    async def chunks() -> AsyncIterator[bytes]:
        yield b"x" * 1200
        yield b"x" * 1200

    response = await client.post("/api/v1/workspaces", content=chunks())
    assert response.status_code == 413


@pytest.mark.parametrize(
    "headers",
    [
        {"Content-Length": "invalid"},
        {"Content-Length": "-1"},
        {"Content-Encoding": "gzip"},
    ],
)
async def test_invalid_request_framing(client: AsyncClient, headers: dict[str, str]) -> None:
    assert (
        await client.post("/api/v1/workspaces", content=b"{}", headers=headers)
    ).status_code == 400


async def test_network_rate_limit(settings: Settings) -> None:
    app = create_app(settings, limiter=MemoryRateLimiter(1))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as plain:
        assert (await plain.get("/health/live")).status_code == 200
        assert (await plain.get("/health/live")).status_code == 429
    await app.state.engine.dispose()


def test_rate_limiter_bounds_keys_and_expires_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    now = 100.0
    monkeypatch.setattr("viesett.core.security.time.monotonic", lambda: now)
    limiter = MemoryRateLimiter(1, max_keys=1)
    assert limiter.allow("a")
    assert not limiter.allow("a") and not limiter.allow("b")
    now += 61
    assert limiter.allow("b")


def test_no_mailbox_or_sending_state() -> None:
    forbidden = (
        "mail",
        "smtp",
        "oauth",
        "recipient",
        "delivery",
        "send_status",
        "thread_id",
        "message_id",
    )
    for table in Base.metadata.tables.values():
        assert not any(term in table.name.lower() for term in forbidden)
        for column in table.columns:
            assert not any(term in column.name.lower() for term in forbidden)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"database_url": SecretStr("sqlite+aiosqlite:///test.db")},
        {"max_upload_bytes": 2048, "max_request_bytes": 1024},
        {"environment": "production", "allow_development_safety": True},
        {"environment": "production", "allowed_hosts": ["*"]},
        {
            "environment": "production",
            "database_url": SecretStr(
                "postgresql+asyncpg://viesett:development-only@localhost:5432/viesett"
            ),
        },
    ],
)
def test_unsafe_configuration_fails(kwargs: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        Settings.model_validate(kwargs)


def test_configuration_errors_do_not_echo_secrets() -> None:
    with pytest.raises(ValidationError) as error:
        Settings.model_validate(
            {
                "environment": "production",
                "allow_development_safety": True,
                "database_url": "postgresql+asyncpg://user:private-config-value@localhost/database",
            }
        )
    assert "private-config-value" not in str(error.value)


async def test_production_blocks_development_adapters(settings: Settings) -> None:
    config = Settings(
        environment="production",
        database_url=settings.database_url,
        storage_root=settings.storage_root,
        allowed_hosts=["testserver"],
    )
    app = create_app(config)
    assert app.docs_url is None and app.openapi_url is None
    with pytest.raises(RuntimeError, match="production document safety"):
        async with app.router.lifespan_context(app):
            pass


class ReviewedTestScanner(DevelopmentScanner):
    production_ready = True


class ReviewedTestGate(ConservativeSensitiveGate):
    production_ready = True


async def test_production_lifespan_with_reviewed_test_adapters(
    settings: Settings,
    db: AsyncSession,
) -> None:
    config = Settings(
        environment="production",
        database_url=settings.database_url,
        storage_root=settings.storage_root,
        allowed_hosts=["testserver"],
    )
    app = create_app(config, pipeline=SafetyPipeline(ReviewedTestScanner(), ReviewedTestGate()))
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as plain:
            assert (await plain.get("/health/ready")).status_code == 200


@pytest.mark.parametrize(
    "kind,value", [("integer", True), ("boolean", 1), ("date", "invalid"), ("text", "x" * 2001)]
)
def test_invalid_typed_evidence_rejected(kind: str, value: object) -> None:
    with pytest.raises(ValidationError):
        TypedValue.model_validate({"kind": kind, "value": value})


def test_provenance_must_be_explicit() -> None:
    with pytest.raises(ValidationError):
        SourceLocator()
    for source, authority in [
        (SourceType.DOCUMENT, Authority.DOCUMENTED),
        (SourceType.MANUAL, Authority.OFFICIAL),
        (SourceType.MANUAL, Authority.DOCUMENTED),
    ]:
        with pytest.raises(ValidationError):
            EvidenceCreate(
                key="x",
                typed_value=TypedValue(kind="text", value="x"),
                source_type=source,
                source_locator=SourceLocator(page=1),
                authority=authority,
            )
    assert TypedValue(kind="date", value="2026-11-11").value == "2026-11-11"


def test_quarantine_cannot_silently_transition_to_ready() -> None:
    document = PropertyDocument(status=DocumentStatus.QUARANTINED)
    with pytest.raises(ValueError):
        transition(document, DocumentStatus.READY)
    assert sanitize_filename("../../\\\x00.pdf") == "_.pdf"
    assert sanitize_filename("../...") == "document.pdf"
