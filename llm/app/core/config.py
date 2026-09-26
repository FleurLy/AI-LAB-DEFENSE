from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.errors import ConfigurationError


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    report_model: str | None = None
    llm_provider: Literal["openrouter"] = "openrouter"
    llm_model: str = Field(
        default="google/gemma-4-26b-a4b-it:free", min_length=1, pattern=r"\S"
    )
    jev_model: str = Field(
        default="typesafe/jev-router", min_length=1, pattern=r"\S"
    )
    llm_temperature: float = Field(default=0, ge=0, le=2, allow_inf_nan=False)
    llm_timeout_seconds: float = Field(default=30, gt=0, allow_inf_nan=False)
    openrouter_api_key: SecretStr | None = None
    openrouter_site_url: str | None = None
    openrouter_app_name: str | None = None


@lru_cache
def get_settings() -> Settings:
    try:
        return Settings()
    except ValidationError as exc:
        raise ConfigurationError() from exc
