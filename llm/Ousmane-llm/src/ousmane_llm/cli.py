from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from ousmane_llm.runtime import build_runtime


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Input JSON must contain one object")
    return value


def _print_result(internal_id: str, decision, output: Path) -> None:
    print(f"Email: {internal_id}")
    print(f"Verdict: {decision.verdict}")
    print(f"Risk score: {decision.risk_score}/100")
    print(f"Confidence: {decision.confidence:.0%}")
    print(f"Category: {decision.category}")
    print(f"Action: {decision.recommended_action}")
    print(f"Result: {output}")


def _analyze_one(path: Path, analyzer, writer) -> None:
    payload = _load_json(path)
    internal_id = str(payload.get("email", {}).get("internal_id", path.stem))
    decision = analyzer.analyze(payload)
    output = writer.write(internal_id, decision)
    logging.getLogger(__name__).info("Result written to %s", output)
    _print_result(internal_id, decision, output)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Classify normalized email JSON with a local LLM")
    subparsers = parser.add_subparsers(dest="command", required=True)
    analyze = subparsers.add_parser("analyze", help="Analyze one normalized email JSON")
    analyze.add_argument("json_file", type=Path)
    folder = subparsers.add_parser("analyze-folder", help="Analyze every JSON file in a folder")
    folder.add_argument("folder", type=Path)
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    settings, analyzer, writer = build_runtime()
    logging.basicConfig(
        level=getattr(logging, settings.log_level, logging.INFO),
        format="[%(levelname)s] %(message)s",
    )
    try:
        if args.command == "analyze":
            _analyze_one(args.json_file, analyzer, writer)
            return
        files = sorted(args.folder.glob("*.json"))
        if not files:
            raise ValueError(f"No JSON files found in {args.folder}")
        failures = 0
        for path in files:
            try:
                _analyze_one(path, analyzer, writer)
            except Exception as exc:
                failures += 1
                logging.error("Failed to analyze %s: %s", path, exc)
        print(f"Processed: {len(files) - failures}/{len(files)}")
        if failures:
            raise SystemExit(1)
    except (OSError, ValueError, json.JSONDecodeError, ValidationError) as exc:
        logging.error("%s", exc)
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()

