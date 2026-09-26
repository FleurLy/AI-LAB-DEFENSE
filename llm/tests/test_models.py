import json
from typing import Any

import pytest
from pydantic import ValidationError

from app.models.analysis import AIAnalysisResult
from app.models.email import EmailAnalysisRequest
from app.prompts.email_analysis import build_analysis_messages


def test_example_preserves_every_field(example_payload: dict[str, Any]) -> None:
    request = EmailAnalysisRequest.model_validate(example_payload)
    assert request.model_dump(mode="json", by_alias=True) == example_payload
    assert request.email.from_.address == "security@example.com"
    messages = build_analysis_messages(request)
    assert messages[0].type == "system"
    assert messages[1].type == "human"
    assert json.loads(messages[1].content) == example_payload


@pytest.mark.parametrize("field", list(EmailAnalysisRequest.model_fields))
def test_missing_top_level_field_rejected(
    example_payload: dict[str, Any], field: str
) -> None:
    del example_payload[field]
    with pytest.raises(ValidationError):
        EmailAnalysisRequest.model_validate(example_payload)


@pytest.mark.parametrize(
    "parent, field",
    [("email", "from"), ("authentication", "spf"), ("technical_signals", "qr_code_count")],
)
def test_missing_nested_field_rejected(
    example_payload: dict[str, Any], parent: str, field: str
) -> None:
    del example_payload[parent][field]
    with pytest.raises(ValidationError):
        EmailAnalysisRequest.model_validate(example_payload)


def test_nullable_fields_and_empty_lists(example_payload: dict[str, Any]) -> None:
    example_payload["email"]["from"]["name"] = None
    example_payload["email"]["reply_to"] = None
    example_payload["email"]["to"] = []
    example_payload["email"]["cc"] = []
    example_payload["email"]["language"] = None
    for field in ("reply_to_domain", "return_path", "return_path_domain"):
        example_payload["sender"][field] = None
    for attachment in example_payload["attachments"]:
        attachment.update(content_text=None, visual_description=None, urls=[], qr_codes=[])
    for url in example_payload["urls"]:
        url["display_text"] = None
    request = EmailAnalysisRequest.model_validate(example_payload)
    assert request.attachments[0].content_text is None
    assert request.urls[0].display_text is None
    assert request.model_dump(mode="json", by_alias=True) == example_payload
    example_payload.update(attachments=[], urls=[])
    request = EmailAnalysisRequest.model_validate(example_payload)
    assert request.attachments == []
    assert request.urls == []


def test_nullable_field_is_still_required(example_payload: dict[str, Any]) -> None:
    del example_payload["attachments"][0]["visual_description"]
    with pytest.raises(ValidationError):
        EmailAnalysisRequest.model_validate(example_payload)


@pytest.mark.parametrize(
    "path, value",
    [
        (("email", "from", "address"), "invalid-address"),
        (("email", "sent_at"), "not-a-date"),
        (("routing", "received_at"), "2026-09-25T18:30:00"),
        (("attachments", 0, "size_bytes"), -1),
        (("urls", 0, "url"), "not-a-url"),
        (("technical_signals", "url_count"), -1),
        (("technical_signals", "url_count"), True),
        (("technical_signals", "url_count"), "2"),
        (("content_signals", "contains_attachment"), "true"),
        (("email", "unexpected"), "extra"),
    ],
)
def test_invalid_nested_values(
    example_payload: dict[str, Any], path: tuple[str | int, ...], value: Any
) -> None:
    target = example_payload
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(ValidationError):
        EmailAnalysisRequest.model_validate(example_payload)


PROBABILITY_FIELDS = [
    name for name in AIAnalysisResult.model_fields if name.endswith("_probability")
]


@pytest.mark.parametrize("field", PROBABILITY_FIELDS)
@pytest.mark.parametrize("value", [-0.01, 1.01, float("nan"), float("inf"), "0.5", True])
def test_probability_constraints(
    analysis_result: AIAnalysisResult, field: str, value: Any
) -> None:
    data = analysis_result.model_dump()
    data[field] = value
    with pytest.raises(ValidationError):
        AIAnalysisResult.model_validate(data)


@pytest.mark.parametrize("value", [0, 1])
def test_probability_boundaries(analysis_result: AIAnalysisResult, value: int) -> None:
    data = analysis_result.model_dump()
    data.update({field: value for field in PROBABILITY_FIELDS})
    data["evidence"][0]["confidence"] = value
    AIAnalysisResult.model_validate(data)


@pytest.mark.parametrize("value", [-0.1, 1.1, float("nan"), True])
def test_evidence_confidence_constraints(analysis_result: AIAnalysisResult, value: Any) -> None:
    data = analysis_result.model_dump()
    data["evidence"][0]["confidence"] = value
    with pytest.raises(ValidationError):
        AIAnalysisResult.model_validate(data)


@pytest.mark.parametrize("field", ["requested_action", "attack_type"])
def test_output_enums_reject_unknown_values(
    analysis_result: AIAnalysisResult, field: str
) -> None:
    data = analysis_result.model_dump()
    data[field] = "invented-value"
    with pytest.raises(ValidationError):
        AIAnalysisResult.model_validate(data)


def test_evidence_severity_validation(analysis_result: AIAnalysisResult) -> None:
    data = analysis_result.model_dump()
    data["evidence"][0]["severity"] = "invented-value"
    with pytest.raises(ValidationError):
        AIAnalysisResult.model_validate(data)
