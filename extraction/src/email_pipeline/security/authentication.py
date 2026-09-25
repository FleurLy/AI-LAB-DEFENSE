from __future__ import annotations

import re

from email_pipeline.schemas.email_schema import Authentication


VALID_RESULTS = {
    "pass", "fail", "softfail", "neutral", "none", "temperror", "permerror", "unknown"
}


def _find_result(headers: list[str], mechanism: str) -> str:
    pattern = re.compile(rf"(?:^|[;\s]){re.escape(mechanism)}\s*=\s*([a-z]+)", re.IGNORECASE)
    for header in headers:
        match = pattern.search(header)
        if match:
            value = match.group(1).lower()
            return value if value in VALID_RESULTS else "unknown"
    return "unknown"


def parse_authentication(
    authentication_results: list[str], received_spf: list[str]
) -> Authentication:
    spf = _find_result(authentication_results, "spf")
    if spf == "unknown":
        for header in received_spf:
            first = header.strip().split(maxsplit=1)[0].lower() if header.strip() else ""
            if first in VALID_RESULTS:
                spf = first
                break
    return Authentication(
        spf=spf,
        dkim=_find_result(authentication_results, "dkim"),
        dmarc=_find_result(authentication_results, "dmarc"),
    )

