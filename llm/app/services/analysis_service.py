import asyncio
from collections.abc import Awaitable
from typing import TypeVar

from pydantic import ValidationError

from app.analyzers.base import EmailAnalyzer, FullEmailAnalyzer, ReportGenerator
from app.core.errors import (
    AnalysisError, AnalysisTimeoutError, ConfigurationError,
    ReportGenerationError, ReportGenerationTimeoutError, StructuredOutputError,
)
from app.models.analysis import AnalysisMode, FinalAnalysisResult, GPTFullAnalysis, SecurityAnalysis, SecurityReport
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
        self, *, analysis_mode: AnalysisMode,
        gpt_analyzer: FullEmailAnalyzer | None = None,
        jev_analyzer: EmailAnalyzer | None = None,
        report_generator: ReportGenerator | None = None,
        timeout_seconds: float = 30,
    ) -> None:
        if analysis_mode not in ("gpt_only", "jev_then_gpt"):
            raise ConfigurationError()
        if (analysis_mode == "gpt_only" and gpt_analyzer is None) or (
            analysis_mode == "jev_then_gpt" and (jev_analyzer is None or report_generator is None)
        ):
            raise ConfigurationError()
        self._mode = analysis_mode
        self._gpt = gpt_analyzer
        self._jev = jev_analyzer
        self._report = report_generator
        self._timeout = timeout_seconds

    async def analyze(self, payload: EmailAnalysisRequest) -> FinalAnalysisResult:
        try:
            if self._mode == "gpt_only":
                assert self._gpt is not None
                result = GPTFullAnalysis.model_validate(await run_with_timeout(
                    self._gpt.analyze(payload), self._timeout
                ))
                return FinalAnalysisResult(**result.model_dump(), approach=self._mode)
            assert self._jev is not None
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
        assert self._report is not None
        try:
            report = SecurityReport.model_validate(await run_with_timeout(
                self._report.generate(decision.model_copy(deep=True)), self._timeout
            ))
        except AnalysisTimeoutError as exc:
            raise ReportGenerationTimeoutError() from exc
        except Exception as exc:
            raise ReportGenerationError() from exc
        return FinalAnalysisResult(analysis=decision, report=report, approach=self._mode)
