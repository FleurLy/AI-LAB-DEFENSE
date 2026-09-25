from __future__ import annotations

from pathlib import Path

from ousmane_llm.schemas.output import EmailAnalysis


class ResultWriter:
    def __init__(self, results_dir: Path):
        self.results_dir = results_dir
        self.results_dir.mkdir(parents=True, exist_ok=True)

    def write(self, internal_id: str, analysis: EmailAnalysis) -> Path:
        safe_id = "".join(char for char in internal_id if char.isalnum() or char in {"-", "_"})
        if not safe_id:
            raise ValueError("Invalid internal email ID")
        target = self.results_dir / f"{safe_id}.result.json"
        temporary = target.with_suffix(".json.tmp")
        temporary.write_text(analysis.model_dump_json(indent=2), encoding="utf-8")
        temporary.replace(target)
        return target

