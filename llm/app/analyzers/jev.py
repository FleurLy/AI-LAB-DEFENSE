from typing import Literal

from langchain_core.language_models.chat_models import BaseChatModel

from app.analyzers.llm import invoke_structured_output
from app.models.analysis import SecurityAnalysis
from app.models.email import EmailAnalysisRequest
from app.prompts.jev_analysis import build_jev_analysis_messages


class JevEmailAnalyzer:
    """Make the machine-facing security decision using JEV_MODEL."""

    def __init__(
        self,
        model: BaseChatModel,
        *,
        structured_output_method: Literal["json_schema", "function_calling"] = "json_schema",
    ) -> None:
        self._structured_model = model.with_structured_output(
            SecurityAnalysis, method=structured_output_method, strict=True
        )

    async def analyze(self, payload: EmailAnalysisRequest) -> SecurityAnalysis:
        return await invoke_structured_output(
            self._structured_model, build_jev_analysis_messages(payload), SecurityAnalysis
        )
