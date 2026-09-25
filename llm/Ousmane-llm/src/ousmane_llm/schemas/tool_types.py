from __future__ import annotations

from typing import Literal, TypedDict


class ReasonPayload(TypedDict):
    type: Literal["authentication", "sender", "content", "url", "attachment", "context"]
    description: str

