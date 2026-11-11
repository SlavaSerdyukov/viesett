from datetime import timedelta
from uuid import UUID

from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import attest, owner, upload, workspace
from viesett.api.app import create_app
from viesett.core.config import Settings
from viesett.db.models import (
    Account,
    ApiToken,
    DocumentRequestDraft,
    EvidenceItem,
    Finding,
    FindingEvidence,
    ObjectDeletionTask,
    PropertyDocument,
    PropertyWorkspace,
    UserPolicyAcknowledgement,
    utcnow,
)
from viesett.domain.schemas import (
    EvidenceCreate,
    FindingCreate,
    FindingProvenance,
    SourceLocator,
    TypedValue,
)
from viesett.domain.types import Authority, Severity, SourceType
from viesett.services.deletion import purge_archived, purge_objects
from viesett.services.evidence import record_evidence, record_finding
from viesett.storage.private import LocalPrivateStorage


async def test_document_deletion_removes_object_and_dependent_state(
    client: AsyncClient,
    db: AsyncSession,
    settings: Settings,
) -> None:
    await attest(client)
    wid = await workspace(client)
    user = await owner(client)
    doc = (await upload(client, wid)).json()
    evidence = await record_evidence(
        db,
        user,
        UUID(wid),
        EvidenceCreate(
            document_id=UUID(doc["id"]),
            key="property.example",
            typed_value=TypedValue(kind="text", value="x"),
            source_type=SourceType.DOCUMENT,
            source_locator=SourceLocator(page=1),
            authority=Authority.DOCUMENTED,
        ),
    )
    await record_finding(
        db,
        user,
        UUID(wid),
        FindingCreate(
            code="EXAMPLE",
            severity=Severity.REVIEW,
            summary="Review source",
            evidence_ids=[evidence.id],
            provenance=FindingProvenance(method="manual", source="test", version="1"),
        ),
    )
    await db.commit()
    await client.post(
        f"/api/v1/workspaces/{wid}/document-request-draft",
        json={"requested_document_types": ["EPC"]},
    )
    assert (await client.get(f"/api/v1/workspaces/{wid}/evidence")).json()
    assert (await client.get(f"/api/v1/workspaces/{wid}/findings")).json()[0]["evidence_ids"]
    response = await client.delete(f"/api/v1/workspaces/{wid}/documents/{doc['id']}")
    assert response.status_code == 204, response.text
    assert not list(settings.storage_root.iterdir())
    for suffix in ["", "/content"]:
        assert (
            await client.get(f"/api/v1/workspaces/{wid}/documents/{doc['id']}{suffix}")
        ).status_code == 404
    exported = (await client.get("/api/v1/me/export")).json()
    for key in ["documents", "evidence", "findings", "document_request_drafts"]:
        assert exported[key] == []


async def test_workspace_deletion_preserves_other_workspace(
    client: AsyncClient,
    db: AsyncSession,
    settings: Settings,
) -> None:
    await attest(client)
    wid, kept = await workspace(client), await workspace(client)
    await upload(client, wid)
    kept_doc = (await upload(client, kept)).json()
    response = await client.delete(f"/api/v1/workspaces/{wid}")
    assert response.status_code == 204, response.text
    assert (await client.get(f"/api/v1/workspaces/{wid}")).status_code == 404
    assert (
        await client.get(f"/api/v1/workspaces/{kept}/documents/{kept_doc['id']}/content")
    ).status_code == 200
    assert len(list(settings.storage_root.iterdir())) == 1
    assert await db.scalar(select(func.count()).select_from(PropertyWorkspace)) == 1


async def test_account_deletion_cascades_and_revokes_token(
    client: AsyncClient,
    other_client: AsyncClient,
    db: AsyncSession,
    settings: Settings,
) -> None:
    await attest(client)
    await upload(client, await workspace(client))
    other_id = await owner(other_client)
    response = await client.delete("/api/v1/me")
    assert response.status_code == 204, response.text
    assert (await client.get("/api/v1/me/export")).status_code == 401
    assert (await other_client.get("/api/v1/me/export")).json()["account"]["id"] == str(other_id)
    assert not list(settings.storage_root.iterdir())
    for model in [
        PropertyWorkspace,
        PropertyDocument,
        EvidenceItem,
        Finding,
        FindingEvidence,
        DocumentRequestDraft,
        UserPolicyAcknowledgement,
        ObjectDeletionTask,
    ]:
        assert await db.scalar(select(func.count()).select_from(model)) == 0
    assert await db.scalar(select(func.count()).select_from(Account)) == 1
    assert await db.scalar(select(func.count()).select_from(ApiToken)) == 1


class FailingDeleteStorage(LocalPrivateStorage):
    def delete(self, key: str) -> None:
        raise OSError("storage unavailable")


async def test_failed_physical_delete_is_inaccessible_and_retryable(
    client: AsyncClient,
    db: AsyncSession,
    settings: Settings,
) -> None:
    await attest(client)
    wid = await workspace(client)
    doc = (await upload(client, wid)).json()
    app = create_app(settings, storage=FailingDeleteStorage(settings.storage_root))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver", headers=client.headers
    ) as failing:
        response = await failing.delete(f"/api/v1/workspaces/{wid}/documents/{doc['id']}")
        assert response.status_code == 503
        assert (
            await failing.get(f"/api/v1/workspaces/{wid}/documents/{doc['id']}")
        ).status_code == 404
    await app.state.engine.dispose()
    assert await db.scalar(select(func.count()).select_from(ObjectDeletionTask)) == 1
    assert await purge_objects(db, LocalPrivateStorage(settings.storage_root)) == 1
    assert not list(settings.storage_root.iterdir())


async def test_archive_retention_is_opt_in(
    client: AsyncClient,
    db: AsyncSession,
    settings: Settings,
) -> None:
    await attest(client)
    wid = await workspace(client)
    await upload(client, wid)
    response = await client.patch(f"/api/v1/workspaces/{wid}", json={"status": "ARCHIVED"})
    assert response.json()["archived_at"]
    assert (await upload(client, wid)).status_code == 409
    row = await db.get(PropertyWorkspace, UUID(wid))
    assert row is not None
    row.archived_at = utcnow() - timedelta(days=60)
    await db.commit()
    storage = LocalPrivateStorage(settings.storage_root)
    assert await purge_archived(db, storage, None) == 0
    assert await purge_archived(db, storage, 30) == 1
    assert not list(settings.storage_root.iterdir())


async def test_unarchive(client: AsyncClient) -> None:
    wid = await workspace(client)
    await client.patch(f"/api/v1/workspaces/{wid}", json={"status": "ARCHIVED"})
    response = await client.patch(f"/api/v1/workspaces/{wid}", json={"status": "ACTIVE"})
    assert response.json()["archived_at"] is None
