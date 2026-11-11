from dataclasses import dataclass, field
from typing import Protocol
from uuid import UUID

from fastapi import HTTPException
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from viesett.db.models import EvidenceItem, Processor, PropertyDocument
from viesett.domain.schemas import EvidenceCreate, Schema, SourceLocator, TypedValue
from viesett.domain.types import Authority, DocumentStatus, SourceType
from viesett.services.evidence import record_evidence
from viesett.services.ownership import owned_workspace


@dataclass(frozen=True)
class SelectedContent:
    document_id: UUID
    source_locator: SourceLocator
    text: str = field(repr=False)


class InferredProposal(Schema):
    section_index: int = Field(ge=0)
    key: str = Field(min_length=1, max_length=120, pattern=r"^[a-z][a-z0-9_.]*$")
    typed_value: TypedValue
    confidence: float | None = Field(default=None, ge=0, le=1)


class InterpretationProvider(Protocol):
    async def interpret(self, sections: tuple[SelectedContent, ...]) -> list[InferredProposal]: ...


class DocumentParser(Protocol):
    async def extract(self, content: bytes) -> tuple[SelectedContent, ...]: ...


def validate_processor(processor: Processor, *, production: bool) -> None:
    if processor.training_use_allowed:
        raise ValueError("Customer-content training is forbidden")
    if not processor.enabled:
        raise ValueError("Processor is disabled")
    if production and (
        not processor.dpa_reviewed
        or not processor.region
        or (
            processor.region not in {"EU", "EEA"} and not processor.international_transfer_mechanism
        )
    ):
        raise ValueError("Production processor requires DPA, location and transfer review")


async def validate_production_processors(db: AsyncSession) -> None:
    for processor in (await db.scalars(select(Processor).where(Processor.enabled.is_(True)))).all():
        validate_processor(processor, production=True)


async def interpret_selected(
    db: AsyncSession,
    user_id: UUID,
    workspace_id: UUID,
    sections: tuple[SelectedContent, ...],
    provider: InterpretationProvider | None = None,
    processor: Processor | None = None,
    *,
    production: bool = False,
) -> list[EvidenceItem]:
    await owned_workspace(db, user_id, workspace_id, lock=True)
    if provider is None or processor is None:
        raise HTTPException(503, "AI interpretation is disabled")
    validate_processor(processor, production=production)
    if not sections or len(sections) > 3 or sum(len(s.text) for s in sections) > 8000:
        raise HTTPException(422, "Select at most three relevant sections totalling 8000 characters")
    for section in sections:
        document = await db.scalar(
            select(PropertyDocument.id).where(
                PropertyDocument.id == section.document_id,
                PropertyDocument.workspace_id == workspace_id,
                PropertyDocument.status == DocumentStatus.READY,
            )
        )
        if document is None:
            raise HTTPException(409, "AI requires ready documents from this workspace")
    try:
        proposals = await provider.interpret(sections)
    except Exception:
        raise HTTPException(503, "AI interpretation unavailable") from None
    if len(proposals) > 50 or any(p.section_index >= len(sections) for p in proposals):
        raise HTTPException(422, "Invalid interpretation response")
    items = []
    for proposal in proposals:
        section = sections[proposal.section_index]
        items.append(
            await record_evidence(
                db,
                user_id,
                workspace_id,
                EvidenceCreate(
                    document_id=section.document_id,
                    key=proposal.key,
                    typed_value=proposal.typed_value,
                    source_type=SourceType.AI,
                    source_locator=section.source_locator,
                    authority=Authority.INFERRED,
                    confidence=proposal.confidence,
                ),
            )
        )
    return items
