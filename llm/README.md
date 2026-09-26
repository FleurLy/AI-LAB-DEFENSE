# Email social-engineering analysis API

A small FastAPI backend that validates a structured email payload and uses
LangChain through OpenRouter. It supports two selectable analysis approaches,
returning a validated security decision and a human-readable report. This first version provides the inference
pipeline; it does not implement a complete fraud-detection engine or calibrated
risk scoring.

## Setup

Requires Python 3.11 or newer. Run these commands from this directory:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

Set `OPENROUTER_API_KEY`, `LLM_MODEL`, and `JEV_MODEL` in `.env`, then start the API:

```bash
uvicorn app.main:app --reload
```

Swagger UI: <http://127.0.0.1:8000/docs>. Health check:

```bash
curl http://127.0.0.1:8000/health
```

Analyze the complete example supplied with the project:

```bash
curl --fail-with-body http://127.0.0.1:8000/analyze \
  -H 'Content-Type: application/json' \
  --data-binary @examples/email_analysis.json
```

## Configuration

Environment variables override `.env`. Restart the process after changing settings;
configuration and active model adapters are cached. Credentials are never hardcoded.

| Variable | Default | Purpose |
| --- | --- | --- |
| `OPENROUTER_API_KEY` | Empty | Required for real analysis; stored as a Pydantic `SecretStr`. |
| `LLM_PROVIDER` | `openrouter` | Provider selection; OpenRouter is the implemented adapter. |
| `LLM_MODEL` | `google/gemma-4-26b-a4b-it:free` | Full-analysis model, also used for reports unless overridden. Set a GPT model ID for these experiments (see `.env.example`). |
| `JEV_MODEL` | `typesafe/jev-router` | Security decision model in `jev_then_gpt`. |
| `ANALYSIS_MODE` | `gpt_only` | Validated selection: `gpt_only` or `jev_then_gpt`. |
| `REPORT_MODEL` | Empty | Report model in `jev_then_gpt`; empty or absent falls back to `LLM_MODEL`. |
| `LLM_TEMPERATURE` | `0` | Sampling temperature, from 0 to 2; must be supported by the chosen model. |
| `LLM_TIMEOUT_SECONDS` | `30` | Positive timeout applied independently to each analysis/report stage and provider call. |
| `OPENROUTER_SITE_URL` | Empty | Optional `HTTP-Referer` attribution header. |
| `OPENROUTER_APP_NAME` | Empty | Optional `X-Title` attribution header. |

The provider factory configures `ChatOpenAI` with
`base_url="https://openrouter.ai/api/v1"` and the OpenRouter key. It explicitly uses
the chat-completions endpoint. Attribution headers are sent only for nonempty
values. Remove the old OpenAI key from the application's `.env`; it is not read
or used as a fallback. If an existing `.env` sets `LLM_PROVIDER=openai`, change it
to `LLM_PROVIDER=openrouter`.

Use an OpenRouter model ID, for example
[`openai/gpt-4o-mini`](https://openrouter.ai/openai/gpt-4o-mini). Choose a model and
provider that support JSON-schema structured output; an incompatible model returns
a provider or structured-output error rather than an unvalidated analysis.

`/health` is a liveness check. It does not validate credentials or contact the
provider. The application and Swagger UI start without an API key.

## Two analysis approaches

- `ANALYSIS_MODE=gpt_only`: original email → GPT → analysis + report, in one call.
- `ANALYSIS_MODE=jev_then_gpt`: original email → Jev → structured analysis → GPT → report.

Both return `{ "analysis": {...}, "report": {...}, "approach": "..." }`.
`SecurityAnalysis` contains the ten probabilities, attack type, requested action,
and evidence. `SecurityReport` contains `summary`, `risk_explanation`, and
`recommended_actions`. In Jev mode, GPT receives **only** the structured decision,
never the original email. Its dedicated prompt prohibits reclassification or new
conclusions; its output schema contains report fields only. The service preserves
Jev's decision unchanged. There is no automatic fallback between modes.
Change `ANALYSIS_MODE` in `.env` and restart the API to switch approaches.

## Architecture

```text
app/
  main.py                       # App factory and sanitized exception handlers
  api/
    routes.py                   # GET /health and POST /analyze
    dependencies.py             # Analyzer and service wiring
  core/
    config.py                   # Environment settings
    errors.py                   # Public analysis errors
  models/
    base.py                     # Shared Pydantic configuration
    email.py                    # Complete nested request schema
    analysis.py                 # Decision, report, common result, enums and evidence
    comparison.py               # Legacy standalone comparison schemas
  analyzers/
    base.py                     # Analyzer and report protocols
    providers.py                # LangChain provider construction
    llm.py                      # Async structured-output integration
    jev.py                      # Jev security decision
    gpt.py                      # GPT decision + report in one call
    report.py                   # Report from a completed decision
  services/
    analysis_service.py         # Mode selection, stage sequencing and timeouts
    comparison_service.py       # Legacy standalone comparison utility
  prompts/
    email_analysis.py           # Shared security prompt and request serialization
    jev_analysis.py             # Dedicated Jev assessment prompt
    gpt_analysis.py             # Full GPT analysis prompt
    security_report.py          # Report-only GPT prompt
examples/
  email_analysis.json           # Exact supplied input example
tests/
  conftest.py
  test_models.py
  test_api.py
  test_analyzers.py
  test_providers.py
  test_comparison.py
.env.example
requirements.txt
pytest.ini
```

Request flow: FastAPI route → `AnalysisService` → active analyzer(s) → LangChain
`ChatOpenAI` → OpenRouter. Mode selection belongs to the service; routes contain
no inference logic. OpenRouter configuration stays in the settings and provider
factory. Swagger at `/docs` describes the common `FinalAnalysisResult` schema.

The active adapters use `with_structured_output(..., method="json_schema", strict=True)`
and asynchronous `ainvoke`: `SecurityAnalysis` for Jev, `SecurityReport` for the
report generator, and `GPTFullAnalysis` for GPT-only. There is no manual JSON
parsing of model responses. The original `LLMEmailAnalyzer`, `AIAnalysisResult`,
and standalone `ComparisonService` remain available for compatibility, but are
not used by `/analyze`. See the [LangChain integration documentation](https://docs.langchain.com/oss/python/integrations/chat/openai)
and [OpenRouter structured-output documentation](https://openrouter.ai/docs/guides/features/structured-outputs).

Only `langchain-core` and `langchain-openai` are needed for this pipeline; the
umbrella package, LangGraph, and agents are not required. The OpenAI SDK is listed
explicitly because LangChain uses it for OpenRouter's OpenAI-compatible API, and
its exception types are used for error handling.

To use another LangChain provider, extend the allowed setting values and
`create_chat_model`. The analyzer accepts an injected `BaseChatModel`, with an
optional structured-output method for providers that use function calling. Adapt
provider-specific exception translation when adding that integration.

The factory can create each configured chat model:

```python
from app.analyzers.jev import JevEmailAnalyzer
from app.analyzers.providers import create_chat_model
from app.core.config import get_settings

settings = get_settings()
llm_model = create_chat_model(settings)                   # LLM_MODEL
jev_model = create_chat_model(settings, model_type="jev")  # JEV_MODEL
report_model = create_chat_model(settings, model_type="report")  # REPORT_MODEL or LLM_MODEL
jev_analyzer = JevEmailAnalyzer(jev_model)
# result = await jev_analyzer.analyze(payload)
```

All selections use OpenRouter, its API key, attribution headers, temperature,
and timeout. Defaults are used when model variables are absent; explicit empty
`LLM_MODEL` and `JEV_MODEL` values are rejected. Only adapters required by the active
mode are constructed. `JEV_MODEL` configures a chat model, not a separate inference
engine or invented API.

`JevEmailAnalyzer` focuses on claimed identity, requested actions and technical
evidence, including conflicting signals and benign explanations. The adapters
share async execution, structured-output validation and error translation.
The complete input retains its original JSON field names, and the prompts treat
embedded email content as untrusted evidence.

The dependency layer caches active adapters. `get_analyzer` uses `LLM_MODEL`,
`get_jev_analyzer` uses `JEV_MODEL`, and `get_report_generator` uses `REPORT_MODEL`
or `LLM_MODEL`. `get_analysis_service` injects them through small protocols.

## Payload and error behavior

- Every input field is retained and required, including nullable fields. The JSON
  key `from` maps to Python's `from_` and is serialized back as `from`.
- All lists may be empty. Display names, reply-to fields, language, attachment
  text/visual descriptions, URL display text, and optional sender metadata may
  explicitly be `null`. Unknown fields are rejected at every level.
- Email addresses and URL syntax are validated. Timestamps require a timezone;
  counts and sizes are nonnegative integers; booleans must be JSON booleans.
  URL strings are preserved after validation, without URL normalization.
- Hashes remain strings so the supplied abbreviated hashes are accepted.
  Authentication statuses, extraction methods, and schema versions remain
  strings to preserve upstream vocabulary. Redundant signals and counts are
  retained without recomputing or enforcing cross-field consistency.
- All ten probabilities and evidence confidence are finite numbers in `[0, 1]`.
  The prompt requests grounded evidence and treats embedded instructions as
  untrusted email content. The complete validated payload goes to the provider;
  this backend does not fetch URLs, extract files, or persist emails.

| HTTP status | Meaning |
| --- | --- |
| `200` | Complete analysis and report, with the selected `approach`. |
| `422` | Invalid input; validation details omit input values. |
| `503` | Missing/invalid configuration or analysis-stage credential/permission failure. |
| `502` | Provider/structured-output failure, or `report_generation_error` in the report stage. |
| `504` | `analysis_timeout` or `report_generation_timeout`, depending on the stage. |
| `500` | Unexpected analysis failure. |

Errors use `{"detail": {"code": "...", "message": "..."}}`. If Jev fails, the
report stage is not called. If its report fails, the API returns a distinct report
error without redoing the decision with GPT. Each stage has its own timeout;
cancellation propagates to the pending call. All public messages are fixed:
provider details, credentials and raw model responses are not returned. Automatic
provider retries are disabled.

## Tests and remaining work

```bash
python -m pytest -q
```

Tests cover the exact example, field preservation, required and nullable fields,
empty lists, probability bounds, both modes and their common response, configuration
errors, provider failures, stage timeouts, and cancellation. They verify that the
report receives only Jev's analysis, cannot mutate the returned decision, and never
triggers fallback. Simulated HTTP transports exercise the full API and real
LangChain parsing for both modes. Existing standalone comparison tests retain
concurrency and independent-payload coverage.
Provider tests cover environment settings, optional headers, rejection of legacy
credentials, and sanitization of errors containing credentials or email content.
No test needs an API key or calls a live LLM. Tests ignore local `.env` files and
disable tracing.

Remaining work: assess both analyzers on labeled emails and calibrate
probabilities before using them for
automated decisions. A live provider smoke test requires your API key and a model
available to your account.
