#!/usr/bin/env python3
"""Replay the .eml dataset through SMTP, then analyze each normalized email."""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import re
import subprocess
import sys
import time
from email import policy
from email.parser import BytesParser
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
EXTRACTION_ROOT = ROOT.parent / "extraction"


def wait_for_normalized(
    directory: Path,
    previous: set[Path],
    expected_raw: bytes,
    timeout: float,
    poll_interval: float = 0.2,
) -> tuple[Path, dict]:
    """Match a new JSON to the bytes sent by replay.py, ignoring late other emails."""
    deadline = time.monotonic() + timeout
    expected_hash = hashlib.sha256(expected_raw).digest()
    while True:
        for path in sorted(set(directory.glob("*.json")) - previous):
            # The SMTP pipeline writes raw/<id>.eml before normalized/<id>.json.
            raw_path = directory.parent / "raw" / path.with_suffix(".eml").name
            try:
                raw = raw_path.read_bytes()
            except FileNotFoundError:
                continue
            if hashlib.sha256(raw).digest() != expected_hash:
                continue
            payload = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise ValueError(f"Normalized JSON must be an object: {path}")
            return path, payload
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("No new normalized JSON matching this email before the deadline")
        time.sleep(min(poll_interval, remaining))


def save_results(path: Path, results: list[dict] | dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def load_manifest_labels(root: Path) -> dict[Path, str]:
    """Load ground-truth labels without adding them to the analyzed payload."""
    labels: dict[Path, str] = {}
    for manifest in sorted(root.resolve().rglob("manifest.csv")):
        with manifest.open(newline="", encoding="utf-8-sig") as stream:
            for row in csv.DictReader(stream):
                file_path = (row.get("file_path") or "").strip()
                raw_label = (row.get("label_name") or row.get("label") or "").strip().casefold()
                if not file_path:
                    continue
                if raw_label in {"safe", "benign", "0"}:
                    label = "benign"
                elif raw_label in {"phishing", "suspicious", "1"}:
                    label = "suspicious"
                else:
                    continue
                labels[(manifest.parent / file_path).resolve()] = label
    return labels


def expected_classification(
    sample: Path, manifest_labels: dict[Path, str] | None = None,
) -> str | None:
    """Resolve a path label first, then fall back to a dataset manifest."""
    parts = {part.casefold() for part in sample.parts}
    if "benign" in parts:
        return "benign"
    if "suspicious" in parts:
        return "suspicious"
    return (manifest_labels or {}).get(sample.resolve())


def classification_success(
    result: dict, sample: Path, manifest_labels: dict[Path, str] | None = None,
) -> bool | None:
    expected = expected_classification(sample, manifest_labels)
    attack_type = (result.get("analysis") or {}).get("attack_type")
    if expected is None:
        return None
    if not isinstance(attack_type, str):
        return False
    predicted_benign = attack_type.strip().casefold() == "none"
    return predicted_benign if expected == "benign" else not predicted_benign


def generate_markdown(result: dict, success: bool | None = None) -> str:
    """Render only facts present in the final API JSON, without model calls."""
    def text(value: object) -> str:
        # Render email-derived text literally, including HTML and Markdown syntax.
        escaped = html.escape(str(value), quote=False)
        return re.sub(r"([\\`*_{}\[\]()#+!|>~-])", r"\\\1", escaped)

    def bullet(label: str, value: object) -> str:
        return f"- {label}: {text(value)}".replace("\n", "\n  ")

    analysis = result.get("analysis") or {}
    report = result.get("report") or {}
    lines = []
    if success is not None:
        lines.extend([f"# {'SUCCESS' if success else 'FAIL'}", ""])
    lines.append("# Email Security Analysis")
    overview = [
        ("Analysis approach", result.get("approach")),
        ("Social engineering probability", analysis.get("social_engineering_probability")),
        ("Phishing probability", analysis.get("phishing_probability")),
        ("Attack type", analysis.get("attack_type")),
        ("Requested action", analysis.get("requested_action")),
    ]
    present = [bullet(label, value) for label, value in overview if value is not None]
    if present:
        lines.extend(["", "## Overview", "", *present])
    if report.get("summary") is not None:
        lines.extend(["", "## Summary", "", text(report["summary"])])
    if analysis.get("evidence"):
        lines.extend(["", "## Evidence"])
        for index, item in enumerate(analysis["evidence"], 1):
            lines.extend(["", f"### Evidence {index}", ""])
            for key in ("type", "severity", "confidence", "description", "source"):
                if item.get(key) is not None:
                    lines.append(bullet(key.capitalize(), item[key]))
    if report.get("risk_explanation") is not None:
        lines.extend(["", "## Risk explanation", "", text(report["risk_explanation"])])
    if report.get("recommended_actions"):
        lines.extend(["", "## Recommended actions", ""])
        lines.extend(
            "- " + text(action).replace("\n", "\n  ")
            for action in report["recommended_actions"]
        )
    return "\n".join(lines) + "\n"


def report_basenames(files: list[Path], samples: Path) -> dict[Path, str]:
    """Keep sample names, disambiguating duplicates and the reserved results.json."""
    names: dict[Path, str] = {}
    used = {"results"}
    for sample in files:
        name = sample.stem
        if name.casefold() in used:
            suffix = hashlib.sha256(sample.relative_to(samples).as_posix().encode()).hexdigest()[:12]
            name = f"{sample.stem}-{suffix}"
            while name.casefold() in used:
                name += "-1"
        used.add(name.casefold())
        names[sample] = name
    return names


def discover_eml_files(root: Path, generated_data_dir: Path) -> list[Path]:
    """Find every source EML while excluding SMTP outputs under data/."""
    root = root.resolve()
    generated_data_dir = generated_data_dir.resolve()
    return sorted(
        path for path in root.rglob("*.eml")
        if not path.is_relative_to(generated_data_dir)
    )


def run_dataset(
    samples: Path,
    data_dir: Path,
    replay_script: Path,
    client: httpx.Client,
    *,
    api_url: str = "http://127.0.0.1:8000/analyze",
    smtp_host: str = "localhost",
    smtp_port: int = 1025,
    replay_timeout: float = 60,
    normalization_timeout: float = 60,
) -> list[dict]:
    files = discover_eml_files(samples, data_dir)
    basenames = report_basenames(files, samples.resolve())
    manifest_labels = load_manifest_labels(EXTRACTION_ROOT)
    normalized = data_dir.resolve() / "normalized"
    output = ROOT / "data" / "results" / "results.json"
    results: list[dict] = []
    save_results(output, results)

    for index, sample in enumerate(files, 1):
        print(f"[{index}/{len(files)}] {sample.relative_to(samples.resolve())}", flush=True)
        started = time.monotonic()
        row = {
            "sample_path": str(sample),
            "normalized_path": None,
            "normalized_json": None,
            "api_status_code": None,
            "api_response": None,
            "errors": [],
        }
        stage = "replay"
        try:
            # Same serialization as replay.py; never modify the source email.
            message = BytesParser(policy=policy.default).parsebytes(sample.read_bytes())
            expected_raw = message.as_bytes(policy=policy.SMTP)
            # smtplib.DATA adds a final CRLF when the serialized body lacks one.
            if not expected_raw.endswith(b"\r\n"):
                expected_raw += b"\r\n"
            previous = set(normalized.glob("*.json"))
            replay = subprocess.run(
                [sys.executable, str(replay_script.resolve()), str(sample),
                 "--host", smtp_host, "--port", str(smtp_port)],
                cwd=replay_script.resolve().parents[1],
                capture_output=True, text=True, errors="replace", timeout=replay_timeout,
            )
            if replay.returncode:
                detail = (replay.stderr or replay.stdout).strip()[-4000:]
                raise RuntimeError(f"replay.py exited with code {replay.returncode}: {detail}")

            stage = "normalization"
            path, payload = wait_for_normalized(
                normalized, previous, expected_raw, normalization_timeout,
            )
            row["normalized_path"] = str(path)
            row["normalized_json"] = payload

            stage = "api"
            response = client.post(api_url, json=payload)
            row["api_status_code"] = response.status_code
            try:
                row["api_response"] = response.json()
            except ValueError:
                row["api_response"] = response.text
                raise ValueError("Analysis API returned a non-JSON response") from None
            response.raise_for_status()

            stage = "report_export"
            result = row["api_response"]
            markdown = generate_markdown(result, classification_success(result, sample, manifest_labels))
            basename = basenames[sample]
            save_results(output.parent / f"{basename}.json", result)
            markdown_path = output.parent / f"{basename}.md"
            temporary = markdown_path.with_suffix(".md.tmp")
            temporary.write_text(markdown, encoding="utf-8")
            temporary.replace(markdown_path)
        except Exception as exc:
            row["errors"].append({
                "stage": stage, "type": type(exc).__name__, "message": str(exc),
            })
        row["duration_seconds"] = round(time.monotonic() - started, 3)
        results.append(row)
        # Persist progress after every sample, including failures.
        save_results(output, results)
        status = f"ERROR ({row['errors'][0]['stage']})" if row["errors"] else "OK"
        print(f"  {status} — {row['duration_seconds']}s", flush=True)

    failures = sum(bool(row["errors"]) for row in results)
    print(f"Completed: {len(results) - failures} OK, {failures} failed. Results: {output}")
    return results


def positive_seconds(value: str) -> float:
    import math

    seconds = float(value)
    if not math.isfinite(seconds) or seconds <= 0:
        raise argparse.ArgumentTypeError("Timeout must be a finite positive number")
    return seconds


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=Path, default=EXTRACTION_ROOT)
    parser.add_argument("--data-dir", type=Path, default=EXTRACTION_ROOT / "data")
    parser.add_argument("--api-url", default="http://127.0.0.1:8000/analyze")
    parser.add_argument("--smtp-host", default="localhost")
    parser.add_argument("--smtp-port", type=int, default=1025)
    parser.add_argument("--replay-timeout", type=positive_seconds, default=60)
    parser.add_argument("--normalization-timeout", type=positive_seconds, default=60)
    parser.add_argument("--api-timeout", type=positive_seconds, default=120)
    args = parser.parse_args()
    if not args.samples.is_dir():
        parser.error(f"Samples directory does not exist: {args.samples}")
    replay_script = EXTRACTION_ROOT / "scripts" / "replay.py"
    with httpx.Client(timeout=args.api_timeout) as client:
        results = run_dataset(
            args.samples, args.data_dir, replay_script, client,
            api_url=args.api_url, smtp_host=args.smtp_host, smtp_port=args.smtp_port,
            replay_timeout=args.replay_timeout,
            normalization_timeout=args.normalization_timeout,
        )
    return 1 if any(row["errors"] for row in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
