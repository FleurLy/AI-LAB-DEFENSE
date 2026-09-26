from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from app.analyzers.base import EmailAnalyzer, ReportGenerator
from app.analyzers.jev import JevEmailAnalyzer
from app.analyzers.providers import create_chat_model
from app.analyzers.report import GPTReportGenerator
from app.core.config import Settings, get_settings
from app.core.errors import ConfigurationError
from app.services.analysis_service import AnalysisService


@lru_cache
def get_jev_analyzer() -> EmailAnalyzer:
    settings = get_settings()
    try:
        return JevEmailAnalyzer(create_chat_model(settings, model_type="jev"))
    except (ValueError, NotImplementedError) as exc:
        raise ConfigurationError() from exc


@lru_cache
def get_report_generator() -> ReportGenerator:
    settings = get_settings()
    try:
        return GPTReportGenerator(create_chat_model(settings, model_type="report"))
    except (ValueError, NotImplementedError) as exc:
        raise ConfigurationError() from exc


def get_analysis_service(
    jev: Annotated[EmailAnalyzer, Depends(get_jev_analyzer)],
    report: Annotated[ReportGenerator, Depends(get_report_generator)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AnalysisService:
    return AnalysisService(
        jev_analyzer=jev, report_generator=report,
        timeout_seconds=settings.llm_timeout_seconds,
    )
