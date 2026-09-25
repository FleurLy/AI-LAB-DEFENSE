from __future__ import annotations

from PIL import Image


def decode_qr_codes(image: Image.Image) -> list[str]:
    try:
        from pyzbar.pyzbar import decode

        values = []
        for item in decode(image):
            value = item.data.decode("utf-8", errors="replace").strip()
            if value and value not in values:
                values.append(value)
        return values
    except Exception:
        # Missing native zbar or malformed image must never break the pipeline.
        return []

