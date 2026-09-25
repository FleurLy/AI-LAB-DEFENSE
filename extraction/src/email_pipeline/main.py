from __future__ import annotations

import logging
import signal
import threading

from email_pipeline.config import Settings
from email_pipeline.pipeline import EmailPipeline
from email_pipeline.smtp import create_controller


def main() -> None:
    settings = Settings.from_env()
    logging.basicConfig(
        level=getattr(logging, settings.log_level, logging.INFO),
        format="[%(levelname)s] %(message)s",
    )
    pipeline = EmailPipeline(settings)
    controller = create_controller(pipeline, settings.smtp_host, settings.smtp_port)
    controller.start()
    logging.info("SMTP server listening on %s:%d", settings.smtp_host, settings.smtp_port)

    stop_event = threading.Event()

    def stop(*_args) -> None:
        stop_event.set()

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    try:
        stop_event.wait()
    finally:
        controller.stop()
        logging.info("SMTP server stopped")


if __name__ == "__main__":
    main()

