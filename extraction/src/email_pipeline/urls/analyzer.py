from __future__ import annotations

import ipaddress
from urllib.parse import urlparse

from email_pipeline.schemas.email_schema import URLFinding


SHORTENER_DOMAINS = {
    "bit.ly", "buff.ly", "cutt.ly", "goo.gl", "is.gd", "ow.ly", "rebrand.ly",
    "shorturl.at", "t.co", "tiny.cc", "tinyurl.com",
}


def _domain_from_display(display_text: str | None) -> str | None:
    if not display_text:
        return None
    candidate = display_text.strip()
    if not candidate.lower().startswith(("http://", "https://")):
        return None
    return (urlparse(candidate).hostname or "").lower() or None


def analyze_url(url: str, source: str, display_text: str | None = None) -> URLFinding:
    parsed = urlparse(url)
    domain = (parsed.hostname or "").lower() or None
    uses_ip = False
    if domain:
        try:
            ipaddress.ip_address(domain.strip("[]"))
            uses_ip = True
        except ValueError:
            pass
    displayed_domain = _domain_from_display(display_text)
    mismatch = None if displayed_domain is None or domain is None else displayed_domain != domain
    return URLFinding(
        source=source,
        display_text=display_text,
        url=url,
        domain=domain,
        scheme=parsed.scheme.lower() or None,
        uses_ip_address=uses_ip,
        uses_punycode=bool(domain and any(label.startswith("xn--") for label in domain.split("."))),
        is_shortened=bool(domain and domain in SHORTENER_DOMAINS),
        display_domain_mismatch=mismatch,
    )


def is_suspicious(finding: URLFinding) -> bool:
    return any(
        (
            finding.uses_ip_address,
            finding.uses_punycode,
            finding.is_shortened,
            finding.display_domain_mismatch is True,
            finding.scheme not in {"http", "https"},
        )
    )

