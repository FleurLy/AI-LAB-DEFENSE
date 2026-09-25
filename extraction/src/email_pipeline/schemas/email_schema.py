from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MailboxAddress(StrictModel):
    name: str | None = None
    address: str | None = None


class EmailData(StrictModel):
    internal_id: str
    from_: MailboxAddress = Field(alias="from", serialization_alias="from")
    reply_to: MailboxAddress
    to: list[str]
    cc: list[str]
    subject: str
    body_text: str
    body_html: str
    language: str | None
    sent_at: str | None
    message_id: str | None


class ExtractionResult(StrictModel):
    method: Literal["text", "ocr", "office", "unsupported", "none", "error"]
    success: bool
    error: str | None = None


class AttachmentSecurity(StrictModel):
    extension_mime_mismatch: bool
    encrypted: bool
    contains_macro: bool
    contains_executable: bool


class Attachment(StrictModel):
    name: str
    mime_type_declared: str | None
    mime_type_detected: str | None
    size_bytes: int
    sha256: str
    content_text: str
    visual_description: str | None = None
    extraction: ExtractionResult
    urls: list[str]
    qr_codes: list[str]
    security: AttachmentSecurity


class URLFinding(StrictModel):
    source: str
    display_text: str | None
    url: str
    domain: str | None
    scheme: str | None
    uses_ip_address: bool
    uses_punycode: bool
    is_shortened: bool
    display_domain_mismatch: bool | None


AuthResult = Literal[
    "pass", "fail", "softfail", "neutral", "none", "temperror", "permerror", "unknown"
]


class Authentication(StrictModel):
    spf: AuthResult = "unknown"
    dkim: AuthResult = "unknown"
    dmarc: AuthResult = "unknown"


class Sender(StrictModel):
    from_domain: str | None
    reply_to_domain: str | None
    return_path: str | None
    return_path_domain: str | None
    from_reply_to_mismatch: bool
    from_return_path_mismatch: bool


class Routing(StrictModel):
    source: Literal["smtp", "gmail", "imap"]
    received_at: str
    received_hops: int


class ContentSignals(StrictModel):
    contains_credential_request: bool
    contains_payment_request: bool
    contains_urgent_language: bool
    contains_threat_language: bool
    contains_secrecy_request: bool
    contains_personal_data_request: bool
    contains_external_link: bool
    contains_attachment: bool
    contains_qr_code: bool


class TechnicalSignals(StrictModel):
    spf_failed: bool
    dkim_failed: bool
    dmarc_failed: bool
    reply_to_mismatch: bool
    return_path_mismatch: bool
    url_count: int
    suspicious_url_count: int
    attachment_count: int
    executable_attachment_count: int
    encrypted_attachment_count: int
    qr_code_count: int


class NormalizedEmail(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    email: EmailData
    attachments: list[Attachment]
    urls: list[URLFinding]
    authentication: Authentication
    sender: Sender
    routing: Routing
    content_signals: ContentSignals
    technical_signals: TechnicalSignals

