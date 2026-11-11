from datetime import timedelta
from uuid import UUID

import pytest
from fastapi import HTTPException
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import PDF, attest, owner, upload, workspace
from viesett.core.config import Settings
from viesett.db.models import PropertyWorkspace, utcnow
from viesett.document_safety.pipeline import (
    ConservativeSensitiveGate,
    DevelopmentScanner,
    SafetyPipeline,
)
from viesett.domain.types import DocumentKind
from viesett.services import deletion
from viesett.services.documents import upload_document
from viesett.services.ownership import owned_workspace
from viesett.storage.private import LocalPrivateStorage


async def test_archive_during_upload_reservation_prevents_storage(
    client: AsyncClient,
    db: AsyncSession,
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await attest(client)
    wid = UUID(await workspace(client))
    user = await owner(client)
    commit = db.commit

    async def commit_then_archive() -> None:
        await commit()
        response = await client.patch(f"/api/v1/workspaces/{wid}", json={"status": "ARCHIVED"})
        assert response.status_code == 200

    monkeypatch.setattr(db, "commit", commit_then_archive)
    with pytest.raises(HTTPException) as error:
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
    assert error.value.status_code == 409
    assert not list(settings.storage_root.iterdir())


async def test_reactivated_workspace_is_not_purged_from_stale_candidate_list(
    client: AsyncClient,
    db: AsyncSession,
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await attest(client)
    wid = UUID(await workspace(client))
    await upload(client, str(wid))
    await client.patch(f"/api/v1/workspaces/{wid}", json={"status": "ARCHIVED"})
    row = await db.get(PropertyWorkspace, wid)
    assert row is not None
    row.archived_at = utcnow() - timedelta(days=60)
    await db.commit()

    async def reactivate_before_lock(
        session: AsyncSession,
        user_id: UUID,
        workspace_id: UUID,
        *,
        lock: bool = False,
    ) -> PropertyWorkspace:
        response = await client.patch(
            f"/api/v1/workspaces/{workspace_id}", json={"status": "ACTIVE"}
        )
        assert response.status_code == 200
        return await owned_workspace(session, user_id, workspace_id, lock=lock)

    monkeypatch.setattr(deletion, "owned_workspace", reactivate_before_lock)
    assert await deletion.purge_archived(db, LocalPrivateStorage(settings.storage_root), 30) == 0
    assert (await client.get(f"/api/v1/workspaces/{wid}")).status_code == 200
    assert len(list(settings.storage_root.iterdir())) == 1
