from __future__ import annotations

import hashlib
import mimetypes
import zipfile
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from pathlib import Path

from email_pipeline.config import Settings
from email_pipeline.mail.parser import RawAttachment
from email_pipeline.schemas.email_schema import (
    Attachment,
    AttachmentSecurity,
    ExtractionResult,
)
from email_pipeline.urls.extractor import extract_text_urls

from .common import sanitize_filename, unique_path
from .image import extract_image
from .office import extract_docx, extract_pptx, extract_xlsx
from .pdf import extract_pdf


EXECUTABLE_EXTENSIONS = {
    ".apk", ".app", ".bat", ".bin", ".cmd", ".com", ".dll", ".dmg", ".exe",
    ".hta", ".jar", ".js", ".lnk", ".msi", ".ps1", ".scr", ".sh", ".vbs",
}
MACRO_EXTENSIONS = {".docm", ".dotm", ".xlsm", ".xltm", ".pptm", ".potm"}
IMAGE_EXTENSIONS = {".bmp", ".gif", ".jpeg", ".jpg", ".png", ".tif", ".tiff", ".webp"}
OFFICE_EXTRACTORS = {
    ".docx": extract_docx,
    ".xlsx": extract_xlsx,
    ".pptx": extract_pptx,
}
EXPECTED_MIME_BY_EXTENSION = {
    ".pdf": {"application/pdf"},
    ".png": {"image/png"},
    ".jpg": {"image/jpeg"},
    ".jpeg": {"image/jpeg"},
    ".gif": {"image/gif"},
    ".tif": {"image/tiff"},
    ".tiff": {"image/tiff"},
    ".txt": {"text/plain"},
    ".docx": {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
    ".xlsx": {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
    ".pptx": {"application/vnd.openxmlformats-officedocument.presentationml.presentation"},
}


def detect_mime(payload: bytes, filename: str) -> str | None:
    try:
        import magic

        detected = magic.from_buffer(payload, mime=True)
        if detected:
            return str(detected)
    except Exception:
        pass
    return mimetypes.guess_type(filename)[0]


def _contains_vba(path: Path) -> bool:
    try:
        if not zipfile.is_zipfile(path):
            return False
        with zipfile.ZipFile(path) as archive:
            return any(name.lower().endswith("vbaproject.bin") for name in archive.namelist())
    except (OSError, zipfile.BadZipFile):
        return False


class AttachmentManager:
    def __init__(self, settings: Settings):
        self.settings = settings

    def process_all(self, internal_id: str, items: list[RawAttachment]) -> list[Attachment]:
        directory = self.settings.data_dir / "attachments" / internal_id
        directory.mkdir(parents=True, exist_ok=True)
        return [self._process(directory, item, index) for index, item in enumerate(items, 1)]

    def _process(self, directory: Path, item: RawAttachment, index: int) -> Attachment:
        name = sanitize_filename(item.filename, f"attachment_{index}")
        path = unique_path(directory, name)
        payload = item.payload
        sha256 = hashlib.sha256(payload).hexdigest()
        detected = detect_mime(payload, name)
        extension = path.suffix.lower()
        declared = item.content_type or None
        generic_detected = detected in {"application/zip", "application/octet-stream"}
        generic_is_expected = generic_detected and (
            extension in OFFICE_EXTRACTORS or extension in MACRO_EXTENSIONS
        )
        declared_mismatch = bool(
            declared and detected and declared != detected and not generic_is_expected
        )
        expected_mimes = EXPECTED_MIME_BY_EXTENSION.get(extension)
        extension_mismatch = bool(
            expected_mimes and detected and detected not in expected_mimes and not generic_is_expected
        )
        mismatch = declared_mismatch or extension_mismatch
        security = AttachmentSecurity(
            extension_mime_mismatch=mismatch,
            encrypted=False,
            contains_macro=extension in MACRO_EXTENSIONS,
            contains_executable=extension in EXECUTABLE_EXTENSIONS,
        )

        if len(payload) > self.settings.max_attachment_size_bytes:
            return self._result(
                name, declared, detected, payload, sha256, "", [], security,
                "error", False, f"Attachment exceeds {self.settings.max_attachment_size_bytes} bytes",
            )

        path.write_bytes(payload)
        security.contains_macro = security.contains_macro or _contains_vba(path)
        executor = ThreadPoolExecutor(max_workers=1)
        try:
            future = executor.submit(self._extract, extension, detected, payload)
            text, method, qr_codes, encrypted = future.result(
                timeout=self.settings.extractor_timeout_seconds
            )
            security.encrypted = encrypted
            success = method not in {"unsupported", "error"}
            error = None if success else (
                "Encrypted PDF cannot be opened" if encrypted else "Unsupported attachment type"
            )
        except FutureTimeout:
            future.cancel()
            text, method, qr_codes, success = "", "error", [], False
            error = f"Extractor timed out after {self.settings.extractor_timeout_seconds:g} seconds"
        except Exception as exc:
            text, method, qr_codes, success = "", "error", [], False
            error = f"{type(exc).__name__}: {exc}"
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

        return self._result(
            name, declared, detected, payload, sha256, text, qr_codes, security,
            method, success, error,
        )

    def _extract(
        self, extension: str, detected: str | None, payload: bytes
    ) -> tuple[str, str, list[str], bool]:
        if extension == ".pdf" or detected == "application/pdf":
            text, method, qr_codes, encrypted = extract_pdf(
                payload, self.settings.min_pdf_text_length, self.settings.ocr_lang
            )
            return text, method, qr_codes, encrypted
        if extension in IMAGE_EXTENSIONS or (detected or "").startswith("image/"):
            text, qr_codes = extract_image(payload, self.settings.ocr_lang)
            return text, "ocr", qr_codes, False
        extractor = OFFICE_EXTRACTORS.get(extension)
        if extractor:
            return extractor(payload), "office", [], False
        if (detected or "").startswith("text/"):
            return payload.decode("utf-8", errors="replace"), "text", [], False
        return "", "unsupported", [], False

    @staticmethod
    def _result(
        name: str,
        declared: str | None,
        detected: str | None,
        payload: bytes,
        sha256: str,
        text: str,
        qr_codes: list[str],
        security: AttachmentSecurity,
        method: str,
        success: bool,
        error: str | None,
    ) -> Attachment:
        return Attachment(
            name=name,
            mime_type_declared=declared,
            mime_type_detected=detected,
            size_bytes=len(payload),
            sha256=sha256,
            content_text=text,
            visual_description=None,
            extraction=ExtractionResult(method=method, success=success, error=error),
            urls=extract_text_urls(text),
            qr_codes=qr_codes,
            security=security,
        )
