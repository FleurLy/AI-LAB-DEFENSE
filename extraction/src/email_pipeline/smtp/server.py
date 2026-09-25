from __future__ import annotations

import logging
from datetime import datetime, timezone

from aiosmtpd.controller import Controller

from email_pipeline.pipeline import EmailPipeline, EmailTooLargeError


LOGGER = logging.getLogger(__name__)


class MailHandler:
    def __init__(self, pipeline: EmailPipeline):
        self.pipeline = pipeline

    async def handle_DATA(self, server, session, envelope):
        raw = envelope.original_content
        if isinstance(raw, str):
            raw = raw.encode("utf-8", errors="surrogateescape")
        try:
            self.pipeline.process_raw(raw, source="smtp", received_at=datetime.now(timezone.utc))
        except EmailTooLargeError as exc:
            LOGGER.warning("Rejected oversized email: %s", exc)
            return "552 5.3.4 Message size exceeds fixed maximum message size"
        except Exception:
            LOGGER.exception("Email processing failed")
            return "451 4.3.0 Temporary processing failure"
        return "250 2.0.0 Message accepted for delivery"


def create_controller(pipeline: EmailPipeline, host: str, port: int) -> Controller:
    return Controller(
        MailHandler(pipeline),
        hostname=host,
        port=port,
        decode_data=False,
        enable_SMTPUTF8=True,
        data_size_limit=pipeline.settings.max_email_size_bytes,
    )
