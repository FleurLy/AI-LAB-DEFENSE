# AI-LAB-DEFENSE

AI-LAB-DEFENSE is an end-to-end email security pipeline that detects phishing,
social engineering, suspicious links, and malicious attachments.

The platform converts a raw email into structured evidence, enriches it with
deterministic security checks and a trained TF-IDF classifier, and asks a local
AutoAgent/Qwen model for an actionable decision. An optional Jev/GPT cloud path
can generate a more detailed report without delaying the primary local verdict.

## Key features

- SMTP ingestion of real `.eml` files.
- Safe MIME parsing and normalized JSON generation.
- Passive PDF, image, Office document, URL, and QR-code extraction.
- SPF, DKIM, DMARC, sender, Reply-To, and technical-signal inspection.
- Five deterministic Python security tools plus a local TF-IDF model.
- Fast local decision with AutoAgent and Qwen through Ollama.
- Optional Jev/GPT report through OpenRouter.
- Strict structured output with a verdict, risk score, explanation, and action.
- Docker-based startup and reproducible demo scripts.

## Architecture

```text
Raw email (.eml)
        │
        ▼
SMTP ingestion and extraction                         port 1025
        │
        ├── MIME content and headers
        ├── URLs and QR codes
        ├── attachments and OCR
        └── authentication and technical signals
        │
        ▼
Normalized evidence JSON
        │
        ▼
Deterministic security tools + TF-IDF classifier
        │
        ▼
AutoAgent + local Qwen                                port 8000
        │
        └── immediate security verdict
                │
                └── optional Jev → GPT report         port 8001
```

The local decision path is the main product path. It does not require a cloud
API key. The Jev/GPT report is started and called only when `--report` is
explicitly requested.

## Requirements

- Docker Desktop with Docker Compose
- Ollama installed on the host
- At least 6 GB of available memory recommended
- An OpenRouter API key only for the optional report

Install Ollama on macOS:

```bash
brew install ollama
```

On Linux:

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

## Quick start

Clone the repository, enter its root directory, and run:

```bash
./start.sh
```

The script starts Ollama when necessary, downloads `qwen2.5:3b` if it is
missing, starts the Docker services, and waits until they are actually ready.

Available services:

| Service | Address | Purpose |
| --- | --- | --- |
| SMTP ingestion | `localhost:1025` | Receives and normalizes email |
| AutoAgent API | `http://localhost:8000` | Returns the primary local verdict |
| Jev/GPT report | `http://localhost:8001` | Optional detailed cloud report |

### Enable the optional report

```bash
cp llm/.env.example llm/.env
```

Set `OPENROUTER_API_KEY` in `llm/.env`, then run:

```bash
./start.sh --report
```

Do not commit `llm/.env`; it may contain credentials.

## Jury demonstration

The guided demo pauses between each stage so the presenter can explain what is
happening.

Phishing example with the optional report:

```bash
./demo.sh --report 8
```

Benign example:

```bash
./demo.sh --report 1
```

Run the demo without pauses:

```bash
DEMO_NO_PAUSE=1 ./demo.sh --report 8
```

The demo shows, in order:

1. The raw email and its normalized evidence.
2. The deterministic tools and TF-IDF model findings.
3. The local AutoAgent/Qwen verdict and processing time.
4. The optional Jev/GPT report and processing time.

All terminal messages and model-facing output used during the demonstration are
in English.

## Analyze an email

Analyze a validation-dataset email by ID:

```bash
./analyze_mail.sh 8
```

Analyze an `.eml` file:

```bash
./analyze_mail.sh extraction/samples/suspicious/phishing_link.eml
```

Analyze an existing normalized JSON file:

```bash
./analyze_mail.sh extraction/data/normalized/mail_000001.json
```

Request the optional detailed report:

```bash
./analyze_mail.sh --report 8
```

Search and inspect the validation dataset:

```bash
./analyze_mail.sh search paypal
./analyze_mail.sh list phishing
./analyze_mail.sh list safe
```

Without `--report`, no OpenRouter request is made and no cloud-report latency is
added to the AutoAgent response.

## API usage

Check the local service:

```bash
curl http://localhost:8000/health
```

Analyze normalized evidence directly:

```bash
curl --fail-with-body http://localhost:8000/analyze \
  -H 'Content-Type: application/json' \
  --data-binary @extraction/data/normalized/mail_000001.json
```

Example response:

```json
{
  "verdict": "malicious",
  "risk_score": 80,
  "explanation": "The sender failed authentication checks and requests credentials through a suspicious link.",
  "recommended_action": "quarantine"
}
```

Possible verdicts and normal actions:

| Verdict | Risk interpretation | Typical action |
| --- | --- | --- |
| `benign` | Low risk | `allow` |
| `suspicious` | Uncertain or conflicting evidence | `human_review` |
| `malicious` | Strong phishing or fraud evidence | `quarantine` |

Risk scores range from `0` to `100`. The final action is schema-validated for
consistency with the verdict.

## How the security decision works

The extraction service first creates factual evidence without assigning a final
verdict. The tools in `agent/tools.py` then evaluate:

1. Sender identity and authentication.
2. Recipient patterns.
3. URL domains and obfuscation signals.
4. Attachment names and security metadata.
5. Subject and body content with the trained TF-IDF classifier.

AutoAgent receives both the normalized email and these findings as untrusted
evidence. Tool scores support the decision but do not automatically override
contradictory evidence.

## Security design

- Email text, attachment text, and URLs are treated as untrusted input.
- The agent cannot browse links, execute attachments, or use a shell.
- Attachments are inspected passively; embedded code is never executed.
- URLs are extracted and analyzed but never opened.
- Model output is validated against a strict schema.
- Oversized text is truncated while important technical evidence is retained.
- A malformed local-model response receives at most one controlled repair.
- GPT receives the structured Jev decision for reporting, not the original email.
- API keys belong only in ignored `.env` files.

## Project structure

```text
AI-LAB-DEFENSE/
├── agent/                    # Deterministic tools and trained TF-IDF classifier
├── extraction/               # SMTP ingestion, parsing, OCR, and normalization
├── llm/
│   ├── Ousmane-llm/          # Local AutoAgent/Qwen decision service
│   └── app/                  # Optional Jev/GPT report service
├── analyze_mail.sh           # End-to-end analysis command
├── auto_analyze.sh           # Watches and analyzes newly normalized emails
├── demo.sh                   # Guided jury demonstration
├── start.sh                  # Platform startup and readiness checks
├── docker-compose.yml        # Root service orchestration
├── PRESENTATION.md           # Presentation script and speaking notes
└── README.md                 # Project overview and operating guide
```

## Tests

Each component has its own test suite.

Extraction pipeline:

```bash
cd extraction
python -m pytest -q
```

Local AutoAgent service:

```bash
cd llm/Ousmane-llm
python -m pytest -q
```

Optional Jev/GPT service:

```bash
cd llm
python -m pytest -q
```

The unit tests mock external inference where appropriate, so normal test runs do
not consume an OpenRouter key.

## Documentation

- [Presentation script and demo flow](PRESENTATION.md)
- [Extraction service guide](extraction/README.md)
- [Extraction technical specification](extraction/email_security_pipeline_spec.md)
- [Local AutoAgent/Qwen guide](llm/Ousmane-llm/README.md)
- [Optional Jev/GPT backend guide](llm/README.md)

Additional supporting documents, diagrams, evaluation results, or jury material
can be added to this section without changing the application.

## Stop the platform

```bash
docker compose --profile report down
```

## Current scope

This repository is a hackathon/MVP implementation. It demonstrates a complete,
testable analysis flow but is not a replacement for a production secure email
gateway. Production deployment would still require authentication, rate limits,
monitoring, calibrated evaluation on a larger labeled dataset, and hardened
secret management.
