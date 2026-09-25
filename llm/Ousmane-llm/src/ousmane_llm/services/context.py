from __future__ import annotations

import copy
import json
import logging
from dataclasses import dataclass
from typing import Any


LOGGER = logging.getLogger(__name__)
TRUNCATION_MARKER = "\n[TRUNCATED BY HOST: untrusted content exceeded configured limit]"


class InputTooLargeError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class PreparedPayload:
    data: dict[str, Any]
    truncated: bool
    original_chars: int
    prepared_chars: int


def _serialized_size(data: dict[str, Any]) -> int:
    return len(json.dumps(data, ensure_ascii=False, separators=(",", ":")))


def _content_slots(data: dict[str, Any]) -> list[tuple[dict[str, Any], str]]:
    slots: list[tuple[dict[str, Any], str]] = []
    email = data.get("email")
    if isinstance(email, dict):
        for key in ("body_text", "body_html"):
            if isinstance(email.get(key), str):
                slots.append((email, key))
    attachments = data.get("attachments")
    if isinstance(attachments, list):
        for attachment in attachments:
            if isinstance(attachment, dict) and isinstance(attachment.get("content_text"), str):
                slots.append((attachment, "content_text"))
    return slots


def prepare_payload(payload: dict[str, Any], max_chars: int) -> PreparedPayload:
    """Bound untrusted text while retaining every technical field and collection."""

    working = copy.deepcopy(payload)
    original_size = _serialized_size(working)
    if original_size <= max_chars:
        return PreparedPayload(working, False, original_size, original_size)

    slots = _content_slots(working)
    originals = [container[key] for container, key in slots]
    for container, key in slots:
        container[key] = ""
    fixed_size = _serialized_size(working)
    if fixed_size > max_chars:
        raise InputTooLargeError(
            "Technical and structural fields alone exceed MAX_INPUT_CHARS; "
            "refusing to silently remove security evidence"
        )

    available = max(0, max_chars - fixed_size - len(slots) * len(TRUNCATION_MARKER) - 256)
    per_slot = max(0, available // max(1, len(slots)))
    for (container, key), original in zip(slots, originals, strict=True):
        if len(original) <= per_slot:
            container[key] = original
        elif per_slot > 80:
            head = int(per_slot * 0.75)
            tail = per_slot - head
            container[key] = original[:head] + TRUNCATION_MARKER + original[-tail:]
        else:
            container[key] = TRUNCATION_MARKER.strip()

    # JSON escaping can add bytes. Tighten only untrusted content until exact.
    prepared_size = _serialized_size(working)
    while prepared_size > max_chars and per_slot > 0:
        per_slot = int(per_slot * 0.8)
        for (container, key), original in zip(slots, originals, strict=True):
            container[key] = original[:per_slot] + TRUNCATION_MARKER
        prepared_size = _serialized_size(working)

    if prepared_size > max_chars:
        raise InputTooLargeError("Unable to bound input without deleting technical evidence")
    LOGGER.warning(
        "Input truncated from %d to %d characters; technical fields preserved",
        original_size,
        prepared_size,
    )
    return PreparedPayload(working, True, original_size, prepared_size)

