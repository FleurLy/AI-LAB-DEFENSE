from __future__ import annotations

import importlib.util
import os
from functools import lru_cache
from pathlib import Path
from types import ModuleType
from typing import Any


def _default_tools_path() -> Path:
    return Path(__file__).resolve().parents[5] / "agent" / "tools.py"


@lru_cache(maxsize=1)
def _load_tools_module() -> ModuleType:
    path = Path(os.getenv("AGENT_TOOLS_PATH", str(_default_tools_path()))).resolve()
    if not path.is_file():
        raise RuntimeError(f"Security tools module not found: {path}")
    spec = importlib.util.spec_from_file_location("ai_defense_security_tools", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load security tools module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def analyze_with_security_tools(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    module = _load_tools_module()
    analyzer = getattr(module, "run_security_tools", None)
    if not callable(analyzer):
        raise RuntimeError("agent/tools.py must expose run_security_tools")
    results = analyzer(payload)
    if not isinstance(results, dict):
        raise RuntimeError("Security tools returned an invalid result")
    return results


def warm_security_tools() -> None:
    """Load the persisted ML model during service startup, before requests arrive."""

    module = _load_tools_module()
    get_model = getattr(module, "get_model", None)
    if not callable(get_model):
        raise RuntimeError("agent/tools.py must expose get_model")
    get_model()
