from __future__ import annotations

from email.utils import parseaddr

from email_pipeline.schemas.email_schema import Sender


def address_domain(address: str | None) -> str | None:
    if not address:
        return None
    parsed = parseaddr(address)[1]
    if "@" not in parsed:
        return None
    return parsed.rsplit("@", 1)[1].strip().lower().rstrip(".") or None


def analyze_sender(
    from_address: str | None, reply_to_address: str | None, return_path: str | None
) -> Sender:
    from_domain = address_domain(from_address)
    reply_domain = address_domain(reply_to_address)
    return_domain = address_domain(return_path)
    return Sender(
        from_domain=from_domain,
        reply_to_domain=reply_domain,
        return_path=return_path,
        return_path_domain=return_domain,
        from_reply_to_mismatch=bool(from_domain and reply_domain and from_domain != reply_domain),
        from_return_path_mismatch=bool(from_domain and return_domain and from_domain != return_domain),
    )

