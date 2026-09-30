from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.integrations.llm import LlmConnector, get_llm_connector
from app.schemas.analysis import (
    AnalysisOverview,
    ErrorAnalysisRead,
    GenerateVariantsRequest,
    QuestionVariantRead,
    VariantStatus,
)
from app.services import analysis as service

router = APIRouter(prefix="/analysis", tags=["analysis"])
DbSession = Annotated[Session, Depends(get_db)]
Llm = Annotated[LlmConnector, Depends(get_llm_connector)]


@router.get("/overview", response_model=AnalysisOverview)
def get_overview(db: DbSession) -> AnalysisOverview:
    return service.overview(db)


@router.get(
    "/knowledge-points/{point_id}/error-analysis", response_model=ErrorAnalysisRead
)
def get_error_analysis(point_id: int, db: DbSession) -> ErrorAnalysisRead:
    return service.get_error_analysis(db, point_id)


@router.post(
    "/knowledge-points/{point_id}/error-analysis/generate", response_model=ErrorAnalysisRead
)
def generate_error_analysis(point_id: int, db: DbSession, llm: Llm) -> ErrorAnalysisRead:
    return service.generate_error_analysis(db, point_id, llm)


@router.get(
    "/knowledge-points/{point_id}/question-variants", response_model=list[QuestionVariantRead]
)
def list_question_variants(
    point_id: int, db: DbSession, status: VariantStatus | None = Query(default=None)
) -> list[QuestionVariantRead]:
    return service.list_question_variants(db, point_id, status)


@router.post(
    "/knowledge-points/{point_id}/question-variants/generate",
    response_model=list[QuestionVariantRead],
)
def generate_question_variants(
    point_id: int, payload: GenerateVariantsRequest, db: DbSession, llm: Llm
) -> list[QuestionVariantRead]:
    return service.generate_question_variants(db, point_id, llm, payload.count)


@router.post(
    "/question-variants/{variant_id}/approve", response_model=QuestionVariantRead
)
def approve_question_variant(variant_id: int, db: DbSession) -> QuestionVariantRead:
    return service.approve_variant(db, variant_id)


@router.post(
    "/question-variants/{variant_id}/reject", response_model=QuestionVariantRead
)
def reject_question_variant(variant_id: int, db: DbSession) -> QuestionVariantRead:
    return service.reject_variant(db, variant_id)
