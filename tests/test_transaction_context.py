from collections.abc import AsyncIterator
from datetime import date
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from viesett.api.app import create_app
from viesett.core.config import Settings
from viesett.db.models import EvidenceItem, PropertyDocument, utcnow
from viesett.domain.intelligence import EvaluationOut, Presence, Requirement
from viesett.domain.types import Authority, SourceType
from viesett.rules.catalog import CATALOG
from viesett.services.auth import provision_account
from viesett.services.transaction_context import KEY, missing_questions


@pytest.fixture
async def context_client(settings: Settings, db: AsyncSession) -> AsyncIterator[AsyncClient]:
    _, token = await provision_account(db)
    config = settings.model_copy(
        update={
            "demo_mode": True,
            "max_upload_bytes": 128 * 1024,
            "max_request_bytes": 130 * 1024,
            "source_min_interval": 0,
        }
    )
    app = create_app(config)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"Authorization": "Bearer " + token},
    ) as c:
        for policy in (await c.get("/api/v1/policies")).json():
            if policy["policy_type"] in {"UPLOAD_ATTESTATION", "PRIVACY_NOTICE"}:
                await c.post(
                    "/api/v1/me/policy-acknowledgements", json={"policy_version_id": policy["id"]}
                )
        yield c
    await app.state.runtime.sources.aclose()
    await app.state.engine.dispose()


async def test_minimal_question_answer_recomputes_only_affected_conclusion(
    context_client: AsyncClient, db: AsyncSession
) -> None:
    c = context_client
    original = (await c.post("/api/v1/development/demo-dossier")).json()
    assert len(original["context_questions"]) == 1
    question = original["context_questions"][0]
    assert question["code"] == "KNOWN_DEED_DATE" and question["affected_rule_codes"] == [
        "FL_EPC_RENOVATION"
    ]
    wid = original["workspace"]["id"]
    response = await c.post(
        f"/api/v1/workspaces/{wid}/context/KNOWN_DEED_DATE", json={"value": "2026-02-28"}
    )
    assert response.status_code == 200
    updated = response.json()
    assert (
        updated["context_questions"] == []
        and updated["context_answers"][0]["authority"] == "UNVERIFIED"
    )
    finding = next(f for f in updated["findings"] if f["code"] == "FL_EPC_RENOVATION")
    assert (
        "2032-02-28" in finding["explanation"]
        and "unverified buyer-provided" in finding["explanation"]
    )
    assert any("Buyer-provided" in s["label"] for s in finding["sources"])
    before = {
        f["code"]: (f["title"], f["explanation"], f["severity"], f["sources"])
        for f in original["findings"]
        if f["code"] != "FL_EPC_RENOVATION"
    }
    after = {
        f["code"]: (f["title"], f["explanation"], f["severity"], f["sources"])
        for f in updated["findings"]
        if f["code"] != "FL_EPC_RENOVATION"
    }
    assert before == after and original["requirements"] == updated["requirements"]
    evidence = await db.scalar(
        select(EvidenceItem).where(EvidenceItem.workspace_id == UUID(wid), EvidenceItem.key == KEY)
    )
    assert (
        evidence
        and evidence.authority == Authority.UNVERIFIED
        and evidence.source_type == SourceType.MANUAL
        and evidence.document_id is None
    )
    repeated = await c.post(
        f"/api/v1/workspaces/{wid}/context/KNOWN_DEED_DATE", json={"value": "2026-02-28"}
    )
    assert repeated.json()["context_answers"] == updated["context_answers"]
    cleared = await c.delete(f"/api/v1/workspaces/{wid}/context/KNOWN_DEED_DATE")
    assert cleared.json()["context_answers"] == [] and cleared.json()["context_questions"]


async def test_trusted_documented_date_suppresses_question_and_overrides_user_answer(
    context_client: AsyncClient, db: AsyncSession
) -> None:
    c = context_client
    data = (await c.post("/api/v1/development/demo-dossier")).json()
    wid = data["workspace"]["id"]
    await c.post(f"/api/v1/workspaces/{wid}/context/KNOWN_DEED_DATE", json={"value": "2026-02-28"})
    doc = await db.scalar(
        select(PropertyDocument).where(
            PropertyDocument.workspace_id == UUID(wid),
            PropertyDocument.original_filename == "EPC demo.pdf",
        )
    )
    assert doc
    db.add(
        EvidenceItem(
            workspace_id=UUID(wid),
            document_id=doc.id,
            key=KEY,
            typed_value={"kind": "date", "value": "2026-03-01"},
            source_type=SourceType.DOCUMENT,
            authority=Authority.DOCUMENTED,
            source_locator={"page": 1, "section": "Synthetic trusted transaction date fixture"},
        )
    )
    await db.commit()
    updated = (await c.get(f"/api/v1/workspaces/{wid}/dossier")).json()
    assert not updated["context_questions"]
    explanation = next(
        f["explanation"] for f in updated["findings"] if f["code"] == "FL_EPC_RENOVATION"
    )
    assert "2032-03-01" in explanation and "unverified buyer-provided" not in explanation
    assert (
        await c.post(
            f"/api/v1/workspaces/{wid}/context/KNOWN_DEED_DATE", json={"value": "2026-01-01"}
        )
    ).status_code == 409


async def test_question_not_asked_without_trusted_prerequisites(
    context_client: AsyncClient, db: AsyncSession
) -> None:
    c = context_client
    data = (await c.post("/api/v1/development/demo-dossier")).json()
    wid = data["workspace"]["id"]
    row = await db.scalar(
        select(EvidenceItem).where(
            EvidenceItem.workspace_id == UUID(wid),
            EvidenceItem.key == "transaction.renovation_exemption",
        )
    )
    assert row
    await db.delete(row)
    await db.commit()
    updated = (await c.get(f"/api/v1/workspaces/{wid}/dossier")).json()
    assert not updated["context_questions"]
    assert (
        await c.post(
            f"/api/v1/workspaces/{wid}/context/KNOWN_DEED_DATE", json={"value": "2026-01-01"}
        )
    ).status_code == 409


@pytest.mark.parametrize(
    "body,status",
    [
        ({"value": "2099-01-01"}, 422),
        ({"value": "unknown"}, 422),
        ({"value": "2026-01-01", "authority": "OFFICIAL"}, 422),
    ],
)
async def test_context_is_bounded_and_cannot_promote_authority(
    context_client: AsyncClient, body: dict[str, str], status: int
) -> None:
    data = (await context_client.post("/api/v1/development/demo-dossier")).json()
    wid = data["workspace"]["id"]
    assert (
        await context_client.post(f"/api/v1/workspaces/{wid}/context/KNOWN_DEED_DATE", json=body)
    ).status_code == status


async def test_context_owner_isolation_and_no_general_questionnaire(
    context_client: AsyncClient, other_client: AsyncClient
) -> None:
    data = (await context_client.post("/api/v1/development/demo-dossier")).json()
    wid = data["workspace"]["id"]
    assert (
        await other_client.post(
            f"/api/v1/workspaces/{wid}/context/KNOWN_DEED_DATE", json={"value": "2026-01-01"}
        )
    ).status_code == 404

    assert (
        await context_client.post(
            f"/api/v1/workspaces/{wid}/context/PROPERTY_ADDRESS", json={"value": "private"}
        )
    ).status_code == 404


@pytest.mark.parametrize("case", ["conflicting_epc", "expired_epc", "conflicting_dates"])
def test_unresolved_source_problems_do_not_trigger_a_buyer_date_question(case: str) -> None:
    requirement = Requirement(
        kind="EPC",
        rule=CATALOG["FL_EPC_REQUIRED"],
        applicability="REQUIRED",
        presence="PRESENT",
        reason="Synthetic current EPC",
        evaluation_date=date(2026, 11, 13),
    )
    due = EvaluationOut(
        id=uuid4(),
        workspace_id=uuid4(),
        evaluation_date=date(2026, 11, 13),
        input_hash="f" * 64,
        identity_revision="synthetic",
        requirements=[requirement],
        finding_ids=[],
        rules=[],
        created_at=utcnow(),
        inputs={
            "facts": {
                "transaction.qualifying_transfer": {"value": True},
                "transaction.renovation_exemption": {"value": False},
                "transaction.existing_renovation_obligation": {"value": False},
            },
            "documents": [
                {
                    "kind": "EPC",
                    "status": "READY",
                    "association": "MATCHED",
                    "fields": {"label": [{"value": "E"}], "residential": [{"value": True}]},
                }
            ],
        },
    )
    assert len(missing_questions(due)) == 1
    if case == "expired_epc":
        due.requirements[0].presence = Presence.EXPIRED
    elif case == "conflicting_dates":
        due.inputs["blocked_context_keys"] = [KEY]
    else:
        due.inputs["documents"] = [
            {
                "kind": "EPC",
                "status": "READY",
                "association": "MATCHED",
                "fields": {
                    "label": [{"value": "E"}, {"value": "D"}],
                    "residential": [{"value": True}],
                },
            }
        ]
    assert missing_questions(due) == []
