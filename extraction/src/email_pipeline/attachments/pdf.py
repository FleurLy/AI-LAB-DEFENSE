from __future__ import annotations

import string
from io import BytesIO

import pymupdf as fitz
import pytesseract
from PIL import Image

from .qr import decode_qr_codes


def is_text_usable(text: str, min_length: int = 30) -> bool:
    compact = text.strip()
    if len(compact) < min_length:
        return False
    printable_ratio = sum(char in string.printable or char.isprintable() for char in compact) / len(compact)
    alphanumeric_ratio = sum(char.isalnum() for char in compact) / len(compact)
    replacement_ratio = compact.count("�") / len(compact)
    return printable_ratio >= 0.85 and alphanumeric_ratio >= 0.20 and replacement_ratio < 0.05


def _pixmap_image(page: fitz.Page) -> Image.Image:
    pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
    return Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)


def extract_pdf(
    payload: bytes, min_text_length: int, ocr_lang: str
) -> tuple[str, str, list[str], bool]:
    document = fitz.open(stream=payload, filetype="pdf")
    try:
        encrypted = bool(document.is_encrypted)
        if encrypted and not document.authenticate(""):
            return "", "error", [], True

        direct_text = "\n".join(page.get_text("text") for page in document).strip()
        qr_codes: list[str] = []
        if is_text_usable(direct_text, min_text_length):
            for page in document:
                for value in decode_qr_codes(_pixmap_image(page)):
                    if value not in qr_codes:
                        qr_codes.append(value)
            return direct_text, "text", qr_codes, encrypted

        ocr_pages: list[str] = []
        for page in document:
            image = _pixmap_image(page)
            ocr_pages.append(pytesseract.image_to_string(image, lang=ocr_lang).strip())
            for value in decode_qr_codes(image):
                if value not in qr_codes:
                    qr_codes.append(value)
        return "\n".join(filter(None, ocr_pages)).strip(), "ocr", qr_codes, encrypted
    finally:
        document.close()
