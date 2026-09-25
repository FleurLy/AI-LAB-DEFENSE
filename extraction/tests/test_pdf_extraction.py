import pymupdf as fitz
from unittest.mock import patch

from email_pipeline.attachments.pdf import extract_pdf, is_text_usable


def make_text_pdf(text: str) -> bytes:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), text)
    payload = document.tobytes()
    document.close()
    return payload


def test_text_usability_rejects_noise() -> None:
    assert not is_text_usable("x", min_length=10)
    assert not is_text_usable("�" * 100, min_length=10)
    assert is_text_usable("Invoice number 4582 and total amount 49 EUR", min_length=10)


def test_pdf_prefers_native_text() -> None:
    payload = make_text_pdf("Invoice 4582 - total amount due is 4850 EUR today")
    text, method, qr_codes, encrypted = extract_pdf(payload, 20, "eng")

    assert "Invoice 4582" in text
    assert method == "text"
    assert qr_codes == []
    assert encrypted is False


def test_scanned_pdf_falls_back_to_ocr() -> None:
    document = fitz.open()
    document.new_page()
    payload = document.tobytes()
    document.close()
    with (
        patch("email_pipeline.attachments.pdf.pytesseract.image_to_string", return_value="Scanned invoice text"),
        patch("email_pipeline.attachments.pdf.decode_qr_codes", return_value=[]),
    ):
        text, method, _, _ = extract_pdf(payload, 30, "eng")
    assert text == "Scanned invoice text"
    assert method == "ocr"
