import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import ValidationError

from app.analyzers.gpt import GPTEmailAnalyzer
from app.analyzers.report import GPTReportGenerator
from app.core.errors import ReportGenerationError, ReportGenerationTimeoutError, StructuredOutputError
from app.models.analysis import SecurityAnalysis, SecurityReport
from app.models.email import EmailAnalysisRequest
from app.services.analysis_service import AnalysisService


def test_report_cannot_mutate_jev_decision(example_payload, security_analysis, security_report):
    snapshot = security_analysis.model_dump()
    jev, reporter = AsyncMock(), AsyncMock()
    jev.analyze.return_value = security_analysis

    async def generate(decision):
        assert isinstance(decision, SecurityAnalysis)
        decision.phishing_probability = 0.0
        decision.evidence.clear()
        return security_report

    reporter.generate.side_effect = generate
    service = AnalysisService(jev_analyzer=jev,
                              report_generator=reporter)
    result = asyncio.run(service.analyze(EmailAnalysisRequest.model_validate(example_payload)))
    assert result.analysis.model_dump() == snapshot
    assert security_analysis.model_dump() == snapshot


@pytest.mark.parametrize("adapter", [GPTEmailAnalyzer, GPTReportGenerator])
def test_new_adapters_reject_invalid_output(adapter, example_payload, security_analysis):
    model = MagicMock(spec=BaseChatModel)
    model.with_structured_output.return_value = AsyncMock()
    model.with_structured_output.return_value.ainvoke.return_value = {"analysis": "invented"}
    instance = adapter(model)
    operation = (instance.generate(security_analysis) if adapter is GPTReportGenerator
                 else instance.analyze(EmailAnalysisRequest.model_validate(example_payload)))
    with pytest.raises(StructuredOutputError):
        asyncio.run(operation)


def test_report_schema_forbids_decision_fields(security_report):
    with pytest.raises(ValidationError):
        SecurityReport.model_validate({**security_report.model_dump(), "attack_type": "none"})


def test_security_schema_forbids_report_fields(security_analysis):
    with pytest.raises(ValidationError):
        SecurityAnalysis.model_validate({**security_analysis.model_dump(), "summary": "report"})


def test_report_timeout_cancels_report_without_fallback(example_payload, security_analysis):
    jev = AsyncMock()
    jev.analyze.return_value = security_analysis
    cancelled = []

    class SlowReport:
        async def generate(self, analysis):
            try:
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                cancelled.append(True)
                raise

    service = AnalysisService(jev_analyzer=jev,
                              report_generator=SlowReport(), timeout_seconds=0.01)
    with pytest.raises(ReportGenerationTimeoutError):
        asyncio.run(service.analyze(EmailAnalysisRequest.model_validate(example_payload)))
    assert cancelled == [True]
    jev.analyze.assert_awaited_once()


def test_invalid_report_is_distinct_error(example_payload, security_analysis):
    jev, reporter = AsyncMock(), AsyncMock()
    jev.analyze.return_value = security_analysis
    reporter.generate.return_value = {"summary": "incomplete"}
    service = AnalysisService(jev_analyzer=jev, report_generator=reporter)
    with pytest.raises(ReportGenerationError):
        asyncio.run(service.analyze(EmailAnalysisRequest.model_validate(example_payload)))
