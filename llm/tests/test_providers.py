import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI
from pydantic import ValidationError

from app.analyzers.llm import LLMEmailAnalyzer
from app.analyzers.providers import create_chat_model
from app.api.dependencies import get_jev_analyzer, get_report_generator
from app.core.config import Settings, get_settings
from app.core.errors import ConfigurationError
from app.main import create_app


def test_openrouter_configuration_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    values = {
        "OPENROUTER_API_KEY": "test-openrouter-key",
        "LLM_MODEL": "openai/gpt-4o-mini",
        "LLM_TEMPERATURE": "0.2",
        "LLM_TIMEOUT_SECONDS": "12",
        "OPENROUTER_SITE_URL": "https://app.example",
        "OPENROUTER_APP_NAME": "Email Defense",
        # Legacy SDK defaults must not override the explicit OpenRouter settings.
        "OPENAI_API_KEY": "unused-legacy-key",
        "OPENAI_API_BASE": "https://legacy.example/v1",
        "OPENAI_BASE_URL": "https://legacy.example/v1",
    }
    for name, value in values.items():
        monkeypatch.setenv(name, value)
    settings = get_settings()
    model = create_chat_model(settings)
    assert isinstance(model, ChatOpenAI)
    assert settings.llm_provider == "openrouter"
    assert settings.openrouter_api_key.get_secret_value() == "test-openrouter-key"
    assert "openai_api_key" not in Settings.model_fields
    assert "test-openrouter-key" not in repr(settings)
    assert model.openai_api_base == "https://openrouter.ai/api/v1"
    assert model.openai_api_key.get_secret_value() == "test-openrouter-key"
    assert model.model_name == "openai/gpt-4o-mini"
    assert model.temperature == 0.2
    assert model.request_timeout == 12
    assert model.max_retries == 0
    assert model.use_responses_api is False
    assert model.default_headers == {
        "HTTP-Referer": "https://app.example", "X-Title": "Email Defense"
    }


@pytest.mark.parametrize(
    "site_url, app_name, expected",
    [
        (None, None, {}),
        ("", "", {}),
        ("   ", "   ", {}),
        ("https://app.example", None, {"HTTP-Referer": "https://app.example"}),
        (None, "Email Defense", {"X-Title": "Email Defense"}),
        (
            " https://app.example ", " Email Defense ",
            {"HTTP-Referer": "https://app.example", "X-Title": "Email Defense"},
        ),
    ],
)
def test_optional_attribution_headers(
    site_url: str | None, app_name: str | None, expected: dict[str, str]
) -> None:
    settings = Settings(
        openrouter_api_key="test-openrouter-key",
        openrouter_site_url=site_url,
        openrouter_app_name=app_name,
    )
    model = create_chat_model(settings)
    assert isinstance(model, ChatOpenAI)
    assert model.default_headers == expected
    for header in ("HTTP-Referer", "X-Title"):
        if header in expected:
            assert model.root_async_client.default_headers[header] == expected[header]
        else:
            assert header not in model.root_async_client.default_headers


@pytest.mark.parametrize(
    "provider_status, expected_status, expected_code",
    [
        (400, 502, "provider_error"),
        (401, 503, "configuration_error"),
        (402, 502, "provider_error"),
        (403, 503, "configuration_error"),
        (429, 502, "provider_error"),
        (500, 502, "provider_error"),
    ],
)
def test_openrouter_errors_do_not_expose_secrets(
    example_payload: dict[str, Any], monkeypatch: pytest.MonkeyPatch,
    provider_status: int, expected_status: int, expected_code: str,
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter-key")
    monkeypatch.setenv("JEV_MODEL", "test-provider/jev-model")
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        assert str(request.url) == "https://openrouter.ai/api/v1/chat/completions"
        assert request.headers["Authorization"] == "Bearer test-openrouter-key"
        return httpx.Response(provider_status, json={
            "error": {
                "code": provider_status,
                "message": "test-openrouter-key private-email-content provider-details",
                "metadata": {"raw": example_payload},
            }
        })

    async def run() -> httpx.Response:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as provider_client:
            with patch("app.analyzers.providers.ChatOpenAI", side_effect=lambda **kwargs: (
                ChatOpenAI(**kwargs, http_async_client=provider_client)
            )):
                async with httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=create_app()),
                    base_url="http://testserver",
                ) as api_client:
                    return await api_client.post("/analyze", json=example_payload)

    response = asyncio.run(run())
    assert response.status_code == expected_status
    assert response.json()["detail"]["code"] == expected_code
    for sensitive in (
        "test-openrouter-key", "private-email-content", "provider-details",
        example_payload["email"]["body_text"],
    ):
        assert sensitive not in response.text
    assert len(calls) == 1


def test_adapter_value_error_does_not_expose_raw_response(
    example_payload: dict[str, Any], monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("JEV_MODEL", "test-provider/jev-model")
    model = MagicMock(spec=BaseChatModel)
    model.with_structured_output.return_value = AsyncMock()
    model.with_structured_output.return_value.ainvoke.side_effect = ValueError(
        "test-openrouter-key private-email-content"
    )
    analyzer = LLMEmailAnalyzer(model)
    app = create_app()
    app.dependency_overrides[get_jev_analyzer] = lambda: analyzer
    app.dependency_overrides[get_report_generator] = lambda: AsyncMock()
    with TestClient(app) as client:
        response = client.post("/analyze", json=example_payload)
    assert response.status_code == 502
    assert response.json()["detail"]["code"] == "provider_error"
    assert "test-openrouter-key" not in response.text
    assert "private-email-content" not in response.text



def test_jev_model_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter-key")
    monkeypatch.setenv("JEV_MODEL", "test-provider/jev-model")
    monkeypatch.setenv("LLM_TEMPERATURE", "0.2")
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "12")
    monkeypatch.setenv("OPENROUTER_SITE_URL", "https://app.example")
    monkeypatch.setenv("OPENROUTER_APP_NAME", "Email Defense")
    settings = get_settings()
    model = create_chat_model(settings, model_type="jev")
    assert isinstance(model, ChatOpenAI)
    assert settings.jev_model == "test-provider/jev-model"
    assert model.model_name == settings.jev_model
    assert model.openai_api_base == "https://openrouter.ai/api/v1"
    assert model.openai_api_key.get_secret_value() == "test-openrouter-key"
    assert model.temperature == settings.llm_temperature
    assert model.request_timeout == settings.llm_timeout_seconds
    assert model.default_headers == {
        "HTTP-Referer": "https://app.example", "X-Title": "Email Defense"
    }
    assert create_chat_model(settings).model_name == settings.llm_model


@pytest.mark.parametrize("jev_model", [None, "", "   "])
def test_invalid_jev_model_is_rejected(jev_model: str | None) -> None:
    with pytest.raises(ValidationError):
        Settings(openrouter_api_key="test-openrouter-key", jev_model=jev_model)


def test_jev_uses_configured_default_when_env_is_absent() -> None:
    settings = Settings(openrouter_api_key="test-openrouter-key")
    model = create_chat_model(settings, model_type="jev")
    assert model.model_name == settings.jev_model
    assert settings.jev_model == Settings.model_fields["jev_model"].default


def test_unknown_model_selection_is_rejected() -> None:
    settings = Settings(openrouter_api_key="test-openrouter-key")
    with pytest.raises(ConfigurationError):
        create_chat_model(settings, model_type="unknown")


def test_jev_model_requires_openrouter_key() -> None:
    settings = Settings(jev_model="test-provider/jev-model")
    with pytest.raises(ConfigurationError):
        create_chat_model(settings, model_type="jev")


@pytest.mark.parametrize("report_model", [None, "", "   ", "provider/report-model"])
def test_report_model_override_and_fallback(report_model):
    settings = Settings(openrouter_api_key="test-key", llm_model="provider/full-model", report_model=report_model)
    assert create_chat_model(settings, model_type="report").model_name == ((report_model or "").strip() or settings.llm_model)


@pytest.mark.parametrize("mode", ["gpt_only", "jev_then_gpt", "invalid"])
def test_only_jev_and_report_are_constructed(monkeypatch, mode):
    monkeypatch.setenv("ANALYSIS_MODE", mode)
    with patch("app.api.dependencies.create_chat_model") as factory:
        get_jev_analyzer()
        get_report_generator()
    assert [call.kwargs["model_type"] for call in factory.call_args_list] == ["jev", "report"]


def test_analysis_mode_is_no_longer_configurable():
    assert "analysis_mode" not in Settings.model_fields
