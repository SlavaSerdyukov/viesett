from collections.abc import AsyncIterator
from datetime import date
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import attest
from viesett.api.app import create_app
from viesett.core.config import Settings
from viesett.db.coownership_models import CoOwnershipEvaluation
from viesett.db.intelligence_models import DueDiligenceEvaluation
from viesett.services import coownership, due_diligence
from viesett.services.auth import provision_account

SCENARIO_DATE = date(2026, 11, 12)


@pytest.fixture
async def demo_client(settings: Settings, db: AsyncSession) -> AsyncIterator[AsyncClient]:
    _, token = await provision_account(db)
    config = settings.model_copy(
        update={
            "demo_mode": True,
            "allow_development_safety": True,
            "max_upload_bytes": 128 * 1024,
            "max_request_bytes": 130 * 1024,
            "source_min_interval": 0,
        }
    )
    app = create_app(config)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
            headers={"Authorization": "Bearer " + token},
        ) as client:
            await attest(client)
            yield client
    finally:
        await app.state.runtime.sources.aclose()
        await app.state.engine.dispose()


@pytest.mark.parametrize(
    "wall_date",
    [SCENARIO_DATE, date(2026, 11, 13), date(2028, 2, 29), date(2036, 1, 13)],
)
async def test_demo_evaluations_stay_at_scenario_date_through_recomputation(
    demo_client: AsyncClient,
    db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    wall_date: date,
) -> None:
    monkeypatch.setattr(due_diligence, "current_evaluation_date", lambda: wall_date)
    monkeypatch.setattr(coownership, "current_evaluation_date", lambda: wall_date)
    created = await demo_client.post("/api/v1/development/demo-dossier")
    assert created.status_code == 201, created.text
    initial = created.json()
    wid = UUID(initial["workspace"]["id"])
    assert initial["completeness"]["applicable_count"] == 10
    assert initial["completeness"]["completed_count"] == 8
    assert initial["completeness"]["percentage"] == 80

    # Check evaluations made DURING seed/analysis, not only the final DTO read.
    async def evaluation_dates() -> None:
        for statement in [
            select(DueDiligenceEvaluation.evaluation_date).where(
                DueDiligenceEvaluation.workspace_id == wid
            ),
            select(CoOwnershipEvaluation.evaluation_date).where(
                CoOwnershipEvaluation.workspace_id == wid
            ),
        ]:
            dates = list(await db.scalars(statement))
            assert dates and set(dates) == {SCENARIO_DATE}

    await evaluation_dates()
    epc = next(d for d in initial["documents"] if d["kind"] == "EPC")
    # Cached analysis and manual reclassification both recompute downstream state.
    for payload in [{}, {"manual_kind": "EPC"}]:
        response = await demo_client.post(
            f"/api/v1/workspaces/{wid}/documents/{epc['id']}/analyze", json=payload
        )
        assert response.status_code == 200, response.text
    due = await demo_client.get(f"/api/v1/workspaces/{wid}/document-requirements")
    co = await demo_client.get(f"/api/v1/workspaces/{wid}/co-ownership")
    assert due.status_code == co.status_code == 200
    assert due.json()["evaluation_date"] == co.json()["evaluation_date"] == "2026-11-12"
    periods = {
        row["code"]: row
        for row in co.json()["article_3_94_completeness"]
        if row["code"] in {"AGM_MINUTES_3Y", "PERIODIC_CHARGES_2Y"}
    }
    assert len(periods) == 2
    assert all(
        row["status"] == "PRESENT" and not row["coverage"]["gaps"] for row in periods.values()
    )
    refreshed = await demo_client.post(f"/api/v1/workspaces/{wid}/refresh", json={})
    assert refreshed.status_code == 200, refreshed.text
    assert refreshed.json()["completeness"] == initial["completeness"]
    await evaluation_dates()

    # Source deletion has its own automatic co-ownership recomputation path.
    deleted = await demo_client.delete(f"/api/v1/workspaces/{wid}/documents/{epc['id']}")
    assert deleted.status_code == 204, deleted.text
    # Deletion erases affected evaluation snapshots for privacy and creates a
    # new co-ownership snapshot from remaining sources without a dossier read.
    dates = list(
        await db.scalars(
            select(CoOwnershipEvaluation.evaluation_date).where(
                CoOwnershipEvaluation.workspace_id == wid
            )
        )
    )
    assert dates and set(dates) == {SCENARIO_DATE}


async def test_normal_workspace_keeps_current_and_explicit_evaluation_dates(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    from viesett.db.models import PropertyWorkspace

    user, _ = await provision_account(db)
    workspace = PropertyWorkspace(owner_user_id=user.id)
    db.add(workspace)
    await db.commit()
    wall_date = date(2028, 2, 29)
    monkeypatch.setattr(due_diligence, "current_evaluation_date", lambda: wall_date)
    monkeypatch.setattr(coownership, "current_evaluation_date", lambda: wall_date)
    current_due = await due_diligence.refresh_due_diligence(db, user.id, workspace.id)
    current_co = await coownership.refresh_coownership(db, user.id, workspace.id)
    assert current_due.evaluation_date == current_co.evaluation_date == wall_date
    explicit_due = await due_diligence.refresh_due_diligence(
        db, user.id, workspace.id, SCENARIO_DATE
    )
    explicit_co = await coownership.refresh_coownership(db, user.id, workspace.id, SCENARIO_DATE)
    assert explicit_due.evaluation_date == explicit_co.evaluation_date == SCENARIO_DATE
