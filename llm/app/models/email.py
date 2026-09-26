from typing import Annotated

from pydantic import (
    AfterValidator,
    AnyUrl,
    AwareDatetime,
    EmailStr,
    Field,
    StrictBool,
    TypeAdapter,
)

from app.models.base import APIModel

NonNegativeCount = Annotated[int, Field(ge=0, strict=True)]
_url_adapter = TypeAdapter(AnyUrl)


def validate_url(value: str) -> str:
    # Validate syntax without normalizing suspicious URLs before analysis.
    _url_adapter.validate_python(value)
    return value


URLString = Annotated[str, AfterValidator(validate_url)]


class EmailAddress(APIModel):
    name: str | None
    address: EmailStr


class EmailData(APIModel):
    from_: EmailAddress = Field(alias="from")
    reply_to: EmailStr | None
    to: list[EmailStr]
    cc: list[EmailStr]
    subject: str
    body_text: str
    language: str | None
    sent_at: AwareDatetime
    message_id: str


class ExtractionInfo(APIModel):
    method: str
    success: StrictBool


class AttachmentSecurity(APIModel):
    extension_mime_mismatch: StrictBool
    encrypted: StrictBool
    contains_macro: StrictBool
    contains_executable: StrictBool


class Attachment(APIModel):
    name: str
    mime_type: str
    size_bytes: NonNegativeCount
    # Keep the supplied value: the example contains abbreviated hashes.
    sha256: str
    content_text: str | None
    visual_description: str | None
    extraction: ExtractionInfo
    urls: list[URLString]
    qr_codes: list[URLString]
    security: AttachmentSecurity


class UrlInfo(APIModel):
    source: str
    display_text: str | None
    url: URLString
    domain: str
    uses_ip_address: StrictBool
    uses_punycode: StrictBool
    is_shortened: StrictBool
    display_domain_mismatch: StrictBool


class Authentication(APIModel):
    # Retain upstream result vocabulary, including vendor-specific statuses.
    spf: str
    dkim: str
    dmarc: str


class SenderInfo(APIModel):
    from_domain: str
    reply_to_domain: str | None
    return_path: str | None
    return_path_domain: str | None
    from_reply_to_mismatch: StrictBool
    from_return_path_mismatch: StrictBool


class RoutingInfo(APIModel):
    source: str
    received_at: AwareDatetime
    received_hops: NonNegativeCount


class ContentSignals(APIModel):
    contains_credential_request: StrictBool
    contains_payment_request: StrictBool
    contains_urgent_language: StrictBool
    contains_threat_language: StrictBool
    contains_secrecy_request: StrictBool
    contains_personal_data_request: StrictBool
    contains_external_link: StrictBool
    contains_attachment: StrictBool
    contains_qr_code: StrictBool


class TechnicalSignals(APIModel):
    spf_failed: StrictBool
    dkim_failed: StrictBool
    dmarc_failed: StrictBool
    reply_to_mismatch: StrictBool
    return_path_mismatch: StrictBool
    url_count: NonNegativeCount
    suspicious_url_count: NonNegativeCount
    attachment_count: NonNegativeCount
    executable_attachment_count: NonNegativeCount
    encrypted_attachment_count: NonNegativeCount
    qr_code_count: NonNegativeCount


class EmailAnalysisRequest(APIModel):
    schema_version: str
    email: EmailData
    attachments: list[Attachment]
    urls: list[UrlInfo]
    authentication: Authentication
    sender: SenderInfo
    routing: RoutingInfo
    content_signals: ContentSignals
    technical_signals: TechnicalSignals
