from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class EmailIdentity(BaseModel):
    model_config = ConfigDict(extra="allow")

    internal_id: str = Field(min_length=1)
    subject: str = ""
    body_text: str = ""
    body_html: str = ""


class NormalizedEmailInput(BaseModel):
    """Compatibility boundary for extraction schema v1.

    The classifier validates the stable envelope and preserves all remaining
    extraction fields verbatim so it can consume future additive schema changes.
    """

    model_config = ConfigDict(extra="allow")

    schema_version: Literal["1.0"]
    email: EmailIdentity
    attachments: list[dict[str, Any]] = Field(default_factory=list)
    urls: list[dict[str, Any]] = Field(default_factory=list)
    authentication: dict[str, Any] = Field(default_factory=dict)
    sender: dict[str, Any] = Field(default_factory=dict)
    routing: dict[str, Any] = Field(default_factory=dict)
    content_signals: dict[str, Any] = Field(default_factory=dict)
    technical_signals: dict[str, Any] = Field(default_factory=dict)

