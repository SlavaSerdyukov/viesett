import logging
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import PDF, attest, upload, workspace
from viesett.api.app import create_app
from viesett.core.config import Settings
from viesett.db.models import ObjectDeletionTask, PropertyDocument
from viesett.document_safety.pipeline import (
    ConservativeSensitiveGate,
    DevelopmentScanner,
    SafetyPipeline,
)
from viesett.storage.private import LocalPrivateStorage


async def test_filename_storage_and_authenticated_download(
    client: AsyncClient,
    db: AsyncSession,
    settings: Settings,
) -> None:
    await attest(client)
    wid = await workspace(client)
    response = await upload(client, wid, filename="../../../../secret.pdf")
    assert response.status_code == 201, response.text
    doc = response.json()
    assert doc["original_filename"] == "secret.pdf"
    assert doc["status"] == "READY"
    assert "storage_key" not in doc
    row = await db.get(PropertyDocument, UUID(doc["id"]))
    assert row is not None
    assert len(row.storage_key) == 64 and row.storage_key != doc["original_filename"]
    path = settings.storage_root / row.storage_key
    assert path.read_bytes() == PDF
    assert path.stat().st_mode & 0o777 == 0o600
    download = await client.get(f"/api/v1/workspaces/{wid}/documents/{doc['id']}/content")
    assert download.content == PDF
    assert download.headers["cache-control"] == "private, no-store"
    assert download.headers["content-disposition"].startswith("attachment;")


@pytest.mark.parametrize("method,suffix", [("GET", ""), ("GET", "/content"), ("DELETE", "")])
async def test_document_isolation_and_enumeration(
    client: AsyncClient,
    other_client: AsyncClient,
    method: str,
    suffix: str,
) -> None:
    await attest(other_client)
    foreign_wid = await workspace(other_client)
    doc = (await upload(other_client, foreign_wid)).json()
    own_wid = await workspace(client)
    foreign = await client.request(
        method, f"/api/v1/workspaces/{foreign_wid}/documents/{doc['id']}{suffix}"
    )
    absent = await client.request(
        method, f"/api/v1/workspaces/{uuid4()}/documents/{uuid4()}{suffix}"
    )
    wrong_workspace = await client.request(
        method, f"/api/v1/workspaces/{own_wid}/documents/{doc['id']}{suffix}"
    )
    assert foreign.status_code == absent.status_code == wrong_workspace.status_code == 404
    assert foreign.json() == absent.json() == wrong_workspace.json()


@pytest.mark.parametrize(
    "content,media_type",
    [
        (b"<script>bad()</script>", "application/pdf"),
        (PDF, "text/html"),
        (b"%PDF-1.7 not complete", "application/pdf"),
    ],
)
async def test_unsafe_media_rejected(
    client: AsyncClient,
    content: bytes,
    media_type: str,
    settings: Settings,
) -> None:
    await attest(client)
    wid = await workspace(client)
    response = await client.post(
        f"/api/v1/workspaces/{wid}/documents", content=content, headers={"Content-Type": media_type}
    )
    assert response.status_code == 415
    assert not list(settings.storage_root.iterdir())


@pytest.mark.parametrize("size", [0, 1100, 3000])
async def test_size_limits(client: AsyncClient, size: int) -> None:
    await attest(client)
    wid = await workspace(client)
    response = await upload(client, wid, b"x" * size)
    assert response.status_code == 413


async def test_dedup_is_scoped_to_workspace(
    client: AsyncClient,
    other_client: AsyncClient,
    settings: Settings,
) -> None:
    await attest(client)
    await attest(other_client)
    wid = await workspace(client)
    other = await workspace(other_client)
    first = await upload(client, wid)
    second = await upload(client, wid, filename="different.pdf")
    across = await upload(other_client, other)
    own_second = await upload(client, await workspace(client))
    assert first.status_code == across.status_code == own_second.status_code == 201
    assert second.status_code == 200 and second.json()["id"] == first.json()["id"]
    assert first.json()["id"] != across.json()["id"]
    assert len(list(settings.storage_root.iterdir())) == 3


async def test_sensitive_quarantine_and_malware_rejection(
    client: AsyncClient,
    settings: Settings,
) -> None:
    await attest(client)
    wid = await workspace(client)
    sensitive = await upload(client, wid, filename="passport.pdf")
    rejected = await upload(client, wid, b"%PDF-1.7\nEICAR\n%%EOF")
    assert sensitive.json()["status"] == "QUARANTINED"
    assert rejected.json()["status"] == "REJECTED"
    assert len(list(settings.storage_root.iterdir())) == 1
    for response in [sensitive, rejected]:
        download = await client.get(
            f"/api/v1/workspaces/{wid}/documents/{response.json()['id']}/content"
        )
        assert download.status_code == 409


class ExplodingScanner:
    production_ready = False

    async def clean(self, content: bytes) -> bool:
        raise RuntimeError(content.decode())


async def test_scan_failure_cannot_become_ready_and_logs_are_clean(
    client: AsyncClient,
    settings: Settings,
    caplog: pytest.LogCaptureFixture,
) -> None:
    await attest(client)
    wid = await workspace(client)
    app = create_app(
        settings, pipeline=SafetyPipeline(ExplodingScanner(), ConservativeSensitiveGate())
    )
    caplog.set_level(logging.INFO)
    secret = b"%PDF-1.7\nVERY_PRIVATE_DOCUMENT_TEXT_9375\n%%EOF"
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver", headers=client.headers
    ) as failing:
        response = await upload(failing, wid, secret)
    await app.state.engine.dispose()
    assert response.json()["status"] == "QUARANTINED"
    assert "VERY_PRIVATE_DOCUMENT_TEXT_9375" not in caplog.text
    assert "VERY_PRIVATE_DOCUMENT_TEXT_9375" not in response.text


async def test_default_scanner_fails_closed(settings: Settings) -> None:
    from viesett.document_safety.pipeline import UnavailableScanner

    pipeline = SafetyPipeline(UnavailableScanner(), ConservativeSensitiveGate())
    assert (await pipeline.inspect("epc.pdf", PDF)).status == "QUARANTINED"


def test_storage_rejects_paths_and_symlinks(tmp_path: Path) -> None:
    store = LocalPrivateStorage(tmp_path / "objects")
    for bad in ["../../secret", "/etc/passwd", "a" * 63, "G" * 64]:
        with pytest.raises(ValueError):
            store.read(bad)
    key = store.new_key()
    (store.root / key).symlink_to(tmp_path / "outside")
    with pytest.raises(OSError):
        store.put(key, b"x")
    with pytest.raises(OSError):
        store.read(key)
    store.delete(key)
    store.delete(key)
    root_link = tmp_path / "link"
    root_link.symlink_to(store.root)
    with pytest.raises(ValueError):
        LocalPrivateStorage(root_link)


async def test_upload_commit_failure_cleans_private_object(
    client: AsyncClient,
    db: AsyncSession,
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests.helpers import owner
    from viesett.domain.types import DocumentKind
    from viesett.services.documents import upload_document

    await attest(client)
    wid = UUID(await workspace(client))
    user = await owner(client)
    original = db.commit
    calls = 0

    async def fail_second_commit() -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("Database failed")
        await original()

    monkeypatch.setattr(db, "commit", fail_second_commit)
    with pytest.raises(RuntimeError, match="Database failed"):
        await upload_document(
            db,
            user,
            wid,
            PDF,
            "epc.pdf",
            "application/pdf",
            DocumentKind.EPC,
            1024,
            LocalPrivateStorage(settings.storage_root),
            SafetyPipeline(DevelopmentScanner(), ConservativeSensitiveGate()),
        )
    assert not list(settings.storage_root.iterdir())
    assert await db.scalar(select(func.count()).select_from(ObjectDeletionTask)) == 1
