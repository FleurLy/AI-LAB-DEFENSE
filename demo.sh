#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

WITH_REPORT=false
EMAIL_ID="8"

if [ "${1:-}" = "--report" ]; then
    WITH_REPORT=true
    shift
fi
if [ -n "${1:-}" ]; then
    EMAIL_ID="$1"
fi

if [[ "$EMAIL_ID" =~ ^[0-9]+$ ]]; then
    EMAIL_STEM=$(printf "mail_%06d" "$EMAIL_ID")
elif [[ "$EMAIL_ID" =~ ^mail_[0-9]+$ ]]; then
    EMAIL_STEM="$EMAIL_ID"
else
    echo "Usage: $0 [--report] [number | mail_XXXXXX]"
    exit 1
fi

EML_FILE="extraction/datasets/phishing_validation/emails/${EMAIL_STEM}.eml"
NORMALIZED_DIR="extraction/data/normalized"
AUTOAGENT_URL="http://localhost:8000/analyze"
REPORT_URL="http://localhost:8001/analyze"
if [ -z "${PYTHON_BIN:-}" ]; then
    if [ -x /opt/homebrew/bin/python3 ]; then
        PYTHON_BIN=/opt/homebrew/bin/python3
    else
        PYTHON_BIN=python3
    fi
fi

pause_demo() {
    if [ "${DEMO_NO_PAUSE:-0}" != "1" ] && [ -t 0 ]; then
        printf "\nPress Enter to continue..."
        read -r _
    fi
}

pretty_json() {
    if command -v jq >/dev/null 2>&1; then
        jq .
    else
        "$PYTHON_BIN" -m json.tool
    fi
}

section() {
    printf '\n============================================================\n'
    printf '%s\n' "$1"
    printf '============================================================\n'
}

if [ ! -f "$EML_FILE" ]; then
    echo "Demo email not found: $EML_FILE"
    exit 1
fi
if ! curl -s --max-time 2 http://localhost:8000/health >/dev/null; then
    echo "AutoAgent is not ready. Run: ./start.sh"
    [ "$WITH_REPORT" = false ] || echo "For the complete demo, run: ./start.sh --report"
    exit 2
fi
if ! (exec 3<>/dev/tcp/127.0.0.1/1025) 2>/dev/null; then
    echo "The SMTP service is not ready. Run: ./start.sh"
    [ "$WITH_REPORT" = false ] || echo "For the complete demo, run: ./start.sh --report"
    exit 2
fi
if [ "$WITH_REPORT" = true ] && ! curl -s --max-time 2 http://localhost:8001/health >/dev/null; then
    echo "The Jev/GPT report service is not ready. Run: ./start.sh --report"
    exit 2
fi

section "1/4 — Raw email and normalized extraction"
echo "Source: $EML_FILE"
echo "Visible headers:"
awk 'NR > 18 { exit } { print } /^$/ { exit }' "$EML_FILE"
pause_demo

PREVIOUS_LATEST="$(ls -t "$NORMALIZED_DIR"/mail_*.json 2>/dev/null | head -n 1 || true)"
"$PYTHON_BIN" extraction/scripts/replay.py "$EML_FILE" >/dev/null

JSON_FILE=""
for _ in {1..40}; do
    CURRENT_LATEST="$(ls -t "$NORMALIZED_DIR"/mail_*.json 2>/dev/null | head -n 1 || true)"
    if [ -n "$CURRENT_LATEST" ]; then
        JSON_FILE="$CURRENT_LATEST"
        if [ "$CURRENT_LATEST" != "$PREVIOUS_LATEST" ]; then
            break
        fi
    fi
    sleep 0.1
done
if [ -z "$JSON_FILE" ]; then
    echo "No normalized JSON file was produced."
    exit 3
fi

echo "Generated JSON: $JSON_FILE"
if command -v jq >/dev/null 2>&1; then
    jq '{
      id: .email.internal_id,
      from: .email.from,
      subject: .email.subject,
      authentication,
      technical_signals,
      url_count: (.urls | length),
      attachment_count: (.attachments | length)
    }' "$JSON_FILE"
else
    "$PYTHON_BIN" -m json.tool "$JSON_FILE" | head -n 60
fi
pause_demo

section "2/4 — Deterministic security tools and ML model"
JSON_BASENAME="$(basename "$JSON_FILE")"
docker compose exec -T ousmane-llm python -c '
import json, sys
from pathlib import Path
from ousmane_llm.services.security_tools import analyze_with_security_tools
payload = json.loads((Path("/input") / sys.argv[1]).read_text())
print(json.dumps(analyze_with_security_tools(payload), indent=2, ensure_ascii=False))
' "$JSON_BASENAME" | pretty_json
pause_demo

section "3/4 — Fast verdict from AutoAgent + local Qwen"
AUTO_RESPONSE="$(mktemp)"
REPORT_RESPONSE=""
trap 'rm -f "$AUTO_RESPONSE" ${REPORT_RESPONSE:+"$REPORT_RESPONSE"}' EXIT
AUTO_TIME=$(curl -sS --fail-with-body -o "$AUTO_RESPONSE" -w '%{time_total}' \
    -X POST "$AUTOAGENT_URL" \
    -H 'Content-Type: application/json' \
    --data-binary @"$JSON_FILE")
cat "$AUTO_RESPONSE" | pretty_json
echo "AutoAgent processing time: ${AUTO_TIME}s"

if [ "$WITH_REPORT" = false ]; then
    echo ""
    echo "Jev/GPT report not requested: no OpenRouter request was made."
    echo "Run '$0 --report $EMAIL_ID' for the complete demonstration."
    exit 0
fi

pause_demo
section "4/4 — Optional Jev + GPT report"
echo "The AutoAgent verdict has already been displayed; the cloud report starts only now."
REPORT_RESPONSE="$(mktemp)"
REPORT_TIME=$(curl -sS --fail-with-body -o "$REPORT_RESPONSE" -w '%{time_total}' \
    -X POST "$REPORT_URL" \
    -H 'Content-Type: application/json' \
    --data-binary @"$JSON_FILE")
cat "$REPORT_RESPONSE" | pretty_json
echo "Jev/GPT report processing time: ${REPORT_TIME}s"

section "Demonstration complete"
echo "Fast path: extraction → security tools → AutoAgent/Qwen."
echo "Optional path: Jev → GPT, used only to generate a detailed report."
