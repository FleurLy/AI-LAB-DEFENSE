from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from app.analyzers.base import EmailAnalyzer
from app.analyzers.jev import JevEmailAnalyzer
from app.analyzers.llm import LLMEmailAnalyzer
from app.analyzers.providers import create_chat_model
from app.core.config import Settings, get_settings
from app.core.errors import ConfigurationError
from app.services.comparison_service import ComparisonService


@lru_cache
def get_analyzer() -> EmailAnalyzer:
    # Lazy construction keeps health checks and dependency overrides key-free.
    try:
        return LLMEmailAnalyzer(create_chat_model(get_settings()))
    except (ValueError, NotImplementedError) as exc:
        raise ConfigurationError() from exc


@lru_cache
def get_jev_analyzer() -> EmailAnalyzer:
    try:
        return JevEmailAnalyzer(create_chat_model(get_settings(), model_type="jev"))
    except (ValueError, NotImplementedError) as exc:
        raise ConfigurationError() from exc


def get_comparison_service(
    llm_analyzer: Annotated[EmailAnalyzer, Depends(get_analyzer)],
    jev_analyzer: Annotated[EmailAnalyzer, Depends(get_jev_analyzer)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ComparisonService:
    if not settings.jev_model or not settings.jev_model.strip():
        raise ConfigurationError()
    return ComparisonService(
        llm_analyzer,
        jev_analyzer,
        llm_model=settings.llm_model.strip(),
        jev_model=settings.jev_model.strip(),
        timeout_seconds=settings.llm_timeout_seconds,
    )

