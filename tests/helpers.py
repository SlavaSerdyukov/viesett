from uuid import UUID

from httpx import AsyncClient, Response

PDF = b"%PDF-1.7\nViesett property document\n%%EOF"


async def attest(client: AsyncClient) -> None:
    policies = (await client.get("/api/v1/policies")).json()
    policy = next(p for p in policies if p["policy_type"] == "UPLOAD_ATTESTATION")
    response = await client.post(
        "/api/v1/me/policy-acknowledgements", json={"policy_version_id": policy["id"]}
    )
    assert response.status_code == 204


async def workspace(client: AsyncClient) -> str:
    response = await client.post("/api/v1/workspaces", json={})
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


async def upload(
    client: AsyncClient,
    workspace_id: str,
    content: bytes = PDF,
    filename: str = "epc.pdf",
) -> Response:
    return await client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        content=content,
        headers={"Content-Type": "application/pdf", "X-Filename": filename},
    )


async def owner(client: AsyncClient) -> UUID:
    return UUID((await client.get("/api/v1/me/export")).json()["account"]["id"])
