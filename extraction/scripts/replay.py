#!/usr/bin/env python3
from __future__ import annotations

import argparse
import smtplib
from email import policy
from email.parser import BytesParser
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay an .eml file through SMTP")
    parser.add_argument("eml", type=Path)
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=1025)
    args = parser.parse_args()

    source = args.eml.read_bytes()
    message = BytesParser(policy=policy.default).parsebytes(source)
    # SMTP requires CRLF line endings and limits each physical line to 998 octets.
    # Re-serialization preserves the MIME content while making hand-written and
    # generated samples safe to transmit with smtplib's bytes API.
    raw = message.as_bytes(policy=policy.SMTP)
    sender = message.get("From", "replay@localhost")
    recipients = [
        address.addr_spec
        for header in ("To", "Cc", "Bcc")
        for address in (message[header].addresses if message.get(header) else ())
    ]
    if not recipients:
        recipients = ["recipient@localhost"]
    with smtplib.SMTP(args.host, args.port, timeout=15) as smtp:
        smtp.sendmail(sender, recipients, raw)
    print(f"Sent {args.eml} to {args.host}:{args.port}")


if __name__ == "__main__":
    main()
