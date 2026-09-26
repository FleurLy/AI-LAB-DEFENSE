from __future__ import annotations

from ousmane_llm.agent import AutoAgentClient
from ousmane_llm.config import Settings
from ousmane_llm.services import EmailAnalyzer, ResultWriter
from ousmane_llm.services.security_tools import warm_security_tools


def build_runtime(settings: Settings | None = None) -> tuple[Settings, EmailAnalyzer, ResultWriter]:
    settings = settings or Settings.from_env()
    settings.validate()
    settings.ensure_directories()
    warm_security_tools()
    client = AutoAgentClient(settings)
    return settings, EmailAnalyzer(settings, client), ResultWriter(settings.results_dir)
