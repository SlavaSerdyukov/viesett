from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Request

from viesett.api.dependencies import Db, UserId, require_user, runtime
from viesett.domain.intelligence import (
    AnalysisOut,
    AnalysisReport,
    AnalyzeRequest,
    EvaluationOut,
    EvaluationRequest,
)
from viesett.services.document_analysis import analysis_report, analyze_document
from viesett.services.due_diligence import refresh_due_diligence

router = APIRouter(prefix="/api/v1", dependencies=[Depends(require_user)])


@router.post(
    "/workspaces/{workspace_id}/documents/{document_id}/analyze", response_model=AnalysisOut
)
async def analyze(
    workspace_id: UUID,
    document_id: UUID,
    data: AnalyzeRequest,
    request: Request,
    db: Db,
    user: UserId,
) -> AnalysisOut:
    context = runtime(request)
    return await analyze_document(
        db, user, workspace_id, document_id, data, context.settings, context.storage
    )


@router.get(
    "/workspaces/{workspace_id}/documents/{document_id}/analysis", response_model=AnalysisReport
)
async def get_analysis(
    workspace_id: UUID, document_id: UUID, db: Db, user: UserId, include_history: bool = False
) -> AnalysisReport:
    return await analysis_report(db, user, workspace_id, document_id, include_history)


@router.post("/workspaces/{workspace_id}/due-diligence/refresh", response_model=EvaluationOut)
async def refresh(
    workspace_id: UUID, data: EvaluationRequest, db: Db, user: UserId
) -> EvaluationOut:
    return await refresh_due_diligence(db, user, workspace_id, data.evaluation_date)


@router.get("/workspaces/{workspace_id}/document-requirements", response_model=EvaluationOut)
async def requirements(
    workspace_id: UUID, db: Db, user: UserId, evaluation_date: date | None = None
) -> EvaluationOut:
    return await refresh_due_diligence(db, user, workspace_id, evaluation_date)
