from langchain_core.language_models.chat_models import BaseChatModel

from app.analyzers.llm import invoke_structured_output
from app.models.analysis import GPTFullAnalysis
from app.models.email import EmailAnalysisRequest
from app.prompts.gpt_analysis import build_gpt_analysis_messages


class GPTEmailAnalyzer:
    """Make the decision and write its report in one structured model call."""

    def __init__(self, model: BaseChatModel) -> None:
        self._structured_model = model.with_structured_output(
            GPTFullAnalysis, method="json_schema", strict=True
        )

    async def analyze(self, payload: EmailAnalysisRequest) -> GPTFullAnalysis:
        return await invoke_structured_output(
            self._structured_model, build_gpt_analysis_messages(payload), GPTFullAnalysis
        )
