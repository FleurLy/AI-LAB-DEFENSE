from email_pipeline.urls.analyzer import analyze_url, is_suspicious
from email_pipeline.urls.extractor import collect_urls, extract_text_urls


def test_extract_urls_strips_sentence_punctuation() -> None:
    assert extract_text_urls("Open https://example.org/login, then continue.") == [
        "https://example.org/login"
    ]


def test_html_display_domain_mismatch_is_detected() -> None:
    findings = collect_urls(
        "",
        '<a href="https://evil.example/login">https://bank.example/login</a>',
        [],
    )

    assert len(findings) == 1
    assert findings[0].display_domain_mismatch is True
    assert is_suspicious(findings[0])


def test_ip_and_punycode_are_suspicious() -> None:
    ip_url = analyze_url("https://192.0.2.1/login", "email_body")
    punycode_url = analyze_url("https://xn--exmple-cua.test", "email_body")
    assert ip_url.uses_ip_address
    assert punycode_url.uses_punycode

