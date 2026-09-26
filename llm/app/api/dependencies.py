from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from app.analyzers.base import EmailAnalyzer, FullEmailAnalyzer, ReportGenerator
from app.analyzers.gpt import GPTEmailAnalyzer
from app.analyzers.jev import JevEmailAnalyzer
from app.analyzers.providers import create_chat_model
from app.analyzers.report import GPTReportGenerator
from app.core.config import Settings, get_settings
from app.core.errors import ConfigurationError
from app.services.analysis_service import AnalysisService


@lru_cache
def get_analyzer() -> FullEmailAnalyzer | None:
    settings = get_settings()
    if settings.analysis_mode != "gpt_only":
        return None
    try:
        return GPTEmailAnalyzer(create_chat_model(settings))
    except (ValueError, NotImplementedError) as exc:
        raise ConfigurationError() from exc


@lru_cache
def get_jev_analyzer() -> EmailAnalyzer | None:
    settings = get_settings()
    if settings.analysis_mode != "jev_then_gpt":
        return None
    try:
        return JevEmailAnalyzer(create_chat_model(settings, model_type="jev"))
    except (ValueError, NotImplementedError) as exc:
        raise ConfigurationError() from exc


@lru_cache
def get_report_generator() -> ReportGenerator | None:
    settings = get_settings()
    if settings.analysis_mode != "jev_then_gpt":
        return None
    try:
        return GPTReportGenerator(create_chat_model(settings, model_type="report"))
    except (ValueError, NotImplementedError) as exc:
        raise ConfigurationError() from exc


def get_analysis_service(
    gpt: Annotated[FullEmailAnalyzer | None, Depends(get_analyzer)],
    jev: Annotated[EmailAnalyzer | None, Depends(get_jev_analyzer)],
    report: Annotated[ReportGenerator | None, Depends(get_report_generator)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AnalysisService:
    return AnalysisService(
        analysis_mode=settings.analysis_mode, gpt_analyzer=gpt,
        jev_analyzer=jev, report_generator=report,
        timeout_seconds=settings.llm_timeout_seconds,
    )
