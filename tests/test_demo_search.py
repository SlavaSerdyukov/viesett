import pytest
from httpx import ASGITransport, AsyncClient

from viesett.api.app import create_app
from viesett.core.config import Settings


@pytest.mark.parametrize(
    "query,status,address_id",
    [
        ("Teststraat 42, 9000 Gent", "RESOLVED", "1"),
        ("  TESTSTRAAT  42 Gent  ", "RESOLVED", "1"),
        ("Teststraat 42 bus 1, 9000 Gent", "RESOLVED", "2"),
        ("Unrelated fictional street 999", "NOT_FOUND", None),
        ("Teststraat", "NEEDS_SELECTION", None),
    ],
)
async def test_demo_search_matches_its_catalog_instead_of_returning_one_old_property(
    settings: Settings, query: str, status: str, address_id: str | None
) -> None:
    app = create_app(
        settings.model_copy(
            update={"demo_mode": True, "source_min_interval": 0, "source_retry_base": 0}
        )
    )
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            response = await client.post("/api/v1/property-preview", json={"query": query})
            assert response.status_code == 200, response.text
            result = response.json()
            assert result["is_demo"]
            assert result["status"] == status
            assert result["property"]["address_id"] == address_id
            if address_id == "2":
                assert "bus 1" in result["property"]["address"]
                assert result["property"]["unit_id"] == "20"
            if status == "NOT_FOUND":
                assert result["property"]["address"] is None and not result["choices"]
            if status == "NEEDS_SELECTION":
                assert {c["address_id"] for c in result["choices"]} == {"1", "2"}
    finally:
        await app.state.runtime.sources.aclose()
        await app.state.engine.dispose()
