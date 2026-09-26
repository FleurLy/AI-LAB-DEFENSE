import asyncio

from app.analyzers.base import EmailAnalyzer
from app.core.errors import AnalysisTimeoutError
from app.models.analysis import AIAnalysisResult
from app.models.email import EmailAnalysisRequest


class AnalysisService:
    def __init__(self, analyzer: EmailAnalyzer, timeout_seconds: float = 30) -> None:
        self._analyzer = analyzer
        self._timeout_seconds = timeout_seconds

    async def analyze(self, payload: EmailAnalysisRequest) -> AIAnalysisResult:
        try:
            # Bound the whole operation, including any provider-side retries.
            async with asyncio.timeout(self._timeout_seconds):
                return await self._analyzer.analyze(payload)
        except TimeoutError as exc:
            raise AnalysisTimeoutError() from exc
