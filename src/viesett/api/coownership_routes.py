from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends

from viesett.api.dependencies import Db, UserId, require_user
from viesett.domain.coownership import BuyerQuestion, CoFinding, CoSnapshot
from viesett.domain.intelligence import EvaluationRequest
from viesett.services.coownership import refresh_coownership

router = APIRouter(prefix="/api/v1", dependencies=[Depends(require_user)])


@router.post("/workspaces/{workspace_id}/co-ownership/refresh", response_model=CoSnapshot)
async def refresh(workspace_id: UUID, data: EvaluationRequest, db: Db, user: UserId) -> CoSnapshot:
    return await refresh_coownership(db, user, workspace_id, data.evaluation_date)


@router.get("/workspaces/{workspace_id}/co-ownership", response_model=CoSnapshot)
async def snapshot(
    workspace_id: UUID, db: Db, user: UserId, evaluation_date: date | None = None
) -> CoSnapshot:
    return await refresh_coownership(db, user, workspace_id, evaluation_date)


@router.get("/workspaces/{workspace_id}/cross-document-findings", response_model=list[CoFinding])
async def findings(
    workspace_id: UUID, db: Db, user: UserId, evaluation_date: date | None = None
) -> list[CoFinding]:
    return (
        await refresh_coownership(db, user, workspace_id, evaluation_date)
    ).cross_document_findings


@router.get("/workspaces/{workspace_id}/buyer-questions", response_model=list[BuyerQuestion])
async def questions(
    workspace_id: UUID, db: Db, user: UserId, evaluation_date: date | None = None
) -> list[BuyerQuestion]:
    return (await refresh_coownership(db, user, workspace_id, evaluation_date)).questions
