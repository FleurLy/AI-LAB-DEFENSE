from fastapi.testclient import TestClient

from ousmane_llm.api import create_app
from ousmane_llm.config import Settings
from tests.helpers import decision


class FakeAnalyzer:
    def analyze(self, _payload):
        return decision("suspicious", "unknown", 52, "human_review")


def test_health_and_model_endpoints() -> None:
    client = TestClient(create_app(Settings(), FakeAnalyzer()))
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/model").json()["model"] == "qwen3.5:4b"


def test_analyze_endpoint(normalized_email) -> None:
    client = TestClient(create_app(Settings(), FakeAnalyzer()))
    response = client.post("/analyze", json=normalized_email)
    assert response.status_code == 200
    assert response.json()["verdict"] == "suspicious"

