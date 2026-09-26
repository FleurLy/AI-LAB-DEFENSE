import asyncio

from pydantic import ValidationError

from app.analyzers.base import EmailAnalyzer
from app.core.errors import AnalysisError, StructuredOutputError
from app.models.comparison import (
    AnalysisComparisonResult,
    AnalysisFailure,
    AnalyzerFailure,
    AnalyzerOutcome,
    AnalyzerSuccess,
)
from app.models.email import EmailAnalysisRequest
from app.services.analysis_service import run_with_timeout


class ComparisonService:
    def __init__(
        self,
        llm_analyzer: EmailAnalyzer,
        jev_analyzer: EmailAnalyzer,
        *,
        llm_model: str,
        jev_model: str,
        timeout_seconds: float = 30,
    ) -> None:
        self._llm_service = llm_analyzer
        self._jev_service = jev_analyzer
        self._timeout_seconds = timeout_seconds
        self._llm_model = llm_model
        self._jev_model = jev_model

    async def analyze(self, payload: EmailAnalysisRequest) -> AnalysisComparisonResult:
        llm, jev = await asyncio.gather(
            self._analyze_one(self._llm_service, self._llm_model, payload),
            self._analyze_one(self._jev_service, self._jev_model, payload),
        )
        return AnalysisComparisonResult(llm=llm, jev=jev)

    async def _analyze_one(
        self, service: EmailAnalyzer, model: str, payload: EmailAnalysisRequest
    ) -> AnalyzerOutcome:
        error: AnalysisError
        try:
            # Independent copies prevent one analyzer from changing the other's evidence.
            result = await run_with_timeout(service.analyze(payload.model_copy(deep=True)), self._timeout_seconds)
            return AnalyzerSuccess(model=model, result=result)
        except AnalysisError as exc:
            error = exc
        except ValidationError:
            error = StructuredOutputError()
        except Exception:
            # Keep the other result even for unexpected adapter failures; never echo details.
            error = AnalysisError()
        return AnalyzerFailure(
            model=model,
            error=AnalysisFailure(
                code=error.code, message=error.message, status_code=error.status_code
            ),
        )
