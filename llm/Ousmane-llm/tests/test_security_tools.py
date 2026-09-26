from __future__ import annotations

from ousmane_llm.services import security_tools


class RecordingModel:
    def __init__(self, probability: float = 0.25):
        self.probability = probability
        self.inputs: list[list[str]] = []

    def predict_proba(self, texts: list[str]):
        self.inputs.append(texts)
        return [[1.0 - self.probability, self.probability]]


def test_tools_consume_normalized_email_fields(monkeypatch, clone_email) -> None:
    payload = clone_email()
    payload["email"]["subject"] = "Urgent account verification"
    payload["email"]["body_text"] = "Open the portal and verify your password."
    payload["email"]["from"] = {"name": "PayPal", "address": "alerts@paypa1.com"}
    payload["email"]["reply_to"] = {"name": None, "address": "help@elsewhere.xyz"}
    payload["authentication"] = {"spf": "fail", "dkim": "pass", "dmarc": "fail"}

    model = RecordingModel(0.8)
    module = security_tools._load_tools_module()
    monkeypatch.setattr(module, "get_model", lambda: model)

    results = security_tools.analyze_with_security_tools(payload)

    assert model.inputs == [["Urgent account verification Open the portal and verify your password."]]
    assert results["check_contenu"]["score"] == 0.8
    assert "high_ml_confidence_phishing" in results["check_contenu"]["flags"]
    assert "reply_to_mismatch" in results["check_expediteur"]["flags"]
    assert "spf_failed" in results["check_expediteur"]["flags"]
    assert "dmarc_failed" in results["check_expediteur"]["flags"]


def test_tools_handle_structured_urls_and_attachments(monkeypatch, clone_email) -> None:
    payload = clone_email()
    payload["urls"] = [{
        "url": "https://192.0.2.10/login",
        "domain": "192.0.2.10",
        "uses_ip_address": True,
        "uses_punycode": False,
        "display_domain_mismatch": True,
    }]
    payload["attachments"] = [{
        "name": "invoice.pdf.exe",
        "security": {
            "extension_mime_mismatch": True,
            "encrypted": False,
            "contains_macro": False,
            "contains_executable": True,
        },
    }]

    module = security_tools._load_tools_module()
    monkeypatch.setattr(module, "get_model", lambda: RecordingModel())
    results = security_tools.analyze_with_security_tools(payload)

    assert "raw_ip_url:192.0.2.10" in results["check_domaine"]["flags"]
    assert "display_domain_mismatch:192.0.2.10" in results["check_domaine"]["flags"]
    attachment_flags = results["check_pieces_jointes"]["flags"]
    assert "dangerous_extension:invoice.pdf.exe" in attachment_flags
    assert "contains_executable:invoice.pdf.exe" in attachment_flags
    assert results["check_pieces_jointes"]["score"] == 1.0


def test_warm_security_tools_loads_model(monkeypatch) -> None:
    module = security_tools._load_tools_module()
    calls = []
    monkeypatch.setattr(module, "get_model", lambda: calls.append("loaded"))

    security_tools.warm_security_tools()

    assert calls == ["loaded"]
