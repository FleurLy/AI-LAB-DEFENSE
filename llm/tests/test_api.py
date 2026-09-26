import asyncio
from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.analyzers.base import EmailAnalyzer
from app.api.dependencies import get_analyzer, get_jev_analyzer, get_report_generator
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
def mock_api(full_analysis, security_analysis, security_report, monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "openai/gpt-4o-mini")
    monkeypatch.setenv("JEV_MODEL", "test-provider/jev-model")
    llm, jev, reporter = AsyncMock(), AsyncMock(), AsyncMock()
    llm.analyze.return_value = full_analysis
    jev.analyze.return_value = security_analysis
    reporter.generate.return_value = security_report
    app = create_app()
    app.dependency_overrides[get_analyzer] = lambda: llm
    app.dependency_overrides[get_jev_analyzer] = lambda: jev
    app.dependency_overrides[get_report_generator] = lambda: reporter
    return app, llm, jev


def test_health_without_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_TEMPERATURE", "invalid")
    with TestClient(create_app()) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.parametrize("mode", ["gpt_only", "jev_then_gpt"])
def test_analyze_returns_common_result(example_payload, mock_api, monkeypatch, mode):
    monkeypatch.setenv("ANALYSIS_MODE", mode)
    app, llm, jev = mock_api
    reporter = app.dependency_overrides[get_report_generator]()
    with TestClient(app) as client:
        response = client.post("/analyze", json=example_payload)
    assert response.status_code == 200
    assert response.json() == {**llm.analyze.return_value.model_dump(mode="json"), "approach": mode}
    active = llm if mode == "gpt_only" else jev
    inactive = jev if mode == "gpt_only" else llm
    active.analyze.assert_awaited_once()
    inactive.analyze.assert_not_awaited()
    assert active.analyze.call_args.args[0].model_dump(mode="json", by_alias=True) == example_payload
    if mode == "jev_then_gpt":
        reporter.generate.assert_awaited_once_with(jev.analyze.return_value)
    else:
        reporter.generate.assert_not_awaited()


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
        ("ANALYSIS_MODE", "invalid"),
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
def test_failed_analysis_returns_error_without_fallback(
    example_payload, mock_api, monkeypatch, failed_name, error, status, code,
):
    monkeypatch.setenv("ANALYSIS_MODE", "gpt_only" if failed_name == "llm" else "jev_then_gpt")
    app, llm, jev = mock_api
    active, inactive = (llm, jev) if failed_name == "llm" else (jev, llm)
    active.analyze.side_effect = error("secret-provider-details")
    with TestClient(app) as client:
        response = client.post("/analyze", json=example_payload)
    assert response.status_code == status
    assert response.json()["detail"]["code"] == code
    assert "secret-provider-details" not in response.text
    active.analyze.assert_awaited_once()
    inactive.analyze.assert_not_awaited()
    app.dependency_overrides[get_report_generator]().generate.assert_not_awaited()


@pytest.mark.parametrize("error, status, code", [
    (ProviderError, 502, "report_generation_error"),
    (StructuredOutputError, 502, "report_generation_error"),
    (RuntimeError, 502, "report_generation_error"),
    (AnalysisTimeoutError, 504, "report_generation_timeout"),
])
def test_report_failure_has_distinct_error_without_fallback(
    example_payload, mock_api, monkeypatch, error, status, code,
):
    monkeypatch.setenv("ANALYSIS_MODE", "jev_then_gpt")
    app, llm, jev = mock_api
    app.dependency_overrides[get_report_generator]().generate.side_effect = error("secret-report")
    with TestClient(app) as client:
        response = client.post("/analyze", json=example_payload)
    assert response.status_code == status
    assert response.json()["detail"]["code"] == code
    assert "secret-report" not in response.text
    jev.analyze.assert_awaited_once()
    llm.analyze.assert_not_awaited()


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

    monkeypatch.setenv("ANALYSIS_MODE", "gpt_only" if slow_name == "llm" else "jev_then_gpt")
    analyzer = SlowAnalyzer()
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "0.01")
    app = mock_api[0]
    dependency = get_analyzer if slow_name == "llm" else get_jev_analyzer
    app.dependency_overrides[dependency] = lambda: analyzer
    with TestClient(app) as client:
        response = client.post("/analyze", json=example_payload)
    assert response.status_code == 504
    assert response.json()["detail"]["code"] == "analysis_timeout"
    assert analyzer.cancelled


def test_openapi_exposes_common_result_and_bounded_probabilities() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/openapi.json")
    assert response.status_code == 200
    specification = response.json()
    schemas = specification["components"]["schemas"]
    assert "from" in schemas["EmailData"]["properties"]
    assert "from_" not in schemas["EmailData"]["properties"]
    probability = schemas["SecurityAnalysis"]["properties"]["phishing_probability"]
    assert probability["minimum"] == 0
    assert probability["maximum"] == 1
    assert set(schemas["FinalAnalysisResult"]["properties"]) == {"analysis", "report", "approach"}
    response_schema = specification["paths"]["/analyze"]["post"]["responses"]["200"]["content"]["application/json"]["schema"]
    assert response_schema["$ref"].endswith("/FinalAnalysisResult")
