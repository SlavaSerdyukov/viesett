from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response
from sqlalchemy import select

from viesett.api.dependencies import Db, UserId, require_user, runtime
from viesett.db.intelligence_models import DueDiligenceEvaluation
from viesett.db.models import (
    DocumentRequestDraft,
    EvidenceItem,
    Finding,
    PolicyVersion,
    PropertyDocument,
    PropertyWorkspace,
    utcnow,
)
from viesett.domain.schemas import (
    AcknowledgementCreate,
    AcknowledgementOut,
    DocumentOut,
    DraftCreate,
    DraftOut,
    EvidenceOut,
    ExportOut,
    FindingOut,
    PolicyOut,
    WorkspaceCreate,
    WorkspaceOut,
    WorkspaceUpdate,
)
from viesett.domain.types import DocumentKind, DocumentStatus, WorkspaceStatus
from viesett.services import deletion
from viesett.services.documents import upload_document
from viesett.services.drafts import CO_COMPONENT_LABELS, generate_request
from viesett.services.evidence import list_findings
from viesett.services.export import export_user
from viesett.services.ownership import owned_document, owned_workspace
from viesett.services.policies import acknowledge, acknowledgements

router = APIRouter(prefix="/api/v1", dependencies=[Depends(require_user)])


@router.post("/workspaces", status_code=201, response_model=WorkspaceOut)
async def create_workspace(data: WorkspaceCreate, db: Db, user: UserId) -> PropertyWorkspace:
    workspace = PropertyWorkspace(owner_user_id=user, canonical_address=data.canonical_address)
    db.add(workspace)
    await db.commit()
    return workspace


@router.get("/workspaces", response_model=list[WorkspaceOut])
async def get_workspaces(
    db: Db,
    user: UserId,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[PropertyWorkspace]:
    return list(
        (
            await db.scalars(
                select(PropertyWorkspace)
                .where(
                    PropertyWorkspace.owner_user_id == user,
                )
                .order_by(PropertyWorkspace.created_at, PropertyWorkspace.id)
                .limit(limit)
                .offset(offset)
            )
        ).all()
    )


@router.get("/workspaces/{workspace_id}", response_model=WorkspaceOut)
async def get_workspace(workspace_id: UUID, db: Db, user: UserId) -> PropertyWorkspace:
    return await owned_workspace(db, user, workspace_id)


@router.patch("/workspaces/{workspace_id}", response_model=WorkspaceOut)
async def archive_workspace(
    workspace_id: UUID,
    data: WorkspaceUpdate,
    db: Db,
    user: UserId,
) -> PropertyWorkspace:
    workspace = await owned_workspace(db, user, workspace_id, lock=True)
    workspace.status = data.status
    workspace.archived_at = utcnow() if data.status == WorkspaceStatus.ARCHIVED else None
    await db.commit()
    return workspace


@router.delete("/workspaces/{workspace_id}", status_code=204)
async def remove_workspace(workspace_id: UUID, request: Request, db: Db, user: UserId) -> None:
    await deletion.delete_workspace(db, user, workspace_id, runtime(request).storage)


@router.post("/workspaces/{workspace_id}/documents", response_model=DocumentOut, status_code=201)
async def upload(
    workspace_id: UUID,
    request: Request,
    response: Response,
    db: Db,
    user: UserId,
    filename: Annotated[str, Header(alias="X-Filename", max_length=512)] = "document.pdf",
    kind: Annotated[DocumentKind, Header(alias="X-Document-Kind")] = DocumentKind.UNKNOWN,
) -> PropertyDocument:
    context = runtime(request)
    document, created = await upload_document(
        db,
        user,
        workspace_id,
        await request.body(),
        filename,
        request.headers.get("content-type", ""),
        kind,
        context.settings.max_upload_bytes,
        context.storage,
        context.pipeline,
    )
    response.status_code = 201 if created else 200
    return document


@router.get("/workspaces/{workspace_id}/documents", response_model=list[DocumentOut])
async def get_documents(workspace_id: UUID, db: Db, user: UserId) -> list[PropertyDocument]:
    await owned_workspace(db, user, workspace_id)
    return list(
        (
            await db.scalars(
                select(PropertyDocument)
                .where(
                    PropertyDocument.workspace_id == workspace_id,
                    PropertyDocument.status != DocumentStatus.DELETED,
                )
                .order_by(PropertyDocument.created_at, PropertyDocument.id)
            )
        ).all()
    )


@router.get("/workspaces/{workspace_id}/documents/{document_id}", response_model=DocumentOut)
async def get_document(
    workspace_id: UUID,
    document_id: UUID,
    db: Db,
    user: UserId,
) -> PropertyDocument:
    return await owned_document(db, user, workspace_id, document_id)


@router.get("/workspaces/{workspace_id}/documents/{document_id}/content")
async def download_document(
    workspace_id: UUID,
    document_id: UUID,
    request: Request,
    db: Db,
    user: UserId,
) -> Response:
    document = await owned_document(db, user, workspace_id, document_id)
    if document.status != DocumentStatus.READY:
        raise HTTPException(409, "Only ready documents can be downloaded")
    try:
        content = runtime(request).storage.read(document.storage_key)
    except OSError:
        raise HTTPException(503, "Private document temporarily unavailable") from None
    return Response(
        content,
        media_type=document.media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{document.id}.pdf"',
        },
    )


@router.delete("/workspaces/{workspace_id}/documents/{document_id}", status_code=204)
async def remove_document(
    workspace_id: UUID,
    document_id: UUID,
    request: Request,
    db: Db,
    user: UserId,
) -> None:
    await deletion.delete_document(db, user, workspace_id, document_id, runtime(request).storage)


@router.get("/workspaces/{workspace_id}/evidence", response_model=list[EvidenceOut])
async def get_evidence(
    workspace_id: UUID,
    db: Db,
    user: UserId,
    include_history: bool = False,
) -> list[EvidenceItem]:
    await owned_workspace(db, user, workspace_id)
    query = select(EvidenceItem).where(EvidenceItem.workspace_id == workspace_id)
    if not include_history:
        query = query.where(EvidenceItem.superseded_at.is_(None))
    return list((await db.scalars(query.order_by(EvidenceItem.created_at, EvidenceItem.id))).all())


@router.get("/workspaces/{workspace_id}/findings", response_model=list[FindingOut])
async def get_findings(
    workspace_id: UUID, db: Db, user: UserId, evaluation_date: date | None = None
) -> list[FindingOut]:
    await owned_workspace(db, user, workspace_id)
    if (
        await db.scalar(
            select(DueDiligenceEvaluation.id)
            .where(
                DueDiligenceEvaluation.workspace_id == workspace_id,
            )
            .limit(1)
        )
        is not None
        or await db.scalar(
            select(Finding.id)
            .where(
                Finding.workspace_id == workspace_id,
                Finding.provenance["source"].as_string() == "viesett.rules",
            )
            .limit(1)
        )
        is not None
    ):
        from viesett.services.due_diligence import refresh_due_diligence

        await refresh_due_diligence(db, user, workspace_id, evaluation_date)
    from viesett.services.coownership import refresh_if_present

    await refresh_if_present(db, user, workspace_id, evaluation_date)
    return await list_findings(db, [workspace_id])


@router.post(
    "/workspaces/{workspace_id}/document-request-draft", response_model=DraftOut, status_code=201
)
async def create_draft(
    workspace_id: UUID,
    data: DraftCreate,
    db: Db,
    user: UserId,
) -> DocumentRequestDraft:
    await owned_workspace(db, user, workspace_id, lock=True)
    kinds, text = generate_request(data)
    from viesett.domain.coownership import CO_KINDS

    if any(kind in CO_KINDS for kind in kinds):
        from viesett.services.coownership import refresh_coownership

        co = await refresh_coownership(db, user, workspace_id)
        lines = []
        for component in co.article_3_94_completeness:
            if component.status in {"MISSING", "PARTIAL", "UNPARSEABLE"}:
                label = CO_COMPONENT_LABELS[data.language][component.code]
                if component.coverage:
                    label += ": " + ", ".join(
                        g.start.isoformat() + "–" + g.end.isoformat()
                        for g in component.coverage.gaps
                    )
                lines.append("- " + label)
        if lines:
            text += (
                "\n\n"
                + (
                    "Missing information / periods:\n"
                    if data.language == "en"
                    else "Ontbrekende informatie / periodes:\n"
                )
                + "\n".join(lines)
            )
    draft = DocumentRequestDraft(
        workspace_id=workspace_id,
        requested_document_types=kinds,
        generated_text=text,
        language=data.language,
    )
    db.add(draft)
    await db.commit()
    return draft


@router.get("/policies", response_model=list[PolicyOut])
async def get_policies(db: Db) -> list[PolicyVersion]:
    return list(
        (
            await db.scalars(
                select(PolicyVersion)
                .where(
                    PolicyVersion.current.is_(True),
                )
                .order_by(PolicyVersion.policy_type)
            )
        ).all()
    )


@router.post("/me/policy-acknowledgements", status_code=204)
async def acknowledge_policy(data: AcknowledgementCreate, db: Db, user: UserId) -> None:
    await acknowledge(db, user, data.policy_version_id)


@router.get("/me/policy-acknowledgements", response_model=list[AcknowledgementOut])
async def get_acknowledgements(db: Db, user: UserId) -> list[AcknowledgementOut]:
    return await acknowledgements(db, user)


@router.get("/upload-guidance")
async def upload_guidance() -> dict[str, str | list[str]]:
    return {
        "purpose": "Files are processed only to analyse this property and create your Viesett "
        "buyer dossier.",
        "avoid": [
            "identity documents",
            "passports",
            "Belgian eID",
            "unrelated banking documents",
            "health information",
            "private correspondence",
            "unnecessary sensitive data",
        ],
        "training": "Customer documents are not used to train AI models.",
        "privacy_notice": "/api/v1/policies",
    }


@router.get("/me/export", response_model=ExportOut)
async def get_export(db: Db, user: UserId) -> ExportOut:
    return await export_user(db, user)


@router.delete("/me", status_code=204)
async def remove_account(request: Request, db: Db, user: UserId) -> None:
    await deletion.delete_account(db, user, runtime(request).storage)
