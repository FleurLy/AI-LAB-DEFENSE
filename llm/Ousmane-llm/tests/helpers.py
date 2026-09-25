from __future__ import annotations

from ousmane_llm.schemas.output import EmailAnalysis


def decision(
    verdict: str = "benign",
    category: str = "legitimate",
    score: int = 8,
    action: str = "allow",
) -> EmailAnalysis:
    return EmailAnalysis.model_validate(
        {
            "schema_version": "1.0",
            "risk_score": score,
            "confidence": 0.9,
            "verdict": verdict,
            "category": category,
            "summary": "Evidence-based email security classification.",
            "explanation": "The available sender, authentication, and content evidence supports this classification.",
            "reasons": [{"type": "context", "description": "The normalized evidence was evaluated."}],
            "recommended_action": action,
        }
    )


class FakeClient:
    def __init__(self, result: EmailAnalysis):
        self.result = result
        self.payload = None

    def classify(self, payload):
        self.payload = payload
        return self.result

