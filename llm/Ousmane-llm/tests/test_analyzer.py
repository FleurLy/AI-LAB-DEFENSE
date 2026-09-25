from ousmane_llm.config import Settings
from ousmane_llm.services.analyzer import EmailAnalyzer
from tests.helpers import FakeClient, decision


def analyzer_for(result):
    client = FakeClient(result)
    return EmailAnalyzer(Settings(max_input_chars=10_000), client), client


def test_benign_email(normalized_email) -> None:
    analyzer, _ = analyzer_for(decision())
    assert analyzer.analyze(normalized_email).verdict == "benign"


def test_obvious_phishing(clone_email) -> None:
    payload = clone_email()
    payload["content_signals"]["contains_credential_request"] = True
    payload["technical_signals"]["suspicious_url_count"] = 1
    analyzer, client = analyzer_for(
        decision("malicious", "credential_phishing", 95, "quarantine")
    )
    assert analyzer.analyze(payload).category == "credential_phishing"
    assert client.payload["content_signals"]["contains_credential_request"] is True


def test_bec_with_valid_authentication(clone_email) -> None:
    payload = clone_email()
    payload["email"]["body_text"] = "Buy gift cards urgently and do not contact anyone."
    analyzer, _ = analyzer_for(decision("malicious", "bec", 91, "quarantine"))
    result = analyzer.analyze(payload)
    assert result.category == "bec"
    assert payload["authentication"]["dmarc"] == "pass"


def test_spf_failure_can_still_require_human_review(clone_email) -> None:
    payload = clone_email()
    payload["authentication"]["spf"] = "fail"
    analyzer, _ = analyzer_for(decision("suspicious", "unknown", 45, "human_review"))
    assert analyzer.analyze(payload).verdict == "suspicious"

