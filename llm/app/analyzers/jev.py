from typing import Literal

from langchain_core.language_models.chat_models import BaseChatModel

from app.analyzers.llm import LLMEmailAnalyzer
from app.prompts.jev_analysis import build_jev_analysis_messages


class JevEmailAnalyzer(LLMEmailAnalyzer):
    """Analyze email with the JEV_MODEL chat model and a dedicated prompt."""

    def __init__(
        self,
        model: BaseChatModel,
        *,
        structured_output_method: Literal["json_schema", "function_calling"] = "json_schema",
    ) -> None:
        # Reuse async execution, structured validation and sanitized error handling.
        super().__init__(
            model,
            structured_output_method=structured_output_method,
            message_builder=build_jev_analysis_messages,
        )
