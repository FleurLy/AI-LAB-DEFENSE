from typing import Protocol

from app.models.analysis import AIAnalysisResult
from app.models.email import EmailAnalysisRequest


class EmailAnalyzer(Protocol):
    async def analyze(self, payload: EmailAnalysisRequest) -> AIAnalysisResult: ...
