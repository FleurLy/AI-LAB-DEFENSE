from __future__ import annotations

import logging
import shutil
import threading
from datetime import datetime, timezone
from pathlib import Path

from email_pipeline.attachments import AttachmentManager
from email_pipeline.config import Settings
from email_pipeline.mail.normalizer import normalize_email
from email_pipeline.mail.parser import MailParser
from email_pipeline.schemas.email_schema import NormalizedEmail


LOGGER = logging.getLogger(__name__)


class EmailTooLargeError(ValueError):
    pass


class EmailPipeline:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.settings.ensure_directories()
        self.parser = MailParser()
        self.attachments = AttachmentManager(settings)
        self._id_lock = threading.Lock()
        self._last_id = self._discover_last_id()

    def _discover_last_id(self) -> int:
        indexes: list[int] = []
        for directory in ("raw", "normalized"):
            for path in (self.settings.data_dir / directory).glob("mail_*.*"):
                try:
                    indexes.append(int(path.stem.removeprefix("mail_")))
                except ValueError:
                    continue
        return max(indexes, default=0)

    def _next_id(self) -> str:
        with self._id_lock:
            self._last_id += 1
            return f"mail_{self._last_id:06d}"

    def process_raw(
        self,
        raw: bytes,
        source: str = "smtp",
        received_at: datetime | None = None,
    ) -> tuple[NormalizedEmail, Path]:
        if len(raw) > self.settings.max_email_size_bytes:
            raise EmailTooLargeError(
                f"Email exceeds {self.settings.max_email_size_bytes} bytes"
            )
        internal_id = self._next_id()
        raw_path = self.settings.data_dir / "raw" / f"{internal_id}.eml"
        raw_path.write_bytes(raw)
        LOGGER.info("Email received: %s", internal_id)

        parsed = self.parser.parse(raw)
        LOGGER.info("Subject: %s", parsed.subject)
        LOGGER.info("Attachments: %d", len(parsed.attachments))
        attachments = self.attachments.process_all(internal_id, parsed.attachments)
        normalized = normalize_email(
            internal_id,
            parsed,
            attachments,
            source=source,
            received_at=received_at or datetime.now(timezone.utc),
        )

        output = self.settings.data_dir / "normalized" / f"{internal_id}.json"
        temporary = output.with_suffix(".json.tmp")
        temporary.write_text(
            normalized.model_dump_json(by_alias=True, indent=2), encoding="utf-8"
        )
        temporary.replace(output)
        if not self.settings.keep_work_files:
            shutil.rmtree(self.settings.data_dir / "work" / internal_id, ignore_errors=True)
        LOGGER.info("Generated %s", output)
        return normalized, output
