from typing import Protocol

from app.models.analysis import GPTFullAnalysis, SecurityAnalysis, SecurityReport
from app.models.email import EmailAnalysisRequest


class EmailAnalyzer(Protocol):
    async def analyze(self, payload: EmailAnalysisRequest) -> SecurityAnalysis: ...


class FullEmailAnalyzer(Protocol):
    async def analyze(self, payload: EmailAnalysisRequest) -> GPTFullAnalysis: ...


class ReportGenerator(Protocol):
    async def generate(self, analysis: SecurityAnalysis) -> SecurityReport: ...
