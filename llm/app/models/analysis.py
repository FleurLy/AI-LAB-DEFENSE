from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field

from app.models.base import APIModel

Probability = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False, strict=True)]
AnalysisMode = Literal["jev_then_gpt"]


class RequestedAction(StrEnum):
    NONE = "none"
    CLICK_LINK = "click_link"
    PROVIDE_CREDENTIALS = "provide_credentials"
    MAKE_PAYMENT = "make_payment"
    CHANGE_BANK_DETAILS = "change_bank_details"
    DOWNLOAD_FILE = "download_file"
    EXECUTE_FILE = "execute_file"
    PROVIDE_PERSONAL_DATA = "provide_personal_data"
    PROVIDE_SENSITIVE_INFORMATION = "provide_sensitive_information"
    OTHER = "other"


class AttackType(StrEnum):
    NONE = "none"
    PHISHING = "phishing"
    SPEAR_PHISHING = "spear_phishing"
    BUSINESS_EMAIL_COMPROMISE = "business_email_compromise"
    CREDENTIAL_THEFT = "credential_theft"
    PAYMENT_FRAUD = "payment_fraud"
    IMPERSONATION = "impersonation"
    MALWARE_DELIVERY = "malware_delivery"
    SOCIAL_ENGINEERING = "social_engineering"
    OTHER = "other"


class Severity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class EvidenceItem(APIModel):
    type: str = Field(description="Signal category, such as urgency or authentication.")
    description: str = Field(description="Explain observed facts separately from inference.")
    source: str = Field(description="Payload field path, e.g. email.subject or urls[0].url.")
    severity: Severity
    confidence: Probability


class SecurityAnalysis(APIModel):
    social_engineering_probability: Probability
    phishing_probability: Probability
    impersonation_probability: Probability
    urgency_probability: Probability
    authority_pressure_probability: Probability
    secrecy_probability: Probability
    credential_request_probability: Probability
    payment_request_probability: Probability
    personal_data_request_probability: Probability
    procedure_bypass_probability: Probability
    requested_action: RequestedAction
    attack_type: AttackType
    evidence: list[EvidenceItem]


class AIAnalysisResult(SecurityAnalysis):
    """Original result retained for the standalone analyzer/comparison utilities."""

    summary: str = Field(description="Concise explanation of the overall assessment.")
    recommended_action: str = Field(description="Concise defensive recommendation.")


class SecurityReport(APIModel):
    summary: str
    risk_explanation: str
    recommended_actions: list[str]


class GPTFullAnalysis(APIModel):
    analysis: SecurityAnalysis
    report: SecurityReport


class FinalAnalysisResult(GPTFullAnalysis):
    approach: AnalysisMode
