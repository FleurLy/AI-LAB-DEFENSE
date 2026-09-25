from __future__ import annotations

import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from email_pipeline.schemas.email_schema import Attachment, URLFinding

from .analyzer import analyze_url


URL_PATTERN = re.compile(r"\b(?:https?|ftp)://[^\s<>\[\]{}\"']+", re.IGNORECASE)
TRAILING_PUNCTUATION = ".,;:!?)]}"


def extract_text_urls(text: str) -> list[str]:
    values: list[str] = []
    for match in URL_PATTERN.finditer(text or ""):
        value = match.group(0).rstrip(TRAILING_PUNCTUATION)
        if value and value not in values:
            values.append(value)
    return values


def collect_urls(
    body_text: str,
    body_html: str,
    attachments: list[Attachment],
    body_text_derived_from_html: bool = False,
) -> list[URLFinding]:
    findings: list[URLFinding] = []
    seen: set[tuple[str, str]] = set()

    def add(url: str, source: str, display: str | None = None) -> None:
        key = (source, url)
        if key not in seen:
            findings.append(analyze_url(url, source, display))
            seen.add(key)

    if not body_text_derived_from_html:
        for url in extract_text_urls(body_text):
            add(url, "email_body")

    if body_html:
        soup = BeautifulSoup(body_html, "html.parser")
        for anchor in soup.find_all("a", href=True):
            href = str(anchor.get("href", "")).strip()
            if urlparse(href).scheme.lower() in {"http", "https", "ftp"}:
                add(href, "email_html", anchor.get_text(" ", strip=True) or None)
        # Anchor labels can themselves look like URLs but are not destinations.
        # Remove anchors before scanning visible, non-link text for bare URLs.
        for anchor in soup.find_all("a"):
            anchor.decompose()
        for url in extract_text_urls(soup.get_text(" ")):
            add(url, "email_html")

    for attachment in attachments:
        for url in attachment.urls:
            add(url, f"attachment:{attachment.name}")
        for value in attachment.qr_codes:
            if urlparse(value).scheme.lower() in {"http", "https", "ftp"}:
                add(value, f"qr_code:{attachment.name}")
    return findings
