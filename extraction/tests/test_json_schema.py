import json
from datetime import datetime, timezone
from email.message import EmailMessage

from email_pipeline.mail.normalizer import normalize_email
from email_pipeline.mail.parser import MailParser
from email_pipeline.schemas.email_schema import NormalizedEmail


def test_normalized_json_round_trips_and_has_no_verdict() -> None:
    message = EmailMessage()
    message["From"] = "sender@example.org"
    message["To"] = "reader@example.net"
    message["Subject"] = "Information"
    message.set_content("A regular message long enough for language detection.")
    parsed = MailParser().parse(message.as_bytes())

    normalized = normalize_email(
        "mail_000001", parsed, [], received_at=datetime(2026, 9, 25, tzinfo=timezone.utc)
    )
    payload = json.loads(normalized.model_dump_json(by_alias=True))
    validated = NormalizedEmail.model_validate(payload)

    assert payload["email"]["from"]["address"] == "sender@example.org"
    assert payload["schema_version"] == "1.0"
    assert "risk_score" not in payload
    assert "verdict" not in payload
    assert validated.email.internal_id == "mail_000001"


def test_html_only_url_is_not_double_counted() -> None:
    message = EmailMessage()
    message["From"] = "sender@example.org"
    message["To"] = "reader@example.net"
    message.set_content(
        '<p>Open this page</p><a href="https://example.org/login">Login</a>',
        subtype="html",
    )
    parsed = MailParser().parse(message.as_bytes())
    normalized = normalize_email("mail_000002", parsed, [])
    assert len(normalized.urls) == 1
    assert normalized.urls[0].source == "email_html"
