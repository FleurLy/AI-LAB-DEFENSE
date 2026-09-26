from langchain_core.language_models.chat_models import BaseChatModel

from app.analyzers.llm import invoke_structured_output
from app.models.analysis import SecurityAnalysis, SecurityReport
from app.prompts.security_report import build_report_messages


class GPTReportGenerator:
    """Explain a completed decision; the original email is never an input."""

    def __init__(self, model: BaseChatModel) -> None:
        self._structured_model = model.with_structured_output(
            SecurityReport, method="json_schema", strict=True
        )

    async def generate(self, analysis: SecurityAnalysis) -> SecurityReport:
        return await invoke_structured_output(
            self._structured_model, build_report_messages(analysis), SecurityReport
        )
