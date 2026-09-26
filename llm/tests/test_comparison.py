import asyncio
import json
from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from langchain_openai import ChatOpenAI

from app.analyzers.base import EmailAnalyzer
from app.main import create_app
from app.models.analysis import AIAnalysisResult
from app.models.email import EmailAnalysisRequest
from app.prompts.email_analysis import SYSTEM_PROMPT
from app.prompts.jev_analysis import JEV_SYSTEM_PROMPT
from app.services.comparison_service import ComparisonService


def test_comparison_is_concurrent_and_keeps_payloads_independent(
    example_payload: dict[str, Any], analysis_result: AIAnalysisResult
) -> None:
    payload = EmailAnalysisRequest.model_validate(example_payload)
    jev_result = AIAnalysisResult.model_validate({
        **analysis_result.model_dump(), "phishing_probability": 0.2,
    })

    async def run() -> None:
        started = {name: asyncio.Event() for name in ("llm", "jev")}
        jev_finished = asyncio.Event()
        received = {}

        class PairedAnalyzer:
            def __init__(self, name: str, result: AIAnalysisResult) -> None:
                self.name = name
                self.result = result

            async def analyze(self, request: EmailAnalysisRequest) -> AIAnalysisResult:
                received[self.name] = request.model_dump(mode="json", by_alias=True)
                started[self.name].set()
                other_name = "jev" if self.name == "llm" else "llm"
                # A sequential implementation deadlocks here and fails the timeout below.
                await started[other_name].wait()
                request.email.body_text = self.name
                await asyncio.sleep(0)
                assert request.email.body_text == self.name
                if self.name == "llm":
                    await jev_finished.wait()
                else:
                    jev_finished.set()
                return self.result

        service = ComparisonService(
            PairedAnalyzer("llm", analysis_result), PairedAnalyzer("jev", jev_result),
            llm_model="provider/first", jev_model="provider/second",
        )
        comparison = await asyncio.wait_for(service.analyze(payload), timeout=1)
        assert comparison.llm.status == "success"
        assert comparison.jev.status == "success"
        assert comparison.llm.result == analysis_result
        assert comparison.jev.result == jev_result
        assert comparison.llm.model == "provider/first"
        assert comparison.jev.model == "provider/second"
        assert received == {"llm": example_payload, "jev": example_payload}
        assert payload.model_dump(mode="json", by_alias=True) == example_payload

    asyncio.run(run())


def test_comparison_cancellation_cancels_both_calls(
    example_payload: dict[str, Any],
) -> None:
    async def run() -> None:
        all_started = asyncio.Event()
        started = set()
        cancelled = set()

        class WaitingAnalyzer:
            def __init__(self, name: str) -> None:
                self.name = name

            async def analyze(self, payload: EmailAnalysisRequest) -> AIAnalysisResult:
                started.add(self.name)
                if len(started) == 2:
                    all_started.set()
                try:
                    await asyncio.Event().wait()
                except asyncio.CancelledError:
                    cancelled.add(self.name)
                    raise
                raise AssertionError("Expected cancellation")

        service = ComparisonService(
            WaitingAnalyzer("llm"), WaitingAnalyzer("jev"),
            llm_model="provider/first", jev_model="provider/second",
        )
        task = asyncio.create_task(service.analyze(
            EmailAnalysisRequest.model_validate(example_payload)
        ))
        try:
            await asyncio.wait_for(all_started.wait(), timeout=1)
        finally:
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        assert cancelled == {"llm", "jev"}

    asyncio.run(run())


def test_invalid_analyzer_result_preserves_valid_result(
    example_payload: dict[str, Any], analysis_result: AIAnalysisResult
) -> None:
    llm = AsyncMock(spec=EmailAnalyzer)
    jev = AsyncMock(spec=EmailAnalyzer)
    llm.analyze.return_value = {"phishing_probability": 4}
    jev.analyze.return_value = analysis_result
    service = ComparisonService(
        llm, jev, llm_model="provider/first", jev_model="provider/second",
    )
    result = asyncio.run(service.analyze(EmailAnalysisRequest.model_validate(example_payload)))
    assert result.llm.status == "error"
    assert result.llm.error.code == "structured_output_error"
    assert result.jev.status == "success"
    assert result.jev.result == analysis_result


@pytest.mark.parametrize("mode", ["jev_then_gpt"])
def test_api_pipeline_with_real_langchain_and_mock_http(
    example_payload, full_analysis, security_analysis, security_report, monkeypatch, mode,
):
    from app.prompts.security_report import GPT_REPORT_PROMPT

    monkeypatch.setenv("ANALYSIS_MODE", mode)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter-key")
    monkeypatch.setenv("LLM_MODEL", "openai/gpt-4o-mini")
    monkeypatch.setenv("JEV_MODEL", "test-provider/jev-model")
    monkeypatch.setenv("REPORT_MODEL", "test-provider/report-model")
    expected = [
        ("test-provider/jev-model", JEV_SYSTEM_PROMPT, example_payload, security_analysis),
        ("test-provider/report-model", GPT_REPORT_PROMPT, security_analysis.model_dump(mode="json"), security_report),
    ]
    calls = []

    def handler(request):
        assert str(request.url) == "https://openrouter.ai/api/v1/chat/completions"
        assert request.headers["Authorization"] == "Bearer test-openrouter-key"
        body = json.loads(request.content)
        model, prompt, human, result = expected[len(calls)]
        calls.append(body)
        assert body["model"] == model
        assert body["messages"][0]["content"] == prompt
        assert json.loads(body["messages"][1]["content"]) == human
        schema = body["response_format"]["json_schema"]
        assert schema["strict"] is True
        assert set(schema["schema"]["properties"]) == set(type(result).model_fields)
        return httpx.Response(200, json={
            "id": "chatcmpl-test", "object": "chat.completion", "created": 1,
            "model": model,
            "choices": [{"index": 0, "finish_reason": "stop", "message": {
                "role": "assistant", "content": result.model_dump_json(),
            }}],
        })

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as provider_client:
            with patch("app.analyzers.providers.ChatOpenAI", side_effect=lambda **kwargs: (
                ChatOpenAI(**kwargs, http_async_client=provider_client)
            )):
                async with httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=create_app()), base_url="http://testserver",
                ) as client:
                    return await client.post("/analyze", json=example_payload)

    response = asyncio.run(run())
    assert response.status_code == 200
    assert len(calls) == len(expected)
    assert response.json() == {**full_analysis.model_dump(mode="json"), "approach": mode}
