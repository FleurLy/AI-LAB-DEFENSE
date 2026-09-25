from __future__ import annotations

import logging
from typing import Any, Protocol

from ousmane_llm.config import Settings
from ousmane_llm.schemas.input import NormalizedEmailInput
from ousmane_llm.schemas.output import EmailAnalysis
from ousmane_llm.services.context import prepare_payload


LOGGER = logging.getLogger(__name__)


class ClassifierClient(Protocol):
    def classify(self, email_payload: dict[str, Any]) -> EmailAnalysis: ...


class EmailAnalyzer:
    def __init__(self, settings: Settings, client: ClassifierClient):
        self.settings = settings
        self.client = client

    def analyze(self, payload: dict[str, Any]) -> EmailAnalysis:
        normalized = NormalizedEmailInput.model_validate(payload)
        LOGGER.info("Loading email JSON: %s", normalized.email.internal_id)
        LOGGER.info("Model: %s", self.settings.llm_model)
        LOGGER.info("Provider: %s", self.settings.llm_provider)
        prepared = prepare_payload(
            normalized.model_dump(mode="json"), self.settings.max_input_chars
        )
        if prepared.truncated:
            LOGGER.warning("Email content was truncated before model analysis")
        LOGGER.info("Sending analysis request")
        decision = self.client.classify(prepared.data)
        LOGGER.info("Verdict: %s", decision.verdict)
        LOGGER.info("Risk score: %d", decision.risk_score)
        return decision

