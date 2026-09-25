import json
import smtplib
import socket
from email.message import EmailMessage

from email_pipeline.config import Settings
from email_pipeline.pipeline import EmailPipeline
from email_pipeline.smtp.server import create_controller


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def test_email_travels_through_real_smtp_and_creates_one_json(tmp_path) -> None:
    port = free_port()
    settings = Settings(data_dir=tmp_path, smtp_host="127.0.0.1", smtp_port=port)
    pipeline = EmailPipeline(settings)
    controller = create_controller(pipeline, settings.smtp_host, settings.smtp_port)
    controller.start()
    try:
        message = EmailMessage()
        message["From"] = "security@example.org"
        message["Reply-To"] = "help@external.example"
        message["To"] = "user@company.test"
        message["Subject"] = "Urgent password verification"
        message.set_content("Verify your password immediately at https://192.0.2.1/login")
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=5) as smtp:
            smtp.send_message(message)
    finally:
        controller.stop()

    raw_files = list((tmp_path / "raw").glob("*.eml"))
    json_files = list((tmp_path / "normalized").glob("*.json"))
    assert len(raw_files) == 1
    assert len(json_files) == 1
    payload = json.loads(json_files[0].read_text(encoding="utf-8"))
    assert payload["email"]["internal_id"] == "mail_000001"
    assert payload["sender"]["from_reply_to_mismatch"] is True
    assert payload["technical_signals"]["url_count"] == 1
    assert "risk_score" not in payload

