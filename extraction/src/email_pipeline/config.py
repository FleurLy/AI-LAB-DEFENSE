from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


def _as_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True, slots=True)
class Settings:
    smtp_host: str = "0.0.0.0"
    smtp_port: int = 1025
    data_dir: Path = Path("data")
    min_pdf_text_length: int = 30
    max_attachment_size_bytes: int = 25 * 1024 * 1024
    max_email_size_bytes: int = 50 * 1024 * 1024
    extractor_timeout_seconds: float = 30.0
    keep_work_files: bool = False
    log_level: str = "INFO"
    ocr_lang: str = "eng+fra"

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        return cls(
            smtp_host=os.getenv("SMTP_HOST", "0.0.0.0"),
            smtp_port=int(os.getenv("SMTP_PORT", "1025")),
            data_dir=Path(os.getenv("DATA_DIR", "data")),
            min_pdf_text_length=int(os.getenv("MIN_PDF_TEXT_LENGTH", "30")),
            max_attachment_size_bytes=int(
                os.getenv("MAX_ATTACHMENT_SIZE_BYTES", str(25 * 1024 * 1024))
            ),
            max_email_size_bytes=int(
                os.getenv("MAX_EMAIL_SIZE_BYTES", str(50 * 1024 * 1024))
            ),
            extractor_timeout_seconds=float(
                os.getenv("EXTRACTOR_TIMEOUT_SECONDS", "30")
            ),
            keep_work_files=_as_bool(os.getenv("KEEP_WORK_FILES"), False),
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
            ocr_lang=os.getenv("OCR_LANG", "eng+fra"),
        )

    def ensure_directories(self) -> None:
        for name in ("raw", "attachments", "work", "normalized"):
            (self.data_dir / name).mkdir(parents=True, exist_ok=True)

