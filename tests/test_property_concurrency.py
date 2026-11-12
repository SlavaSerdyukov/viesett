import asyncio
from uuid import UUID

import httpx
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import workspace
from tests.official_fixtures import HOST, OfficialFixtureService
from tests.test_property_resolution import resolve
from viesett.api.app import create_app
from viesett.core.config import Settings
from viesett.db.property_models import PropertyResolution, PublicEnrichmentRun
from viesett.domain.property import SourceProvider
from viesett.services.auth import provision_account


async def test_older_resolution_completion_cannot_replace_newer_selection(
    settings: Settings,
    db: AsyncSession,
) -> None:
    service = OfficialFixtureService()
    entered, release = asyncio.Event(), asyncio.Event()

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v2/adressen/zoeken":
            query = request.url.params["query"]
            if query == "first address query":
                entered.set()
                await release.wait()
            identifier = "1" if query == "first address query" else "2"
            return httpx.Response(
                200,
                json={
                    "resultaten": [
                        {
                            "id": f"https://data.vlaanderen.be/id/adres/{identifier}",
                            "objectId": identifier,
                            "detail": HOST + "/v2/adressen/" + identifier,
                        }
                    ]
                },
            )
        return service.handler(request)

    _, token = await provision_account(db)
    app = create_app(
        settings.model_copy(update={"source_min_interval": 0}),
        source_transport=httpx.MockTransport(handler),
    )
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"Authorization": "Bearer " + token},
    ) as client:
        wid = await workspace(client)
        path = f"/api/v1/workspaces/{wid}/property-resolution"
        first = asyncio.create_task(client.post(path, json={"query": "first address query"}))
        await asyncio.wait_for(entered.wait(), timeout=2)
        second = asyncio.create_task(client.post(path, json={"query": "second address query"}))
        try:
            for _ in range(100):
                generation = await db.scalar(
                    select(func.max(PropertyResolution.generation)).where(
                        PropertyResolution.workspace_id == UUID(wid),
                    )
                )
                if generation == 2:
                    break
                await asyncio.sleep(0.01)
            else:
                pytest.fail("Second request did not reserve its independent generation")
        finally:
            release.set()
        older, newer = await asyncio.wait_for(asyncio.gather(first, second), timeout=5)
        assert older.status_code == newer.status_code == 200
        assert not older.json()["applied_to_snapshot"] and newer.json()["applied_to_snapshot"]
        data = (await client.get(f"/api/v1/workspaces/{wid}/property-snapshot")).json()
        assert data["address"]["official_id"] == "2"
        assert data["selected_building_unit"]["official_id"] == "20"
    await app.state.runtime.sources.aclose()
    await app.state.engine.dispose()


async def test_enrichment_of_old_identity_is_discarded_after_property_change(
    settings: Settings,
    db: AsyncSession,
) -> None:
    service = OfficialFixtureService()
    entered, release = asyncio.Event(), asyncio.Event()

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "geo.onroerenderfgoed.be":
            entered.set()
            await release.wait()
        return service.handler(request)

    _, token = await provision_account(db)
    app = create_app(
        settings.model_copy(update={"source_min_interval": 0}),
        source_transport=httpx.MockTransport(handler),
    )
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"Authorization": "Bearer " + token},
    ) as client:
        wid = await workspace(client)
        await resolve(client, wid)
        pending = asyncio.create_task(
            client.post(f"/api/v1/workspaces/{wid}/public-enrichment/refresh")
        )
        await asyncio.wait_for(entered.wait(), timeout=2)
        service.search_ids = ["2"]
        assert (await resolve(client, wid)).json()["status"] == "RESOLVED"
        release.set()
        rejected = await asyncio.wait_for(pending, timeout=5)
        assert rejected.status_code == 409
        result = (await client.get(f"/api/v1/workspaces/{wid}/property-snapshot")).json()
        assert result["address"]["official_id"] == "2" and result["heritage"] == []
        run = await db.scalar(
            select(PublicEnrichmentRun).where(
                PublicEnrichmentRun.workspace_id == UUID(wid),
                PublicEnrichmentRun.provider == SourceProvider.HERITAGE,
            )
        )
        assert run and run.status == "NOT_APPLICABLE"
        assert run.error_code == "property_changed_during_enrichment"
    await app.state.runtime.sources.aclose()
    await app.state.engine.dispose()


async def test_operation_deadline_preserves_previous_identity_and_client_recovers(
    settings: Settings,
    db: AsyncSession,
) -> None:
    service = OfficialFixtureService()
    slow = False

    async def handler(request: httpx.Request) -> httpx.Response:
        if slow:
            await asyncio.sleep(0.1)
        return service.handler(request)

    _, token = await provision_account(db)
    config = settings.model_copy(update={"source_min_interval": 0, "source_operation_timeout": 1})
    app = create_app(config, source_transport=httpx.MockTransport(handler))
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"Authorization": "Bearer " + token},
    ) as client:
        wid = await workspace(client)
        assert (await resolve(client, wid)).json()["status"] == "RESOLVED"
        slow = True
        config.source_operation_timeout = 0.01
        unavailable = (await resolve(client, wid)).json()
        assert unavailable["status"] == "UPSTREAM_UNAVAILABLE"
        assert unavailable["error_code"] == "source_operation_timeout"
        data = (await client.get(f"/api/v1/workspaces/{wid}/property-snapshot")).json()
        assert data["address"]["official_id"] == "1" and data["stale"]
        slow = False
        config.source_operation_timeout = 1
        assert (await resolve(client, wid)).json()["status"] == "RESOLVED"
    await app.state.runtime.sources.aclose()
    await app.state.engine.dispose()
