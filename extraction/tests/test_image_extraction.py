from io import BytesIO
from unittest.mock import patch

from PIL import Image

from email_pipeline.attachments.image import extract_image


def png_bytes() -> bytes:
    image = Image.new("RGB", (100, 50), "white")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_image_ocr_and_qr_results_are_returned() -> None:
    with (
        patch("email_pipeline.attachments.image.pytesseract.image_to_string", return_value="Visible text\n"),
        patch("email_pipeline.attachments.image.decode_qr_codes", return_value=["https://qr.example"]),
    ):
        text, qr_codes = extract_image(png_bytes(), "eng")

    assert text == "Visible text"
    assert qr_codes == ["https://qr.example"]

