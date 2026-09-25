from __future__ import annotations

import re
import unicodedata
from pathlib import Path


_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")


def sanitize_filename(name: str, fallback: str = "attachment") -> str:
    normalized = unicodedata.normalize("NFKD", Path(name).name)
    ascii_name = normalized.encode("ascii", "ignore").decode("ascii")
    cleaned = _UNSAFE.sub("_", ascii_name).strip("._")
    return (cleaned or fallback)[:180]


def unique_path(directory: Path, filename: str) -> Path:
    path = directory / filename
    stem, suffix = path.stem, path.suffix
    index = 1
    while path.exists():
        path = directory / f"{stem}_{index}{suffix}"
        index += 1
    return path

