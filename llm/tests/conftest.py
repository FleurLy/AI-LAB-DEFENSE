import json
from pathlib import Path
from typing import Any

import pytest

from app.api.dependencies import get_analyzer, get_jev_analyzer, get_report_generator
from app.core.config import get_settings
from app.models.analysis import AIAnalysisResult


@pytest.fixture(autouse=True)
def isolate_configuration(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    # Ignore both local .env files and credentials exported by the test runner.
    monkeypatch.chdir(tmp_path)
    for name in (
        "OPENROUTER_API_KEY",
        "OPENROUTER_SITE_URL",
        "OPENROUTER_APP_NAME",
        "OPENAI_API_KEY",
        "OPENAI_API_BASE",
        "OPENAI_BASE_URL",
        "OPENAI_ORG_ID",
        "OPENAI_ORGANIZATION",
        "OPENAI_PROJECT_ID",
        "ANALYSIS_MODE",
        "REPORT_MODEL",
        "LLM_PROVIDER",
        "LLM_MODEL",
        "JEV_MODEL",
        "LLM_TEMPERATURE",
        "LLM_TIMEOUT_SECONDS",
        "LANGCHAIN_TRACING_V2",
        "LANGCHAIN_API_KEY",
        "LANGSMITH_TRACING",
        "LANGSMITH_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")
    get_settings.cache_clear()
    get_analyzer.cache_clear()
    get_jev_analyzer.cache_clear()
    get_report_generator.cache_clear()
    yield
    get_analyzer.cache_clear()
    get_jev_analyzer.cache_clear()
    get_report_generator.cache_clear()
    get_settings.cache_clear()


@pytest.fixture
def example_payload() -> dict[str, Any]:
    path = Path(__file__).resolve().parents[1] / "examples" / "email_analysis.json"
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture
def analysis_result() -> AIAnalysisResult:
    return AIAnalysisResult(
        social_engineering_probability=0.92,
        phishing_probability=0.9,
        impersonation_probability=0.8,
        urgency_probability=0.95,
        authority_pressure_probability=0.7,
        secrecy_probability=0.1,
        credential_request_probability=0.9,
        payment_request_probability=0.1,
        personal_data_request_probability=0.2,
        procedure_bypass_probability=0.3,
        requested_action="provide_credentials",
        attack_type="phishing",
        evidence=[
            {
                "type": "urgency",
                "description": "The subject explicitly says URGENT.",
                "source": "email.subject",
                "severity": "high",
                "confidence": 0.99,
            }
        ],
        summary="The message combines urgency with suspicious sender metadata.",
        recommended_action="Verify the request through a known trusted channel.",
    )


@pytest.fixture
def security_analysis(analysis_result):
    from app.models.analysis import SecurityAnalysis
    return SecurityAnalysis.model_validate(analysis_result.model_dump(exclude={"summary", "recommended_action"}))


@pytest.fixture
def security_report():
    from app.models.analysis import SecurityReport
    return SecurityReport(summary="Suspicious request.", risk_explanation="Urgency and credential request.", recommended_actions=["Verify through a trusted channel."])


@pytest.fixture
def full_analysis(security_analysis, security_report):
    from app.models.analysis import GPTFullAnalysis
    return GPTFullAnalysis(analysis=security_analysis, report=security_report)
