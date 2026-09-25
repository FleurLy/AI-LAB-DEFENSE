from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be true or false")


@dataclass(frozen=True, slots=True)
class Settings:
    llm_provider: str = "ollama"
    llm_model: str = "qwen3.5:4b"
    llm_base_url: str = "http://localhost:11434/v1"
    llm_api_key: str = "ollama"
    llm_timeout_seconds: float = 180.0
    llm_temperature: float = 0.1
    llm_max_output_tokens: int = 600
    llm_think: bool = False
    max_input_chars: int = 50_000
    results_dir: Path = Path("data/results")
    log_level: str = "INFO"
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        return cls(
            llm_provider=os.getenv("LLM_PROVIDER", "ollama").lower(),
            llm_model=os.getenv("LLM_MODEL", "qwen3.5:4b"),
            llm_base_url=os.getenv("LLM_BASE_URL", "http://localhost:11434/v1").rstrip("/"),
            llm_api_key=os.getenv("LLM_API_KEY", "ollama"),
            llm_timeout_seconds=float(os.getenv("LLM_TIMEOUT_SECONDS", "180")),
            llm_temperature=float(os.getenv("LLM_TEMPERATURE", "0.1")),
            llm_max_output_tokens=int(os.getenv("LLM_MAX_OUTPUT_TOKENS", "600")),
            llm_think=_env_bool("LLM_THINK", False),
            max_input_chars=int(os.getenv("MAX_INPUT_CHARS", "50000")),
            results_dir=Path(os.getenv("RESULTS_DIR", "data/results")),
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
            api_host=os.getenv("API_HOST", "0.0.0.0"),
            api_port=int(os.getenv("API_PORT", "8000")),
        )

    def ensure_directories(self) -> None:
        self.results_dir.mkdir(parents=True, exist_ok=True)

    def validate(self) -> None:
        if self.llm_provider not in {"ollama", "openai_compatible"}:
            raise ValueError("LLM_PROVIDER must be 'ollama' or 'openai_compatible'")
        if not self.llm_model.strip():
            raise ValueError("LLM_MODEL cannot be empty")
        if self.max_input_chars < 5_000:
            raise ValueError("MAX_INPUT_CHARS must be at least 5000")
