import os

import pytest

from ousmane_llm.agent.autoagent_client import AutoAgentClient
from ousmane_llm.config import Settings


@pytest.mark.integration
@pytest.mark.skipif(
    os.getenv("RUN_OLLAMA_INTEGRATION") != "1",
    reason="Set RUN_OLLAMA_INTEGRATION=1 with Ollama/Qwen running",
)
def test_real_ollama_qwen_classification(normalized_email) -> None:
    result = AutoAgentClient(Settings.from_env()).classify(normalized_email)
    assert result.verdict in {"benign", "suspicious", "malicious"}
    assert 0 <= result.risk_score <= 100

