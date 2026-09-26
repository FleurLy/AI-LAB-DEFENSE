import asyncio
from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.analyzers.base import EmailAnalyzer
from app.api.dependencies import get_analyzer, get_jev_analyzer
from app.core.errors import (
    AnalysisTimeoutError,
    ConfigurationError,
    ProviderError,
    StructuredOutputError,
)
from app.main import create_app
from app.models.analysis import AIAnalysisResult
from app.models.email import EmailAnalysisRequest


@pytest.fixture
def mock_api(
    analysis_result: AIAnalysisResult, monkeypatch: pytest.MonkeyPatch
) -> tuple[FastAPI, AsyncMock, AsyncMock]:
    monkeypatch.setenv("LLM_MODEL", "openai/gpt-4o-mini")
    monkeypatch.setenv("JEV_MODEL", "test-provider/jev-model")
    llm = AsyncMock(spec=EmailAnalyzer)
    jev = AsyncMock(spec=EmailAnalyzer)
    llm.analyze.return_value = analysis_result
    jev.analyze.return_value = AIAnalysisResult.model_validate({
        **analysis_result.model_dump(), "phishing_probability": 0.25,
    })
    app = create_app()
    app.dependency_overrides[get_analyzer] = lambda: llm
    app.dependency_overrides[get_jev_analyzer] = lambda: jev
    return app, llm, jev


def test_health_without_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_TEMPERATURE", "invalid")
    with TestClient(create_app()) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_analyze_returns_both_results(
    example_payload: dict[str, Any], mock_api: tuple[FastAPI, AsyncMock, AsyncMock]
) -> None:
    app, llm, jev = mock_api
    with TestClient(app) as client:
        response = client.post("/analyze", json=example_payload)
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"llm", "jev"}
    for name, analyzer, model in (
        ("llm", llm, "openai/gpt-4o-mini"),
        ("jev", jev, "test-provider/jev-model"),
    ):
        assert body[name] == {
            "status": "success", "model": model,
            "result": analyzer.analyze.return_value.model_dump(mode="json"),
        }
        analyzer.analyze.assert_awaited_once()
        received = analyzer.analyze.call_args.args[0]
        assert isinstance(received, EmailAnalysisRequest)
        assert received.model_dump(mode="json", by_alias=True) == example_payload
    assert body["llm"]["result"] != body["jev"]["result"]


@pytest.mark.parametrize("invalid_json", [False, True])
def test_invalid_payload_returns_422_without_calling_analyzers(
    invalid_json: bool, mock_api: tuple[FastAPI, AsyncMock, AsyncMock]
) -> None:
    app, llm, jev = mock_api
    with TestClient(app) as client:
        response = client.post(
            "/analyze", content="{" if invalid_json else "{}",
            headers={"Content-Type": "application/json"},
        )
    assert response.status_code == 422
    assert response.json()["detail"]
    llm.analyze.assert_not_awaited()
    jev.analyze.assert_not_awaited()


def test_validation_error_does_not_echo_email_content(
    example_payload: dict[str, Any], mock_api: tuple[FastAPI, AsyncMock, AsyncMock]
) -> None:
    example_payload["email"]["body_text"] = {"secret": "private-email-content"}
    with TestClient(mock_api[0]) as client:
        response = client.post("/analyze", json=example_payload)
    assert response.status_code == 422
    assert "private-email-content" not in response.text


@pytest.mark.parametrize(
    "name, value",
    [
        ("OPENROUTER_API_KEY", ""),
        ("OPENROUTER_API_KEY", "   "),
        ("LLM_PROVIDER", "openai"),
        ("LLM_PROVIDER", "unsupported"),
        ("LLM_MODEL", ""),
        ("LLM_MODEL", "   "),
        ("LLM_TEMPERATURE", "not-a-number"),
        ("LLM_TIMEOUT_SECONDS", "0"),
    ],
)
def test_bad_configuration_returns_503(
    example_payload: dict[str, Any], monkeypatch: pytest.MonkeyPatch, name: str, value: str
) -> None:
    monkeypatch.setenv(name, value)
    with TestClient(create_app()) as client:
        response = client.post("/analyze", json=example_payload)
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "configuration_error"


@pytest.mark.parametrize("jev_model", ["", "   "])
def test_invalid_jev_model_returns_503_before_analysis(
    example_payload: dict[str, Any], monkeypatch: pytest.MonkeyPatch, jev_model: str
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter-key")
    monkeypatch.setenv("JEV_MODEL", jev_model)
    llm = AsyncMock(spec=EmailAnalyzer)
    app = create_app()
    app.dependency_overrides[get_analyzer] = lambda: llm
    with TestClient(app) as client:
        response = client.post("/analyze", json=example_payload)
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "configuration_error"
    llm.analyze.assert_not_awaited()


def test_missing_api_key_returns_503(example_payload: dict[str, Any]) -> None:
    with TestClient(create_app()) as client:
        response = client.post("/analyze", json=example_payload)
    assert response.status_code == 503
    assert "API key" in response.json()["detail"]["message"]


def test_openai_key_cannot_replace_openrouter_key(
    example_payload: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "unused-legacy-key")
    with TestClient(create_app()) as client:
        response = client.post("/analyze", json=example_payload)
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "configuration_error"
    assert "unused-legacy-key" not in response.text


@pytest.mark.parametrize("failed_name", ["llm", "jev"])
@pytest.mark.parametrize(
    "error, status, code",
    [
        (ConfigurationError, 503, "configuration_error"),
        (ProviderError, 502, "provider_error"),
        (StructuredOutputError, 502, "structured_output_error"),
        (AnalysisTimeoutError, 504, "analysis_timeout"),
        (RuntimeError, 500, "analysis_error"),
    ],
)
def test_failed_analysis_preserves_the_other_result(
    example_payload: dict[str, Any], mock_api: tuple[FastAPI, AsyncMock, AsyncMock],
    failed_name: str, error: type[Exception], status: int, code: str,
) -> None:
    app, llm, jev = mock_api
    analyzers = {"llm": llm, "jev": jev}
    analyzers[failed_name].analyze.side_effect = error("secret-provider-details")
    with TestClient(app) as client:
        response = client.post("/analyze", json=example_payload)
    assert response.status_code == 200
    body = response.json()
    assert body[failed_name]["status"] == "error"
    assert body[failed_name]["error"]["code"] == code
    assert body[failed_name]["error"]["status_code"] == status
    successful_name = "jev" if failed_name == "llm" else "llm"
    assert body[successful_name]["status"] == "success"
    assert body[successful_name]["result"] == analyzers[successful_name].analyze.return_value.model_dump(mode="json")
    assert "secret-provider-details" not in response.text
    llm.analyze.assert_awaited_once()
    jev.analyze.assert_awaited_once()


def test_both_analysis_errors_are_returned(
    example_payload: dict[str, Any], mock_api: tuple[FastAPI, AsyncMock, AsyncMock]
) -> None:
    app, llm, jev = mock_api
    llm.analyze.side_effect = ProviderError("secret-llm")
    jev.analyze.side_effect = StructuredOutputError("secret-jev")
    with TestClient(app) as client:
        response = client.post("/analyze", json=example_payload)
    assert response.status_code == 200
    assert response.json()["llm"]["error"]["code"] == "provider_error"
    assert response.json()["jev"]["error"]["code"] == "structured_output_error"
    assert "secret-" not in response.text


@pytest.mark.parametrize("slow_name", ["llm", "jev"])
def test_service_timeout_cancels_only_slow_analysis(
    example_payload: dict[str, Any], monkeypatch: pytest.MonkeyPatch,
    mock_api: tuple[FastAPI, AsyncMock, AsyncMock], slow_name: str,
) -> None:
    class SlowAnalyzer:
        cancelled = False

        async def analyze(self, payload: EmailAnalysisRequest) -> AIAnalysisResult:
            try:
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                self.cancelled = True
                raise
            raise AssertionError("The analysis should have been cancelled")

    analyzer = SlowAnalyzer()
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "0.01")
    app = mock_api[0]
    dependency = get_analyzer if slow_name == "llm" else get_jev_analyzer
    app.dependency_overrides[dependency] = lambda: analyzer
    with TestClient(app) as client:
        response = client.post("/analyze", json=example_payload)
    assert response.status_code == 200
    assert response.json()[slow_name]["error"]["status_code"] == 504
    assert response.json()["jev" if slow_name == "llm" else "llm"]["status"] == "success"
    assert analyzer.cancelled


def test_openapi_exposes_comparison_and_bounded_probabilities() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/openapi.json")
    assert response.status_code == 200
    specification = response.json()
    schemas = specification["components"]["schemas"]
    assert "from" in schemas["EmailData"]["properties"]
    assert "from_" not in schemas["EmailData"]["properties"]
    probability = schemas["AIAnalysisResult"]["properties"]["phishing_probability"]
    assert probability["minimum"] == 0
    assert probability["maximum"] == 1
    assert set(schemas["AnalysisComparisonResult"]["properties"]) == {"llm", "jev"}
    response_schema = specification["paths"]["/analyze"]["post"]["responses"]["200"]["content"]["application/json"]["schema"]
    assert response_schema["$ref"].endswith("/AnalysisComparisonResult")
