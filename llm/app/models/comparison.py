from typing import Annotated, Literal

from pydantic import Field

from app.models.analysis import AIAnalysisResult
from app.models.base import APIModel


class AnalysisFailure(APIModel):
    code: str
    message: str
    status_code: int


class AnalyzerSuccess(APIModel):
    status: Literal["success"] = "success"
    model: str
    result: AIAnalysisResult


class AnalyzerFailure(APIModel):
    status: Literal["error"] = "error"
    model: str
    error: AnalysisFailure


AnalyzerOutcome = Annotated[
    AnalyzerSuccess | AnalyzerFailure, Field(discriminator="status")
]


class AnalysisComparisonResult(APIModel):
    llm: AnalyzerOutcome
    jev: AnalyzerOutcome
