# Ousmane LLM — email security classification

Consumes one normalized JSON from `extraction/`, analyzes it through
[AutoAgent](https://github.com/laazizi/autoagent) and local Qwen 3.5, then writes one English classification JSON.

The normalized email first passes through the five deterministic checks in
`../../agent/tools.py`. AutoAgent receives their scores and flags together with
the original normalized evidence; tool scores support the decision but never
override contradictory evidence automatically.

## Docker: start in one command

Requirements: Docker Desktop with at least 6 GB available memory. From this directory:

```bash
cp .env.example .env
docker compose up --build
```

The first start downloads `qwen3.5:4b` (about 3.4 GB), so it can take several minutes.
The API is then available at `http://localhost:8000`.

## Analyze an extraction JSON

Install the small Python client locally once:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Analyze one email produced by `extraction/`:

```bash
python -m ousmane_llm analyze \
  ../../extraction/data/normalized/mail_000001.json
```

The complete result is written to:

```text
data/results/mail_000001.result.json
```

Analyze every normalized email:

```bash
python -m ousmane_llm analyze-folder ../../extraction/data/normalized/
```

## API

Health and active model:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/model
```

Analyze a JSON directly:

```bash
curl -X POST http://localhost:8000/analyze \
  -H 'Content-Type: application/json' \
  --data-binary @../../extraction/data/normalized/mail_000001.json
```

## Change the model

Edit `.env` and restart:

```env
LLM_MODEL=qwen3.5:2b
```

```bash
docker compose down
docker compose up --build
```

Other Ollama models with tool support can be tested the same way. No cloud API key is required.

`LLM_THINK=false` keeps Qwen's extended reasoning disabled for this constrained,
structured classification task. Set it to `true` only if extra latency is acceptable.

## Apple Silicon with 8 GB RAM

`qwen3.5:4b` is the default. If Docker is too slow, use `qwen3.5:2b`, or run
Ollama natively (better Metal acceleration):

```bash
ollama pull qwen3.5:4b
ollama serve
```

Keep `LLM_BASE_URL=http://localhost:11434/v1` for the local CLI. The Docker API
uses the Compose Ollama service automatically.

## Tests

```bash
pip install -e '.[dev]'
pytest
```

The unit tests mock inference. To run the real Ollama/Qwen integration test:

```bash
RUN_OLLAMA_INTEGRATION=1 pytest -m integration -v
```

## Security design

- Email and attachment content enters AutoAgent through an `untrusted=True` tool.
- The same evidence is evaluated by all five local Python checks in `agent/tools.py`.
- The model has no browser, shell, filesystem, URL-fetching, or malware-execution tool.
- Output is submitted through a strict Pydantic-backed tool and validated again by the host.
- One controlled repair is allowed for malformed model output.
- Oversized untrusted text is truncated while authentication, sender, URL metadata, and technical signals are preserved.
- Output strings, explanations, and reasons are required to be in English by the system prompt.

Stop the services with:

```bash
docker compose down
```
