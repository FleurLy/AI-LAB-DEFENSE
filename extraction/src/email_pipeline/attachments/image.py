from __future__ import annotations

from io import BytesIO

import pytesseract
from PIL import Image, ImageOps

from .qr import decode_qr_codes


def extract_image(payload: bytes, ocr_lang: str) -> tuple[str, list[str]]:
    with Image.open(BytesIO(payload)) as source:
        image = ImageOps.exif_transpose(source).convert("RGB")
        qr_codes = decode_qr_codes(image)
        text = pytesseract.image_to_string(image, lang=ocr_lang).strip()
    return text, qr_codes

