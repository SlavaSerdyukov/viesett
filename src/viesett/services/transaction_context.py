"""One optional transaction need; property/document facts are never asked again."""

from datetime import date
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from viesett.db.models import EvidenceItem, utcnow
from viesett.domain.intelligence import EvaluationOut
from viesett.domain.product import ContextAnswerResponse, MissingContextQuestion
from viesett.domain.types import Authority, SourceType
from viesett.services.due_diligence import current_evaluation_date, refresh_due_diligence
from viesett.services.ownership import owned_workspace
from viesett.services.property_snapshot import snapshot

KEY = "transaction.authentic_deed_date"
METHOD = "user-transaction-context:1.0.0"


def missing_questions(due: EvaluationOut) -> list[MissingContextQuestion]:
    facts = due.inputs.get("facts", {})
    blocked = due.inputs.get("blocked_context_keys", [])
    if (
        not isinstance(facts, dict)
        or KEY in facts
        or (isinstance(blocked, list) and KEY in blocked)
    ):
        return []
    prerequisites = {
        "transaction.qualifying_transfer": True,
        "transaction.renovation_exemption": False,
        "transaction.existing_renovation_obligation": False,
    }
    for key, expected in prerequisites.items():
        fact = facts.get(key)
        if not isinstance(fact, dict) or fact.get("value") is not expected:
            return []
    docs = due.inputs.get("documents", [])
    if not isinstance(docs, list):
        return []
    if not any(r.kind == "EPC" and r.presence == "PRESENT" for r in due.requirements):
        return []
    all_labels: set[str] = set()
    all_residential: set[bool] = set()
    for doc in docs:
        if (
            not isinstance(doc, dict)
            or doc.get("kind") != "EPC"
            or doc.get("association") != "MATCHED"
            or doc.get("status") != "READY"
        ):
            continue
        fields = doc.get("fields", {})
        if not isinstance(fields, dict):
            continue
        labels, residential = fields.get("label", []), fields.get("residential", [])
        if isinstance(labels, list):
            all_labels.update(
                str(f["value"])
                for f in labels
                if isinstance(f, dict) and isinstance(f.get("value"), str)
            )
        if isinstance(residential, list):
            all_residential.update(
                bool(f["value"])
                for f in residential
                if isinstance(f, dict) and isinstance(f.get("value"), bool)
            )
    residential_fact = facts.get("property.residential")
    if isinstance(residential_fact, dict) and isinstance(residential_fact.get("value"), bool):
        all_residential = {bool(residential_fact["value"])}
    return (
        [MissingContextQuestion()]
        if all_labels in ({"E"}, {"F"}) and all_residential == {True}
        else []
    )


async def answers(
    db: AsyncSession, wid: UUID, identity_revision: str | None
) -> list[ContextAnswerResponse]:
    rows = (
        await db.scalars(
            select(EvidenceItem).where(
                EvidenceItem.workspace_id == wid,
                EvidenceItem.key == KEY,
                EvidenceItem.authority == Authority.UNVERIFIED,
                EvidenceItem.superseded_at.is_(None),
            )
        )
    ).all()
    return [
        ContextAnswerResponse(value=str(e.typed_value["value"]), evidence_id=e.id)
        for e in rows
        if e.source_locator.get("identity_revision") == identity_revision
    ]


async def record_answer(db: AsyncSession, user: UUID, wid: UUID, value: date) -> None:
    if not date(1900, 1, 1) <= value <= current_evaluation_date():
        raise HTTPException(422, "Enter a known past or current deed date")
    due = await refresh_due_diligence(db, user, wid)
    await owned_workspace(db, user, wid, lock=True)
    prop = await snapshot(db, wid, user)
    if (
        prop.stale
        or prop.identity_revision is None
        or prop.identity_revision != due.identity_revision
    ):
        raise HTTPException(409, "Confirm current property information first")
    current = await answers(db, wid, prop.identity_revision)
    if not missing_questions(due) and not current:
        raise HTTPException(409, "No buyer transaction answer is needed")
    facts = due.inputs.get("facts", {})
    existing = facts.get(KEY) if isinstance(facts, dict) else None
    if isinstance(existing, dict) and existing.get("authority") != "UNVERIFIED":
        raise HTTPException(409, "Use the available source information")
    rows = (
        await db.scalars(
            select(EvidenceItem).where(
                EvidenceItem.workspace_id == wid,
                EvidenceItem.key == KEY,
                EvidenceItem.authority == Authority.UNVERIFIED,
                EvidenceItem.superseded_at.is_(None),
            )
        )
    ).all()
    if (
        len(rows) == 1
        and rows[0].typed_value.get("value") == value.isoformat()
        and rows[0].source_locator.get("identity_revision") == prop.identity_revision
    ):
        await db.commit()
        return
    for row in rows:
        row.superseded_at = utcnow()
    db.add(
        EvidenceItem(
            workspace_id=wid,
            key=KEY,
            typed_value={"kind": "date", "value": value.isoformat()},
            source_type=SourceType.MANUAL,
            authority=Authority.UNVERIFIED,
            source_locator={
                "method": METHOD,
                "question_code": "KNOWN_DEED_DATE",
                "identity_revision": prop.identity_revision,
            },
            observed_at=utcnow(),
            supersedes_evidence_id=rows[0].id if rows else None,
        )
    )
    await db.commit()


async def clear_answer(db: AsyncSession, user: UUID, wid: UUID) -> None:
    await owned_workspace(db, user, wid, lock=True)
    rows = (
        await db.scalars(
            select(EvidenceItem).where(
                EvidenceItem.workspace_id == wid,
                EvidenceItem.key == KEY,
                EvidenceItem.authority == Authority.UNVERIFIED,
                EvidenceItem.superseded_at.is_(None),
            )
        )
    ).all()
    for row in rows:
        row.superseded_at = utcnow()
    await db.commit()
