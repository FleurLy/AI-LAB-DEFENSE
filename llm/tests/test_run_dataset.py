"""Dataset runner tests: no SMTP server, API server or external LLM required."""
import importlib.util
import json
import subprocess
import sys
from email import policy
from email.parser import BytesParser
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_dataset.py"
spec = importlib.util.spec_from_file_location("run_dataset", SCRIPT)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


@pytest.fixture
def dataset(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "ROOT", tmp_path / "llm")
    samples = tmp_path / "samples"
    nested = samples / "nested"
    nested.mkdir(parents=True)
    for name in ("a", "b", "c"):
        (nested / f"{name}.eml").write_text(
            f"From: sender@example.com\nTo: user@example.com\nSubject: {name}\n\nBody {name}\n"
        )
    (nested / "ignored.txt").write_text("ignored")
    data = tmp_path / "data"
    (data / "normalized").mkdir(parents=True)
    (data / "raw").mkdir()
    return samples, data


def produce(data, sample, number):
    raw = BytesParser(policy=policy.default).parsebytes(sample.read_bytes()).as_bytes(policy=policy.SMTP)
    if not raw.endswith(b"\r\n"):
        raw += b"\r\n"
    (data / "raw" / f"mail_{number}.eml").write_bytes(raw)
    payload = {"email": {"subject": sample.stem}}
    path = data / "normalized" / f"mail_{number}.json"
    path.write_text(json.dumps(payload))
    return path, payload


def test_sequential_recursive_run_records_api_failure_and_continues(dataset):
    samples, data = dataset
    events = []
    calls = []
    produce(data, samples / "nested" / "a.eml", "old")

    def replay(command, **kwargs):
        sample = Path(command[2])
        assert command[0] == sys.executable
        assert Path(command[1]).name == "replay.py"
        assert kwargs["timeout"] == 60
        events.append(f"replay:{sample.stem}")
        produce(data, sample, sample.stem)
        return subprocess.CompletedProcess(command, 0, "Sent", "")

    def api(request):
        payload = json.loads(request.content)
        subject = payload["email"]["subject"]
        events.append(f"api:{subject}")
        calls.append(payload)
        if subject == "b":
            return httpx.Response(502, json={"detail": {"code": "provider_error"}})
        return httpx.Response(200, json={"approach": "jev_then_gpt", "analysis": {}, "report": {}})

    with patch.object(runner.subprocess, "run", side_effect=replay):
        with httpx.Client(transport=httpx.MockTransport(api)) as client:
            results = runner.run_dataset(samples, data, runner.EXTRACTION_ROOT / "scripts" / "replay.py", client)
    assert events == [f"{stage}:{name}" for name in "abc" for stage in ("replay", "api")]
    assert len(results) == 3
    assert [row["api_status_code"] for row in results] == [200, 502, 200]
    assert results[1]["errors"][0]["stage"] == "api"
    assert results[1]["api_response"]["detail"]["code"] == "provider_error"
    for index, row in enumerate(results):
        assert Path(row["sample_path"]).is_file()
        assert Path(row["normalized_path"]).name != "mail_old.json"
        assert row["normalized_json"] == calls[index]
    assert json.loads((data.parent / "llm" / "data" / "results" / "results.json").read_text()) == results
    output = runner.ROOT / "data" / "results"
    for row in (results[0], results[2]):
        name = Path(row["sample_path"]).stem
        assert json.loads((output / f"{name}.json").read_text()) == row["api_response"]
        assert (output / f"{name}.md").read_text() == runner.generate_markdown(row["api_response"])
    assert not (output / "b.md").exists()
    assert not (output / "b.json").exists()



@pytest.mark.parametrize("failure", ["smtp_error", "replay_timeout", "normalization_timeout"])
def test_replay_and_normalization_failures_do_not_stop_dataset(dataset, failure):
    samples, data = dataset

    def replay(command, **kwargs):
        sample = Path(command[2])
        if sample.stem == "a":
            if failure == "replay_timeout":
                raise subprocess.TimeoutExpired(command, kwargs["timeout"])
            return subprocess.CompletedProcess(command, 1 if failure == "smtp_error" else 0, "", "SMTP unavailable")
        # Late output from the failed first sample must not be used for b.
        produce(data, samples / "nested" / "a.eml", "late")
        produce(data, sample, sample.stem)
        return subprocess.CompletedProcess(command, 0, "", "")

    with patch.object(runner.subprocess, "run", side_effect=replay):
        with httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(200, json={"ok": True}))) as client:
            results = runner.run_dataset(samples, data, runner.EXTRACTION_ROOT / "scripts" / "replay.py", client, normalization_timeout=0.01)
    assert results[0]["errors"][0]["stage"] == ("normalization" if failure == "normalization_timeout" else "replay")
    assert results[0]["api_response"] is None
    assert [row["normalized_json"]["email"]["subject"] for row in results[1:]] == ["b", "c"]
    assert all(not row["errors"] for row in results[1:])


@pytest.mark.parametrize("failure", ["timeout", "non_json"])
def test_http_transport_and_non_json_errors_are_saved(dataset, failure):
    samples, data = dataset

    def replay(command, **kwargs):
        sample = Path(command[2])
        produce(data, sample, sample.stem)
        return subprocess.CompletedProcess(command, 0, "", "")

    def api(request):
        if failure == "timeout":
            raise httpx.ReadTimeout("API timeout", request=request)
        return httpx.Response(503, text="Unavailable")

    with patch.object(runner.subprocess, "run", side_effect=replay):
        with httpx.Client(transport=httpx.MockTransport(api)) as client:
            results = runner.run_dataset(samples, data, runner.EXTRACTION_ROOT / "scripts" / "replay.py", client)
    assert len(results) == 3
    assert all(row["errors"][0]["stage"] == "api" for row in results)
    if failure == "non_json":
        assert all(row["api_response"] == "Unavailable" and row["api_status_code"] == 503 for row in results)


def test_actual_replay_subprocess_invocation(dataset, tmp_path):
    samples, data = dataset
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    fake_replay = scripts / "replay.py"
    fake_replay.write_text('''import json, sys
from pathlib import Path
from email import policy
from email.parser import BytesParser
root = Path(__file__).resolve().parents[1]
sample = Path(sys.argv[1])
raw = BytesParser(policy=policy.default).parsebytes(sample.read_bytes()).as_bytes(policy=policy.SMTP)
(root / "data/raw" / (sample.stem + ".eml")).write_bytes(raw)
(root / "data/normalized" / (sample.stem + ".json")).write_text(json.dumps({"email": {"subject": sample.stem}}))
''')
    with httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(200, json={"ok": True}))) as client:
        results = runner.run_dataset(samples, data, fake_replay, client)
    assert len(results) == 3
    assert all(not row["errors"] for row in results)


def test_email_without_final_newline_matches_smtp_output(dataset):
    samples, data = dataset
    sample = samples / "nested" / "a.eml"
    sample.write_bytes(sample.read_bytes().rstrip(b"\r\n"))

    def replay(command, **kwargs):
        current = Path(command[2])
        produce(data, current, current.stem)
        return subprocess.CompletedProcess(command, 0, "", "")

    with patch.object(runner.subprocess, "run", side_effect=replay):
        with httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(200, json={"ok": True}))) as client:
            results = runner.run_dataset(samples, data, runner.EXTRACTION_ROOT / "scripts" / "replay.py", client, normalization_timeout=0.01)
    assert all(not row["errors"] for row in results)


def test_waits_for_delayed_matching_json_and_ignores_other_email(dataset):
    import threading

    samples, data = dataset
    sample = samples / "nested" / "a.eml"
    expected_raw = BytesParser(policy=policy.default).parsebytes(sample.read_bytes()).as_bytes(policy=policy.SMTP)
    previous = set((data / "normalized").glob("*.json"))
    produce(data, samples / "nested" / "b.eml", "unrelated")
    delayed = threading.Timer(0.03, produce, args=(data, sample, "delayed"))
    delayed.start()
    try:
        path, payload = runner.wait_for_normalized(data / "normalized", previous, expected_raw, 1, poll_interval=0.01)
    finally:
        delayed.join()
    assert path.name == "mail_delayed.json"
    assert payload["email"]["subject"] == "a"


def test_generate_markdown_uses_existing_fields_only():
    result = {
        "approach": "jev_then_gpt",
        "analysis": {
            "social_engineering_probability": 0.9,
            "phishing_probability": 0.0,
            "attack_type": "phishing",
            "requested_action": "provide_credentials",
            "evidence": [{
                "type": "urgency", "severity": "high", "confidence": 0.8,
                "description": "Demande urgente de vérification.", "source": "email.subject",
            }],
        },
        "report": {
            "summary": "Message suspect.",
            "risk_explanation": "La demande utilise l’urgence.",
            "recommended_actions": ["Vérifier l’expéditeur.", "Signaler le message."],
        },
    }
    snapshot = json.dumps(result)
    markdown = runner.generate_markdown(result)
    assert markdown == runner.generate_markdown(result)
    assert json.dumps(result) == snapshot
    for heading in ("Overview", "Summary", "Evidence", "Risk explanation", "Recommended actions"):
        assert f"## {heading}\n\n" in markdown
    for field in (
        "Social engineering probability: 0.9", "Phishing probability: 0.0",
        "Attack type: phishing", "Type: urgency", "Severity: high", "Confidence: 0.8",
        "Description: Demande urgente de vérification.", "Source: email.subject",
        "Message suspect.", "La demande utilise l’urgence.",
        "- Vérifier l’expéditeur.", "- Signaler le message.",
    ):
        assert field in markdown
    assert "provide\\_credentials" in markdown
    assert "jev\\_then\\_gpt" in markdown


def test_generate_markdown_omits_absent_values():
    assert runner.generate_markdown({}) == "# Email Security Analysis\n"
    markdown = runner.generate_markdown({
        "analysis": {"phishing_probability": 0, "evidence": []},
        "report": {"summary": None, "recommended_actions": []},
    })
    assert "Phishing probability: 0" in markdown
    assert "## Summary" not in markdown
    assert "## Evidence" not in markdown
    assert "## Risk explanation" not in markdown
    assert "## Recommended actions" not in markdown
    assert "None" not in markdown


def test_markdown_renders_embedded_markup_as_text():
    markdown = runner.generate_markdown({"report": {
        "summary": "<script>alert(1)</script> ![image](https://example.com)",
        "recommended_actions": ["First line\nsecond line"],
    }})
    assert "<script>" not in markdown
    assert "![image]" not in markdown
    assert "&lt;script&gt;" in markdown
    assert "- First line\n  second line" in markdown




def test_discovers_all_source_eml_and_excludes_generated_data(tmp_path):
    root = tmp_path / "extraction"
    data = root / "data"
    source_files = [
        root / "samples" / "benign" / "one.eml",
        root / "datasets" / "set" / "two.eml",
    ]
    generated = data / "raw" / "mail_000001.eml"
    for path in [*source_files, generated]:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("From: test.org\n\nbody")
    assert runner.discover_eml_files(root, data) == sorted(source_files)



def test_loads_manifest_labels_and_scores_predictions(tmp_path):
    dataset = tmp_path / "datasets" / "validation"
    emails = dataset / "emails"
    emails.mkdir(parents=True)
    safe_path = emails / "safe.eml"
    phishing_path = emails / "phishing.eml"
    numeric_path = emails / "numeric.eml"
    for path in (safe_path, phishing_path, numeric_path):
        path.write_text("From: test.org\n\nbody")
    (dataset / "manifest.csv").write_text(
        "file_path,label,label_name\n"
        "emails/safe.eml,0,safe\n"
        "emails/phishing.eml,1,phishing\n"
        "emails/numeric.eml,1,\n"
    )

    labels = runner.load_manifest_labels(tmp_path)
    assert labels == {
        safe_path.resolve(): "benign",
        phishing_path.resolve(): "suspicious",
        numeric_path.resolve(): "suspicious",
    }
    safe = {"analysis": {"attack_type": "none"}}
    attack = {"analysis": {"attack_type": "phishing"}}
    assert runner.classification_success(safe, safe_path, labels) is True
    assert runner.classification_success(attack, safe_path, labels) is False
    assert runner.classification_success(attack, phishing_path, labels) is True
    assert runner.classification_success(safe, phishing_path, labels) is False


def test_path_label_takes_priority_over_manifest(tmp_path):
    sample = tmp_path / "benign" / "message.eml"
    labels = {sample.resolve(): "suspicious"}
    assert runner.expected_classification(sample, labels) == "benign"


def test_dataset_path_classification_and_markdown_flag(tmp_path):
    benign = tmp_path / "benign" / "message.eml"
    suspicious = tmp_path / "suspicious" / "message.eml"
    unlabeled = tmp_path / "other" / "message.eml"
    safe = {"analysis": {"attack_type": "none"}}
    attack = {"analysis": {"attack_type": "phishing"}}

    assert runner.classification_success(safe, benign) is True
    assert runner.classification_success(attack, benign) is False
    assert runner.classification_success(attack, suspicious) is True
    assert runner.classification_success(safe, suspicious) is False
    assert runner.classification_success({}, suspicious) is False
    assert runner.classification_success(attack, unlabeled) is None
    assert runner.generate_markdown(safe, True).startswith("# SUCCESS\n\n# Email Security Analysis")
    assert runner.generate_markdown(attack, False).startswith("# FAIL\n\n# Email Security Analysis")
    assert runner.generate_markdown(attack).startswith("# Email Security Analysis")


def test_report_names_avoid_duplicates_and_reserved_aggregate(tmp_path):
    paths = [tmp_path / name for name in ("a/same.eml", "b/same.eml", "results.eml", "simple.eml")]
    names = runner.report_basenames(paths, tmp_path)
    assert len(set(names.values())) == len(paths)
    assert "results" not in names.values()
    assert names[paths[-1]] == "simple"
    assert names == runner.report_basenames(paths, tmp_path)
