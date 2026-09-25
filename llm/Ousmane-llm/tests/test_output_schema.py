import pytest
from pydantic import ValidationError

from tests.helpers import decision


def test_valid_output_schema() -> None:
    result = decision("malicious", "credential_phishing", 94, "quarantine")
    assert result.risk_score == 94
    assert result.explanation


def test_output_rejects_out_of_range_score() -> None:
    with pytest.raises(ValidationError):
        decision("malicious", "phishing", 101, "quarantine")


def test_output_rejects_incoherent_action() -> None:
    with pytest.raises(ValidationError):
        decision("benign", "legitimate", 2, "quarantine")

