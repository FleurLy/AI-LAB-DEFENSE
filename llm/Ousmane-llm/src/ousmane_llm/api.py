from __future__ import annotations

import asyncio
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import ValidationError

from ousmane_llm.agent.autoagent_client import AnalysisGenerationError
from ousmane_llm.config import Settings
from ousmane_llm.runtime import build_runtime
from ousmane_llm.services.analyzer import EmailAnalyzer


def create_app(
    settings: Settings | None = None,
    analyzer: EmailAnalyzer | None = None,
) -> FastAPI:
    if settings is None or analyzer is None:
        runtime_settings, runtime_analyzer, _ = build_runtime(settings)
        settings = settings or runtime_settings
        analyzer = analyzer or runtime_analyzer

    app = FastAPI(title="Ousmane LLM Email Security API", version="1.0")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/model")
    def model() -> dict[str, str]:
        return {
            "provider": settings.llm_provider,
            "model": settings.llm_model,
            "base_url": settings.llm_base_url,
        }

    @app.post("/analyze")
    async def analyze(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            result = await asyncio.to_thread(analyzer.analyze, payload)
            return result.model_dump(mode="json")
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail=exc.errors()) from exc
        except AnalysisGenerationError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=413, detail=str(exc)) from exc

    return app


app = create_app()

