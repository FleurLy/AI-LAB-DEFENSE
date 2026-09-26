from typing import Annotated, Literal

from fastapi import APIRouter, Depends

from app.api.dependencies import get_analysis_service
from app.models.analysis import FinalAnalysisResult
from app.models.base import APIModel
from app.models.email import EmailAnalysisRequest
from app.services.analysis_service import AnalysisService

router = APIRouter()


class HealthResponse(APIModel):
    status: Literal["ok"] = "ok"


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse()


@router.post("/analyze", response_model=FinalAnalysisResult)
async def analyze(
    payload: EmailAnalysisRequest,
    service: Annotated[AnalysisService, Depends(get_analysis_service)],
) -> FinalAnalysisResult:
    return await service.analyze(payload)
