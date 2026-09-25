from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timezone
from email import policy
from email.message import Message
from email.parser import BytesParser
from email.utils import getaddresses, parsedate_to_datetime

from bs4 import BeautifulSoup


@dataclass(slots=True)
class RawAttachment:
    filename: str
    content_type: str
    payload: bytes


@dataclass(slots=True)
class ParsedEmail:
    from_name: str | None = None
    from_address: str | None = None
    reply_to_name: str | None = None
    reply_to_address: str | None = None
    to: list[str] = field(default_factory=list)
    cc: list[str] = field(default_factory=list)
    subject: str = ""
    sent_at: str | None = None
    message_id: str | None = None
    return_path: str | None = None
    received: list[str] = field(default_factory=list)
    authentication_results: list[str] = field(default_factory=list)
    received_spf: list[str] = field(default_factory=list)
    body_text: str = ""
    body_html: str = ""
    body_text_derived_from_html: bool = False
    attachments: list[RawAttachment] = field(default_factory=list)


def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for element in soup(["script", "style", "noscript"]):
        element.decompose()
    for anchor in soup.find_all("a", href=True):
        label = anchor.get_text(" ", strip=True)
        href = str(anchor.get("href", "")).strip()
        anchor.replace_with(f"{label} ({href})" if label and label != href else href)
    return "\n".join(
        line.strip() for line in soup.get_text("\n").splitlines() if line.strip()
    )


def _addresses(values: list[str]) -> list[str]:
    return [address for _, address in getaddresses(values) if address]


def _first_address(value: str | None) -> tuple[str | None, str | None]:
    if not value:
        return None, None
    parsed = getaddresses([value])
    if not parsed:
        return None, None
    name, address = parsed[0]
    return name or None, address or None


def _content(part: Message) -> str:
    try:
        value = part.get_content()
        if isinstance(value, str):
            return value
    except (LookupError, UnicodeError, ValueError):
        pass
    payload = part.get_payload(decode=True) or b""
    charset = part.get_content_charset() or "utf-8"
    try:
        return payload.decode(charset, errors="replace")
    except LookupError:
        return payload.decode("utf-8", errors="replace")


class MailParser:
    def parse(self, raw: bytes) -> ParsedEmail:
        message = BytesParser(policy=policy.default).parsebytes(raw)
        parsed = ParsedEmail()
        parsed.from_name, parsed.from_address = _first_address(message.get("From"))
        parsed.reply_to_name, parsed.reply_to_address = _first_address(
            message.get("Reply-To")
        )
        parsed.to = _addresses(message.get_all("To", []))
        parsed.cc = _addresses(message.get_all("Cc", []))
        parsed.subject = str(message.get("Subject", ""))
        parsed.message_id = str(message.get("Message-ID")) if message.get("Message-ID") else None
        _, parsed.return_path = _first_address(message.get("Return-Path"))
        parsed.received = [str(v) for v in message.get_all("Received", [])]
        parsed.authentication_results = [
            str(v) for v in message.get_all("Authentication-Results", [])
        ]
        parsed.received_spf = [str(v) for v in message.get_all("Received-SPF", [])]

        date_value = message.get("Date")
        if date_value:
            try:
                dt = parsedate_to_datetime(str(date_value))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                parsed.sent_at = dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
            except (TypeError, ValueError, OverflowError):
                parsed.sent_at = None

        text_parts: list[str] = []
        html_parts: list[str] = []
        parts = message.walk() if message.is_multipart() else [message]
        for part in parts:
            if part.is_multipart():
                continue
            disposition = part.get_content_disposition()
            filename = part.get_filename()
            content_type = part.get_content_type()
            if disposition == "attachment" or filename:
                payload = part.get_payload(decode=True) or b""
                parsed.attachments.append(
                    RawAttachment(
                        filename=filename or "attachment",
                        content_type=content_type,
                        payload=payload,
                    )
                )
            elif content_type == "text/plain":
                text_parts.append(_content(part))
            elif content_type == "text/html":
                html_parts.append(_content(part))

        parsed.body_html = "\n".join(filter(None, html_parts)).strip()
        parsed.body_text = "\n".join(filter(None, text_parts)).strip()
        if not parsed.body_text and parsed.body_html:
            parsed.body_text = html_to_text(parsed.body_html)
            parsed.body_text_derived_from_html = True
        return parsed
