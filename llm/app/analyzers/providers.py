from typing import Literal

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI
from pydantic import ValidationError

from app.core.config import Settings
from app.core.errors import ConfigurationError


def create_chat_model(
    settings: Settings, *, model_type: Literal["llm", "jev", "report"] = "llm"
) -> BaseChatModel:
    """Create a configured chat model through OpenRouter."""
    if settings.llm_provider != "openrouter":
        raise ConfigurationError()
    if model_type == "llm":
        model_name = settings.llm_model
    elif model_type == "jev":
        model_name = settings.jev_model
    elif model_type == "report":
        model_name = (settings.report_model or "").strip() or settings.llm_model
    else:
        raise ConfigurationError()
    if model_name is None or not model_name.strip():
        raise ConfigurationError()
    key = settings.openrouter_api_key
    if key is None or not key.get_secret_value().strip():
        raise ConfigurationError()
    headers: dict[str, str] = {}
    if settings.openrouter_site_url and settings.openrouter_site_url.strip():
        headers["HTTP-Referer"] = settings.openrouter_site_url.strip()
    if settings.openrouter_app_name and settings.openrouter_app_name.strip():
        headers["X-Title"] = settings.openrouter_app_name.strip()
    try:
        return ChatOpenAI(
            model=model_name.strip(),
            api_key=key,
            base_url="https://openrouter.ai/api/v1",
            default_headers=headers,
            # Use OpenRouter's OpenAI-compatible chat-completions endpoint.
            use_responses_api=False,
            temperature=settings.llm_temperature,
            timeout=settings.llm_timeout_seconds,
            max_retries=0,
        )
    except (ValidationError, ValueError) as exc:
        raise ConfigurationError() from exc
