import asyncio
from collections.abc import Awaitable
from typing import TypeVar

from pydantic import ValidationError

from app.analyzers.base import EmailAnalyzer, ReportGenerator
from app.core.errors import (
    AnalysisError, AnalysisTimeoutError,
    ReportGenerationError, ReportGenerationTimeoutError, StructuredOutputError,
)
from app.models.analysis import FinalAnalysisResult, SecurityAnalysis, SecurityReport
from app.models.email import EmailAnalysisRequest

T = TypeVar("T")


async def run_with_timeout(operation: Awaitable[T], timeout_seconds: float) -> T:
    try:
        async with asyncio.timeout(timeout_seconds):
            return await operation
    except TimeoutError as exc:
        raise AnalysisTimeoutError() from exc


class AnalysisService:
    def __init__(
        self, *,
        jev_analyzer: EmailAnalyzer,
        report_generator: ReportGenerator,
        timeout_seconds: float = 30,
    ) -> None:
        self._jev = jev_analyzer
        self._report = report_generator
        self._timeout = timeout_seconds

    async def analyze(self, payload: EmailAnalysisRequest) -> FinalAnalysisResult:
        try:
            decision = SecurityAnalysis.model_validate(await run_with_timeout(
                self._jev.analyze(payload), self._timeout
            )).model_copy(deep=True)
        except AnalysisError:
            raise
        except ValidationError as exc:
            raise StructuredOutputError() from exc
        except Exception as exc:
            raise AnalysisError() from exc

        # Only the completed decision crosses this boundary, never the email payload.
        try:
            report = SecurityReport.model_validate(await run_with_timeout(
                self._report.generate(decision.model_copy(deep=True)), self._timeout
            ))
        except AnalysisTimeoutError as exc:
            raise ReportGenerationTimeoutError() from exc
        except Exception as exc:
            raise ReportGenerationError() from exc
        return FinalAnalysisResult(analysis=decision, report=report, approach="jev_then_gpt")
