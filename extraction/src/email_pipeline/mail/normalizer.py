from __future__ import annotations

from datetime import datetime, timezone

from langdetect import DetectorFactory, LangDetectException, detect

from email_pipeline.schemas.email_schema import (
    Attachment,
    EmailData,
    MailboxAddress,
    NormalizedEmail,
    Routing,
)
from email_pipeline.security import (
    analyze_sender,
    build_content_signals,
    build_technical_signals,
    parse_authentication,
)
from email_pipeline.urls.extractor import collect_urls

from .parser import ParsedEmail


DetectorFactory.seed = 0


def detect_language(text: str) -> str | None:
    if len(text.strip()) < 20:
        return None
    try:
        return detect(text)
    except LangDetectException:
        return None


def normalize_email(
    internal_id: str,
    parsed: ParsedEmail,
    attachments: list[Attachment],
    source: str = "smtp",
    received_at: datetime | None = None,
) -> NormalizedEmail:
    received_at = received_at or datetime.now(timezone.utc)
    urls = collect_urls(
        parsed.body_text,
        parsed.body_html,
        attachments,
        body_text_derived_from_html=parsed.body_text_derived_from_html,
    )
    authentication = parse_authentication(
        parsed.authentication_results, parsed.received_spf
    )
    sender = analyze_sender(parsed.from_address, parsed.reply_to_address, parsed.return_path)
    aggregate_text = "\n".join(
        [parsed.subject, parsed.body_text, *(attachment.content_text for attachment in attachments)]
    )
    return NormalizedEmail(
        email=EmailData(
            internal_id=internal_id,
            **{
                "from": MailboxAddress(name=parsed.from_name, address=parsed.from_address),
            },
            reply_to=MailboxAddress(
                name=parsed.reply_to_name, address=parsed.reply_to_address
            ),
            to=parsed.to,
            cc=parsed.cc,
            subject=parsed.subject,
            body_text=parsed.body_text,
            body_html=parsed.body_html,
            language=detect_language(parsed.body_text),
            sent_at=parsed.sent_at,
            message_id=parsed.message_id,
        ),
        attachments=attachments,
        urls=urls,
        authentication=authentication,
        sender=sender,
        routing=Routing(
            source=source,
            received_at=received_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
            received_hops=len(parsed.received),
        ),
        content_signals=build_content_signals(aggregate_text, attachments, urls),
        technical_signals=build_technical_signals(
            authentication, sender, attachments, urls
        ),
    )
