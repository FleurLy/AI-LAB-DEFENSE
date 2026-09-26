from typing import Annotated, Literal

from fastapi import APIRouter, Depends

from app.api.dependencies import get_comparison_service
from app.models.comparison import AnalysisComparisonResult
from app.models.base import APIModel
from app.models.email import EmailAnalysisRequest
from app.services.comparison_service import ComparisonService

router = APIRouter()


class HealthResponse(APIModel):
    status: Literal["ok"] = "ok"


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse()


@router.post("/analyze", response_model=AnalysisComparisonResult)
async def analyze(
    payload: EmailAnalysisRequest,
    service: Annotated[ComparisonService, Depends(get_comparison_service)],
) -> AnalysisComparisonResult:
    return await service.analyze(payload)
