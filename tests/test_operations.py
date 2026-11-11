import asyncio
import json
from datetime import timedelta
from pathlib import Path
from uuid import UUID

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import PDF, attest, owner, upload, workspace
from tests.test_ai_evidence import reviewed_processor
from viesett.ai.boundary import InferredProposal, SelectedContent, interpret_selected
from viesett.api.app import create_app
from viesett.cli import main, run
from viesett.core.config import Settings
from viesett.db.models import ObjectDeletionTask, PropertyDocument, utcnow
from viesett.domain.schemas import SourceLocator, TypedValue
from viesett.services.deletion import purge_objects
from viesett.storage.private import LocalPrivateStorage


async def test_concurrent_duplicate_uploads_create_one_object(
    client: AsyncClient,
    settings: Settings,
) -> None:
    await attest(client)
    wid = await workspace(client)
    responses = await asyncio.gather(upload(client, wid), upload(client, wid))
    assert sorted(r.status_code for r in responses) == [200, 201]
    assert responses[0].json()["id"] == responses[1].json()["id"]
    assert len(list(settings.storage_root.iterdir())) == 1


async def test_expired_upload_reservation_is_purged(
    db: AsyncSession,
    settings: Settings,
) -> None:
    storage = LocalPrivateStorage(settings.storage_root)
    old, live = storage.new_key(), storage.new_key()
    storage.put(old, PDF)
    storage.put(live, PDF)
    db.add_all(
        [
            ObjectDeletionTask(storage_key=old, not_before=utcnow() - timedelta(minutes=1)),
            ObjectDeletionTask(storage_key=live, not_before=utcnow() + timedelta(minutes=10)),
        ]
    )
    await db.commit()
    assert await purge_objects(db, storage) == 1
    assert storage.read(live) == PDF
    assert not (settings.storage_root / old).exists()
    assert await db.scalar(select(func.count()).select_from(ObjectDeletionTask)) == 1


async def test_missing_ready_object_is_safe_503(
    client: AsyncClient,
    db: AsyncSession,
    settings: Settings,
) -> None:
    await attest(client)
    wid = await workspace(client)
    doc = (await upload(client, wid)).json()
    row = await db.get(PropertyDocument, UUID(doc["id"]))
    assert row is not None
    LocalPrivateStorage(settings.storage_root).delete(row.storage_key)
    response = await client.get(f"/api/v1/workspaces/{wid}/documents/{doc['id']}/content")
    assert response.status_code == 503 and row.storage_key not in response.text


async def test_readiness_failure_does_not_expose_exception(
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_app(settings)

    def fail() -> None:
        raise RuntimeError("private-db-connection-details")

    monkeypatch.setattr(app.state.runtime, "sessions", fail)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as plain:
        response = await plain.get("/health/ready")
        assert response.status_code == 503
        assert response.json() == {"status": "unavailable"}
    await app.state.engine.dispose()


async def test_training_permission_is_forbidden_in_database(db: AsyncSession) -> None:
    processor = reviewed_processor()
    processor.training_use_allowed = True
    db.add(processor)
    with pytest.raises(IntegrityError):
        await db.flush()
    await db.rollback()


async def test_cli_provision_and_purge(
    settings: Settings,
    db: AsyncSession,
    capsys: pytest.CaptureFixture[str],
) -> None:
    await run("create-account", settings)
    issued = json.loads(capsys.readouterr().out)
    assert UUID(issued["account_id"]) and len(issued["token"]) == 64
    await run("purge", settings)
    assert json.loads(capsys.readouterr().out)["objects_purged"] == 0
    config = settings.model_copy(update={"environment": "production"})
    with pytest.raises(RuntimeError, match="disabled"):
        await run("create-account", config)


def test_cli_entrypoint(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str] = []

    async def fake_run(command: str, settings: Settings) -> None:
        seen.append(command)

    monkeypatch.setattr("sys.argv", ["viesett", "purge"])
    monkeypatch.setattr("viesett.cli.run", fake_run)
    main()
    assert seen == ["purge"]


class BadReferenceInterpreter:
    async def interpret(self, sections: tuple[SelectedContent, ...]) -> list[InferredProposal]:
        return [
            InferredProposal(
                section_index=10, key="x", typed_value=TypedValue(kind="text", value="x")
            )
        ]


async def test_ai_provider_cannot_fabricate_source_reference(
    client: AsyncClient,
    db: AsyncSession,
) -> None:
    await attest(client)
    wid = UUID(await workspace(client))
    doc = (await upload(client, str(wid))).json()
    with pytest.raises(HTTPException) as error:
        await interpret_selected(
            db,
            await owner(client),
            wid,
            (SelectedContent(UUID(doc["id"]), SourceLocator(page=1), "selected"),),
            BadReferenceInterpreter(),
            reviewed_processor(),
        )
    assert error.value.status_code == 422


async def test_request_drafts_normalize_duplicates_and_support_dutch(client: AsyncClient) -> None:
    wid = await workspace(client)
    response = await client.post(
        f"/api/v1/workspaces/{wid}/document-request-draft",
        json={
            "requested_document_types": ["SOIL_CERTIFICATE", "EPC", "EPC"],
            "language": "nl",
        },
    )
    assert response.status_code == 201
    assert response.json()["requested_document_types"] == ["EPC", "SOIL_CERTIFICATE"]
    assert response.json()["generated_text"] == (
        "Kunt u het volgende bezorgen voor dit pand: EPC en bodemattest?"
    )
    rejected = await client.post(
        f"/api/v1/workspaces/{wid}/document-request-draft",
        json={
            "requested_document_types": ["EPC"],
            "recipient": "not-stored@example.invalid",
        },
    )
    assert rejected.status_code == 422


def test_storage_failed_write_removes_partial_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage = LocalPrivateStorage(tmp_path)

    def fail_sync(descriptor: int) -> None:
        raise OSError("disk failure")

    monkeypatch.setattr("viesett.storage.private.os.fsync", fail_sync)
    with pytest.raises(OSError):
        storage.put(storage.new_key(), PDF)
    assert not list(tmp_path.iterdir())
