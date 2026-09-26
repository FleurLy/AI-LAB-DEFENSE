# Email social-engineering analysis API

A small FastAPI backend that validates a structured email payload and runs two
LangChain analyzers through OpenRouter in parallel. It returns both validated
security assessments for comparison. This first version provides the inference
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
configuration and both analyzers are cached. Credentials are never hardcoded.

| Variable | Default | Purpose |
| --- | --- | --- |
| `OPENROUTER_API_KEY` | Empty | Required for real analysis; stored as a Pydantic `SecretStr`. |
| `LLM_PROVIDER` | `openrouter` | Provider selection; OpenRouter is the implemented adapter. |
| `LLM_MODEL` | `google/gemma-4-26b-a4b-it:free` | First OpenRouter model ID, using the original prompt. |
| `JEV_MODEL` | `typesafe/jev-router` | Second OpenRouter model ID, using the Jev prompt. |
| `LLM_TEMPERATURE` | `0` | Sampling temperature, from 0 to 2; must be supported by the chosen model. |
| `LLM_TIMEOUT_SECONDS` | `30` | Positive timeout applied independently to each analysis and provider call. |
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
    analysis.py                 # AI result, enums, evidence and probabilities
    comparison.py               # Two model outcomes with model IDs and status
  analyzers/
    base.py                     # EmailAnalyzer protocol
    providers.py                # LangChain provider construction
    llm.py                      # Async structured-output integration
    jev.py                      # Jev chat analyzer with a dedicated prompt
  services/
    analysis_service.py         # Single analyzer invocation and timeout
    comparison_service.py       # Concurrent calls and independent error handling
  prompts/
    email_analysis.py           # Shared security prompt and request serialization
    jev_analysis.py             # Dedicated Jev assessment prompt
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

Request flow: FastAPI route → `ComparisonService` → two concurrent
`AnalysisService` calls → `LLMEmailAnalyzer` / `JevEmailAnalyzer` → LangChain
`ChatOpenAI` → OpenRouter. Each analyzer receives an independent copy of the same
validated input and returns `AIAnalysisResult`. Routes contain no inference logic;
OpenRouter configuration stays in the settings and provider factory.

`POST /analyze` now returns `AnalysisComparisonResult` instead of a single
`AIAnalysisResult`. Each named entry contains its configured model ID, a status,
and either the full analysis or a sanitized error. Successful response shape
(`result` objects abbreviated):

```text
{
  "llm": {"status": "success", "model": "<LLM_MODEL>", "result": {...}},
  "jev": {"status": "success", "model": "<JEV_MODEL>", "result": {...}}
}
```

The `llm` entry uses the original prompt and `LLM_MODEL`; `jev` uses its dedicated
prompt and `JEV_MODEL`. These are independent assessments, not successive stages.
Each request attempts two provider calls; their outputs are kept separate without
averaging scores. The two IDs may be identical if comparing prompts on one model.
Swagger at `/docs` describes the complete response schema.

`LLMEmailAnalyzer` receives a LangChain chat model and calls
`with_structured_output(AIAnalysisResult, method="json_schema", strict=True)`
followed by asynchronous `ainvoke`. The same result model defines FastAPI's
response schema and the model's output contract. There is no manual JSON parsing
of model responses. See the [LangChain integration documentation](https://docs.langchain.com/oss/python/integrations/chat/openai)
and [OpenRouter structured-output documentation](https://openrouter.ai/docs/guides/features/structured-outputs).

Only `langchain-core` and `langchain-openai` are needed for this pipeline; the
umbrella package, LangGraph, and agents are not required. The OpenAI SDK is listed
explicitly because LangChain uses it for OpenRouter's OpenAI-compatible API, and
its exception types are used for error handling.

To use another LangChain provider, extend the allowed setting values and
`create_chat_model`. The analyzer accepts an injected `BaseChatModel`, with an
optional structured-output method for providers that use function calling. Adapt
provider-specific exception translation when adding that integration.

The factory can create either configured chat model:

```python
from app.analyzers.jev import JevEmailAnalyzer
from app.analyzers.providers import create_chat_model
from app.core.config import get_settings

settings = get_settings()
llm_model = create_chat_model(settings)                   # LLM_MODEL
jev_model = create_chat_model(settings, model_type="jev")  # JEV_MODEL
jev_analyzer = JevEmailAnalyzer(jev_model)
# result = await jev_analyzer.analyze(payload)
```

Both selections use OpenRouter, its API key, attribution headers, temperature,
and timeout. The configured defaults are used when model variables are absent;
explicit empty values are rejected. `/analyze` prepares both analyzers before
making provider calls. Here, `JEV_MODEL` names a second chat model; it does not
implement a separate Jev inference engine.

`JevEmailAnalyzer` uses a dedicated prompt to compare claimed identity, requested
actions and technical evidence, including conflicting signals and benign
explanations. It inherits async execution, structured-output validation and error
handling from `LLMEmailAnalyzer`; both return the same `AIAnalysisResult`.
The complete payload is serialized with the original JSON field names, and shared
security instructions treat embedded email content as untrusted evidence.

The dependency layer creates and caches both analyzers: `get_analyzer` uses
`LLM_MODEL`, and `get_jev_analyzer` uses `JEV_MODEL`. `get_comparison_service` wires
them into the comparison service through the `EmailAnalyzer` protocol.
A separate native Jev engine could still be implemented as another adapter once
its official API/client is available; this implementation uses LangChain/OpenRouter.

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
| `200` | Both attempts completed; inspect each entry's `status`, including when both failed. |
| `422` | Invalid request; `detail` lists field locations and validation messages without echoing input values. |
| `503` | Missing or invalid configuration before analysis starts, including an empty model ID or absent API key. |

A failure during inference affects only that model's entry. Its successful peer's
result is preserved. For example, a timeout produces this entry:

```json
{
  "status": "error",
  "model": "provider/model",
  "error": {
    "code": "analysis_timeout",
    "message": "The email analysis timed out. Try again later.",
    "status_code": 504
  }
}
```

Within each entry, `error.status_code` describes the failure: `503` for rejected
credentials or permissions, `502` for provider or structured-output failures,
`504` for a timeout, and `500` for an unexpected analyzer error. The comparison
response itself remains HTTP `200`, even if both entries have `status="error"`.
Each analysis has its own timeout; cancellation of the comparison cancels both
pending tasks. Clients must inspect both statuses before reading `result`.

Configuration errors before execution retain the
`{"detail": {"code": "...", "message": "..."}}` response format. All error messages
are fixed public messages. Provider exception details, credentials, and raw model
responses are not returned. Automatic provider retries are disabled.

## Tests and remaining work

```bash
python -m pytest -q
```

Tests cover the exact example, field preservation, required and nullable fields,
empty lists, probability bounds, the two-result API response, configuration errors,
provider failures, partial success, independent timeouts, and cancellation.
Concurrency tests verify that both calls start before either completes and that
an analyzer cannot modify the other's payload. A simulated HTTP transport also
exercises the complete two-model route and real LangChain structured parsing
through the configured OpenRouter adapter.
Provider tests cover environment settings, optional headers, rejection of legacy
credentials, and sanitization of errors containing credentials or email content.
No test needs an API key or calls a live LLM. Tests ignore local `.env` files and
disable tracing.

Remaining work: assess both analyzers on labeled emails and calibrate
probabilities before using them for
automated decisions. A live provider smoke test requires your API key and a model
available to your account.
