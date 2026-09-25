from email_pipeline.attachments.manager import AttachmentManager
from email_pipeline.config import Settings
from email_pipeline.mail.parser import RawAttachment


def test_unknown_attachment_does_not_crash(tmp_path) -> None:
    manager = AttachmentManager(Settings(data_dir=tmp_path))
    result = manager.process_all(
        "mail_000001",
        [RawAttachment(filename="unknown.xyz", content_type="application/octet-stream", payload=b"data")],
    )[0]

    assert result.extraction.success is False
    assert result.extraction.method == "unsupported"
    assert result.sha256


def test_path_traversal_filename_is_sanitized(tmp_path) -> None:
    manager = AttachmentManager(Settings(data_dir=tmp_path))
    result = manager.process_all(
        "mail_000001",
        [RawAttachment(filename="../../evil.txt", content_type="text/plain", payload=b"safe")],
    )[0]

    assert result.name == "evil.txt"
    assert (tmp_path / "attachments" / "mail_000001" / "evil.txt").read_bytes() == b"safe"


def test_oversized_attachment_is_reported_without_writing(tmp_path) -> None:
    settings = Settings(data_dir=tmp_path, max_attachment_size_bytes=3)
    result = AttachmentManager(settings).process_all(
        "mail_000001",
        [RawAttachment(filename="large.bin", content_type="application/octet-stream", payload=b"1234")],
    )[0]

    assert result.extraction.success is False
    assert "exceeds" in (result.extraction.error or "")
    assert not (tmp_path / "attachments" / "mail_000001" / "large.bin").exists()


def test_corrupt_pdf_is_reported_without_crashing(tmp_path) -> None:
    result = AttachmentManager(Settings(data_dir=tmp_path)).process_all(
        "mail_000001",
        [RawAttachment(filename="broken.pdf", content_type="application/pdf", payload=b"not a pdf")],
    )[0]
    assert result.extraction.success is False
    assert result.extraction.method == "error"
    assert result.extraction.error
