"""Written first: privacy contracts exercised against a real PostgreSQL database."""

from uuid import uuid4

import pytest
from httpx import AsyncClient


@pytest.mark.parametrize("suffix", ["", "/documents", "/evidence", "/findings"])
async def test_other_workspace_is_indistinguishable_from_missing(
    client: AsyncClient, other_client: AsyncClient, suffix: str
) -> None:
    workspace = (await other_client.post("/api/v1/workspaces", json={})).json()
    foreign = await client.get(f"/api/v1/workspaces/{workspace['id']}{suffix}")
    absent = await client.get(f"/api/v1/workspaces/{uuid4()}{suffix}")
    assert foreign.status_code == absent.status_code == 404
    assert foreign.json() == absent.json() == {"detail": "Not found"}


async def test_no_unrelated_pii_needed(client: AsyncClient) -> None:
    response = await client.post("/api/v1/workspaces", json={})
    assert response.status_code == 201
    assert response.json()["region"] == "FLANDERS"
    assert response.json()["canonical_address"] is None


async def test_upload_requires_separate_versioned_attestation(client: AsyncClient) -> None:
    workspace = (await client.post("/api/v1/workspaces", json={})).json()["id"]
    response = await client.post(
        f"/api/v1/workspaces/{workspace}/documents",
        content=b"%PDF-1.7\nproperty file\n%%EOF",
        headers={"Content-Type": "application/pdf", "X-Filename": "epc.pdf"},
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "Current upload attestation required"


async def test_export_contains_only_caller_data(
    client: AsyncClient, other_client: AsyncClient
) -> None:
    own = (await client.post("/api/v1/workspaces", json={})).json()["id"]
    other = (await other_client.post("/api/v1/workspaces", json={})).json()["id"]
    response = await client.get("/api/v1/me/export")
    assert response.status_code == 200
    assert [row["id"] for row in response.json()["workspaces"]] == [own]
    assert other not in response.text
    assert "token_hash" not in response.text
    assert "storage_key" not in response.text


async def test_drafts_are_plain_text_only(client: AsyncClient) -> None:
    workspace = (await client.post("/api/v1/workspaces", json={})).json()["id"]
    response = await client.post(
        f"/api/v1/workspaces/{workspace}/document-request-draft",
        json={"requested_document_types": ["EPC", "SOIL_CERTIFICATE"], "language": "en"},
    )
    assert response.status_code == 201
    assert response.json()["generated_text"] == (
        "Could you please provide the EPC and soil certificate for this property?"
    )
    assert not {"recipient", "send_status", "delivery_status"} & response.json().keys()
    assert (await client.post(f"/api/v1/workspaces/{workspace}/send")).status_code == 404
