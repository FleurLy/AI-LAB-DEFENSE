from __future__ import annotations

import copy

import pytest


@pytest.fixture
def normalized_email() -> dict:
    return {
        "schema_version": "1.0",
        "email": {
            "internal_id": "mail_000001",
            "from": {"name": "Alice", "address": "alice@example.org"},
            "reply_to": {"name": None, "address": None},
            "to": ["bob@example.net"],
            "cc": [],
            "subject": "Project update",
            "body_text": "The project meeting is scheduled for tomorrow.",
            "body_html": "",
            "language": "en",
            "sent_at": None,
            "message_id": "<1@example.org>",
        },
        "attachments": [],
        "urls": [],
        "authentication": {"spf": "pass", "dkim": "pass", "dmarc": "pass"},
        "sender": {
            "from_domain": "example.org",
            "reply_to_domain": None,
            "return_path": "alice@example.org",
            "return_path_domain": "example.org",
            "from_reply_to_mismatch": False,
            "from_return_path_mismatch": False,
        },
        "routing": {"source": "smtp", "received_at": "2026-09-25T10:00:00Z", "received_hops": 2},
        "content_signals": {
            "contains_credential_request": False,
            "contains_payment_request": False,
            "contains_urgent_language": False,
            "contains_threat_language": False,
            "contains_secrecy_request": False,
            "contains_personal_data_request": False,
            "contains_external_link": False,
            "contains_attachment": False,
            "contains_qr_code": False,
        },
        "technical_signals": {
            "spf_failed": False,
            "dkim_failed": False,
            "dmarc_failed": False,
            "reply_to_mismatch": False,
            "return_path_mismatch": False,
            "url_count": 0,
            "suspicious_url_count": 0,
            "attachment_count": 0,
            "executable_attachment_count": 0,
            "encrypted_attachment_count": 0,
            "qr_code_count": 0,
        },
    }


@pytest.fixture
def clone_email(normalized_email):
    return lambda: copy.deepcopy(normalized_email)

