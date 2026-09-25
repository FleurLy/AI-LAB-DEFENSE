#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import urllib.request


base_url = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1").rstrip("/")
model = os.getenv("LLM_MODEL", "qwen3.5:4b")
request = urllib.request.Request(
    f"{base_url}/chat/completions",
    data=json.dumps(
        {
            "model": model,
            "messages": [{"role": "user", "content": "Reply with exactly: ready"}],
            "stream": False,
        }
    ).encode(),
    headers={"Content-Type": "application/json", "Authorization": "Bearer ollama"},
)
with urllib.request.urlopen(request, timeout=180) as response:
    payload = json.load(response)
print(payload["choices"][0]["message"]["content"])

