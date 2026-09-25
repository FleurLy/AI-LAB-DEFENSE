from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


Verdict = Literal["benign", "suspicious", "malicious"]
Category = Literal[
    "legitimate",
    "spam",
    "phishing",
    "credential_phishing",
    "spear_phishing",
    "bec",
    "invoice_fraud",
    "payment_fraud",
    "qr_phishing",
    "social_engineering",
    "malicious_attachment",
    "unknown",
]
Action = Literal["allow", "flag", "human_review", "quarantine"]
ReasonType = Literal["authentication", "sender", "content", "url", "attachment", "context", "technical"]


class Reason(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: ReasonType
    description: str = Field(min_length=3, max_length=300)


class EmailAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    risk_score: int = Field(ge=0, le=100)
    confidence: float = Field(default=0.9, ge=0.0, le=1.0)
    verdict: Verdict
    category: Category = "unknown"
    summary: str = Field(default="Security analysis", min_length=1, max_length=240)
    explanation: str = Field(min_length=5, max_length=1000)
    reasons: list[Reason] = Field(default_factory=list, max_length=8)
    recommended_action: Action = "allow"

    @model_validator(mode="before")
    @classmethod
    def populate_defaults(cls, data: Any) -> Any:
        if isinstance(data, dict):
            verdict = data.get("verdict")
            if not data.get("recommended_action") and verdict:
                data["recommended_action"] = {
                    "benign": "allow",
                    "suspicious": "human_review",
                    "malicious": "quarantine",
                }.get(verdict, "human_review")
            if not data.get("summary") and data.get("explanation"):
                data["summary"] = data["explanation"][:60]
            if not data.get("category") and verdict:
                data["category"] = "legitimate" if verdict == "benign" else "phishing"
        return data

    @model_validator(mode="after")
    def coherent_action(self) -> "EmailAnalysis":
        allowed = {
            "benign": {"allow", "flag"},
            "suspicious": {"flag", "human_review", "quarantine"},
            "malicious": {"human_review", "quarantine"},
        }
        if self.recommended_action not in allowed[self.verdict]:
            raise ValueError(
                f"Action {self.recommended_action!r} is inconsistent with verdict {self.verdict!r}"
            )
        return self

