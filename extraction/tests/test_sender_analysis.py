from email_pipeline.security.authentication import parse_authentication
from email_pipeline.security.sender import analyze_sender


def test_sender_domain_mismatches() -> None:
    sender = analyze_sender(
        "Security <security@example.org>",
        "support@other.example",
        "bounce@example.org",
    )

    assert sender.from_reply_to_mismatch is True
    assert sender.from_return_path_mismatch is False


def test_authentication_results_are_extracted() -> None:
    authentication = parse_authentication(
        ["mx.test; spf=fail smtp.mailfrom=x; dkim=pass; dmarc=softfail"], []
    )

    assert authentication.spf == "fail"
    assert authentication.dkim == "pass"
    assert authentication.dmarc == "softfail"


def test_missing_authentication_is_unknown() -> None:
    authentication = parse_authentication([], [])
    assert authentication.spf == authentication.dkim == authentication.dmarc == "unknown"

