from ousmane_llm.services.context import TRUNCATION_MARKER, prepare_payload


def test_truncation_preserves_technical_fields(clone_email) -> None:
    payload = clone_email()
    payload["email"]["body_text"] = "A" * 20_000
    payload["email"]["body_html"] = "B" * 20_000
    prepared = prepare_payload(payload, 6_000)
    assert prepared.truncated
    assert prepared.data["authentication"] == payload["authentication"]
    assert prepared.data["technical_signals"] == payload["technical_signals"]
    assert TRUNCATION_MARKER.strip() in prepared.data["email"]["body_text"]

