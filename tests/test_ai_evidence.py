import logging
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from httpx import AsyncClient
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import attest, owner, upload, workspace
from viesett.ai.boundary import (
    InferredProposal,
    SelectedContent,
    interpret_selected,
    validate_processor,
    validate_production_processors,
)
from viesett.db.models import EvidenceItem, Processor
from viesett.domain.schemas import (
    EvidenceCreate,
    FindingCreate,
    FindingProvenance,
    SourceLocator,
    TypedValue,
)
from viesett.domain.types import Authority, Severity, SourceType
from viesett.services.evidence import record_evidence, record_finding


def reviewed_processor() -> Processor:
    return Processor(
        name="deterministic-test-only",
        purpose="selected content interpretation",
        data_categories=["selected property text"],
        region="EEA",
        enabled=True,
        training_use_allowed=False,
        dpa_reviewed=True,
    )


class FakeInterpreter:
    def __init__(self) -> None:
        self.calls = 0

    async def interpret(self, sections: tuple[SelectedContent, ...]) -> list[InferredProposal]:
        self.calls += 1
        return [
            InferredProposal(
                section_index=0,
                key="property.value",
                typed_value=TypedValue(kind="integer", value=200),
                confidence=0.7,
            )
        ]


@pytest.mark.parametrize("authority", [Authority.OFFICIAL, Authority.DOCUMENTED])
async def test_ai_is_append_only_and_cannot_overwrite_authoritative_evidence(
    client: AsyncClient,
    db: AsyncSession,
    authority: Authority,
) -> None:
    await attest(client)
    wid = UUID(await workspace(client))
    user = await owner(client)
    doc = (await upload(client, str(wid))).json()
    original = await record_evidence(
        db,
        user,
        wid,
        EvidenceCreate(
            document_id=UUID(doc["id"]),
            key="property.value",
            typed_value=TypedValue(kind="integer", value=100),
            source_type=SourceType.PUBLIC_REGISTRY
            if authority == Authority.OFFICIAL
            else SourceType.DOCUMENT,
            source_locator=SourceLocator(page=1, source_identifier="test-source"),
            authority=authority,
        ),
    )
    section = SelectedContent(UUID(doc["id"]), SourceLocator(page=1), "ONLY_RELEVANT_TEXT")
    items = await interpret_selected(
        db, user, wid, (section,), FakeInterpreter(), reviewed_processor()
    )
    await db.commit()
    assert original.typed_value["value"] == 100 and original.authority == authority
    assert items[0].authority == Authority.INFERRED and items[0].typed_value["value"] == 200
    assert len((await db.scalars(select(EvidenceItem))).all()) == 2
    assert "ONLY_RELEVANT_TEXT" not in repr(section)


@pytest.mark.parametrize(
    "filename,content",
    [
        ("passport.pdf", b"%PDF-1.7\nprivate\n%%EOF"),
        ("epc.pdf", b"%PDF-1.7\nEICAR\n%%EOF"),
    ],
)
async def test_unsafe_documents_cannot_reach_ai_or_evidence(
    client: AsyncClient,
    db: AsyncSession,
    filename: str,
    content: bytes,
) -> None:
    await attest(client)
    wid = UUID(await workspace(client))
    user = await owner(client)
    doc = (await upload(client, str(wid), content, filename)).json()
    interpreter = FakeInterpreter()
    with pytest.raises(HTTPException) as result:
        await interpret_selected(
            db,
            user,
            wid,
            (SelectedContent(UUID(doc["id"]), SourceLocator(page=1), "text"),),
            interpreter,
            reviewed_processor(),
        )
    assert result.value.status_code == 409
    assert interpreter.calls == 0
    with pytest.raises(HTTPException):
        await record_evidence(
            db,
            user,
            wid,
            EvidenceCreate(
                document_id=UUID(doc["id"]),
                key="property.value",
                typed_value=TypedValue(kind="text", value="x"),
                source_type=SourceType.DOCUMENT,
                source_locator=SourceLocator(page=1),
                authority=Authority.DOCUMENTED,
            ),
        )


async def test_ai_disabled_and_minimisation(client: AsyncClient, db: AsyncSession) -> None:
    wid = UUID(await workspace(client))
    user = await owner(client)
    with pytest.raises(HTTPException, match="disabled"):
        await interpret_selected(db, user, wid, ())
    for sections in [(), (SelectedContent(uuid4(), SourceLocator(page=1), "x" * 8001),)]:
        with pytest.raises(HTTPException) as error:
            await interpret_selected(
                db, user, wid, sections, FakeInterpreter(), reviewed_processor()
            )
        assert error.value.status_code == 422


async def test_processor_defaults_and_runtime_production_guard(db: AsyncSession) -> None:
    processor = Processor(
        name="unreviewed", purpose="AI", data_categories=["selected text"], region="EU"
    )
    db.add(processor)
    await db.commit()
    assert (
        not processor.enabled and not processor.training_use_allowed and not processor.dpa_reviewed
    )
    processor.enabled = True
    await db.commit()
    with pytest.raises(ValueError, match="review"):
        await validate_production_processors(db)
    processor.dpa_reviewed = True
    await db.commit()
    await validate_production_processors(db)
    processor.region = "US"
    with pytest.raises(ValueError):
        validate_processor(processor, production=True)
    processor.international_transfer_mechanism = "Review recorded for deterministic test only"
    validate_processor(processor, production=True)
    processor.training_use_allowed = True
    with pytest.raises(ValueError, match="training"):
        validate_processor(processor, production=False)
    processor.training_use_allowed = False
    processor.enabled = False
    with pytest.raises(ValueError, match="disabled"):
        validate_processor(processor, production=False)


@pytest.mark.parametrize("authority", [Authority.OFFICIAL, Authority.DOCUMENTED])
def test_ai_authority_is_rejected_by_schema(authority: Authority) -> None:
    with pytest.raises(ValidationError):
        EvidenceCreate(
            key="x",
            typed_value=TypedValue(kind="text", value="x"),
            source_type=SourceType.AI,
            source_locator=SourceLocator(page=1),
            authority=authority,
        )


async def test_cross_workspace_evidence_and_findings_are_rejected(
    client: AsyncClient,
    other_client: AsyncClient,
    db: AsyncSession,
) -> None:
    await attest(other_client)
    other_wid = await workspace(other_client)
    doc = (await upload(other_client, other_wid)).json()
    wid = UUID(await workspace(client))
    user = await owner(client)
    with pytest.raises(HTTPException):
        await record_evidence(
            db,
            user,
            wid,
            EvidenceCreate(
                document_id=UUID(doc["id"]),
                key="x",
                typed_value=TypedValue(kind="text", value="x"),
                source_type=SourceType.DOCUMENT,
                source_locator=SourceLocator(page=1),
                authority=Authority.DOCUMENTED,
            ),
        )
    with pytest.raises(HTTPException):
        await record_finding(
            db,
            user,
            wid,
            FindingCreate(
                code="GAP",
                severity=Severity.BLOCKING_DATA_GAP,
                summary="Insufficient evidence",
                evidence_ids=[uuid4()],
                provenance=FindingProvenance(method="deterministic", source="test", version="1"),
            ),
        )


class FailingInterpreter:
    async def interpret(self, sections: tuple[SelectedContent, ...]) -> list[InferredProposal]:
        raise RuntimeError(sections[0].text)


async def test_extracted_content_not_logged(
    client: AsyncClient,
    db: AsyncSession,
    caplog: pytest.LogCaptureFixture,
) -> None:
    await attest(client)
    wid = UUID(await workspace(client))
    user = await owner(client)
    doc = (await upload(client, str(wid))).json()
    caplog.set_level(logging.DEBUG)
    with pytest.raises(HTTPException) as error:
        await interpret_selected(
            db,
            user,
            wid,
            (SelectedContent(UUID(doc["id"]), SourceLocator(page=1), "EXTRACTED_SECRET_8321"),),
            FailingInterpreter(),
            reviewed_processor(),
        )
    assert "EXTRACTED_SECRET_8321" not in caplog.text
    assert "EXTRACTED_SECRET_8321" not in str(error.value)
