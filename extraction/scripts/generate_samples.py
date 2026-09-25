#!/usr/bin/env python3
"""Generate harmless PDF/image attachment samples and matching .eml files."""
from __future__ import annotations

from email.message import EmailMessage
from pathlib import Path

import pymupdf as fitz
import qrcode
from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
ATTACHMENTS = ROOT / "samples" / "attachments"
SUSPICIOUS = ROOT / "samples" / "suspicious"


def write_message(path: Path, subject: str, body: str, attachment: Path) -> None:
    message = EmailMessage()
    message["From"] = "Billing <billing@example.com>"
    message["To"] = "user@company.test"
    message["Subject"] = subject
    message.set_content(body)
    payload = attachment.read_bytes()
    maintype, subtype = (
        ("application", "pdf") if attachment.suffix == ".pdf" else ("image", "png")
    )
    message.add_attachment(payload, maintype=maintype, subtype=subtype, filename=attachment.name)
    path.write_bytes(message.as_bytes())


def main() -> None:
    ATTACHMENTS.mkdir(parents=True, exist_ok=True)
    SUSPICIOUS.mkdir(parents=True, exist_ok=True)

    invoice = ATTACHMENTS / "invoice.pdf"
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "INVOICE 4582 - Amount due: EUR 4,850 - https://example.test/pay")
    document.save(invoice)
    document.close()

    scanned = ATTACHMENTS / "scanned_invoice.pdf"
    image = Image.new("RGB", (1200, 500), "white")
    ImageDraw.Draw(image).text((60, 180), "SCANNED INVOICE 991 - PAYMENT REQUIRED", fill="black")
    pixmap_path = ATTACHMENTS / "scanned_invoice.png"
    image.save(pixmap_path)
    document = fitz.open()
    page = document.new_page(width=1200, height=500)
    page.insert_image(page.rect, filename=str(pixmap_path))
    document.save(scanned)
    document.close()
    pixmap_path.unlink()

    qr_path = ATTACHMENTS / "qr_code.png"
    qr_image = qrcode.make("https://fake-login.example")
    qr_image.save(qr_path)

    write_message(
        SUSPICIOUS / "invoice_pdf.eml",
        "Facture urgente",
        "Veuillez examiner la facture jointe.",
        invoice,
    )
    write_message(
        SUSPICIOUS / "scanned_pdf.eml",
        "Facture scannée",
        "La facture scannée est jointe.",
        scanned,
    )
    write_message(
        SUSPICIOUS / "qr_phishing.eml",
        "Confirmez votre compte",
        "Scannez le code joint pour confirmer votre compte.",
        qr_path,
    )
    print("Generated harmless attachment samples")


if __name__ == "__main__":
    main()
