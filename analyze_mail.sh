#!/usr/bin/env bash
set -e

# Script d'analyse d'email de bout en bout (EML ou JSON -> LLM Security Analysis)
# Supporte les chemins de fichiers, les IDs du dataset (ex: 8 ou mail_000008), et la recherche.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

MANIFEST="extraction/datasets/phishing_validation/manifest.csv"
DATASET_DIR="extraction/datasets/phishing_validation/emails"
GENERATE_REPORT=false
REPORT_URL="${REPORT_URL:-http://localhost:8001/analyze}"
if [ -z "${PYTHON_BIN:-}" ]; then
    if [ -x /opt/homebrew/bin/python3 ]; then
        PYTHON_BIN=/opt/homebrew/bin/python3
    else
        PYTHON_BIN=python3
    fi
fi

if [ "${1:-}" = "--report" ]; then
    GENERATE_REPORT=true
    shift
fi

# Commande de recherche dans le dataset
if [ "${1:-}" = "search" ] && [ -n "${2:-}" ]; then
    QUERY="$2"
    echo "=== Dataset search for '$QUERY' ==="
    echo "ID            | LABEL    | SUBJECT"
    echo "--------------+----------+--------------------------------------------------"
    grep -i "$QUERY" "$MANIFEST" | awk -F',' '{printf "%-13s | %-8s | %s\n", $1, $5, $7}' | head -n 15
    exit 0
fi

# Commande de listing des emails du dataset
if [ "${1:-}" = "list" ]; then
    FILTER="${2:-all}"
    echo "=== Dataset samples ($FILTER) ==="
    echo "ID            | LABEL    | SUBJECT"
    echo "--------------+----------+--------------------------------------------------"
    if [ "$FILTER" = "phishing" ]; then
        grep ",phishing," "$MANIFEST" | awk -F',' '{printf "%-13s | %-8s | %s\n", $1, $5, $7}' | head -n 10
    elif [ "$FILTER" = "safe" ]; then
        grep ",safe," "$MANIFEST" | awk -F',' '{printf "%-13s | %-8s | %s\n", $1, $5, $7}' | head -n 10
    else
        awk -F',' 'NR>1 {printf "%-13s | %-8s | %s\n", $1, $5, $7}' "$MANIFEST" | head -n 15
    fi
    echo ""
    echo "To test one: ./analyze_mail.sh <ID> (e.g. ./analyze_mail.sh mail_000008 or ./analyze_mail.sh 8)"
    exit 0
fi

if [ -z "${1:-}" ]; then
    echo "Usage: $0 [--report] <file.eml | file.json | dataset ID>"
    echo ""
    echo "Useful options:"
    echo "  $0 search <keyword>      Search the email dataset (e.g. paypal, account, bank...)"
    echo "  $0 list [phishing|safe]  List sample emails from the dataset"
    echo "  $0 --report <email>      Show AutoAgent first, then generate the Jev/GPT report"
    echo ""
    echo "Examples:"
    echo "  $0 8                                                        (PayPal phishing email from the dataset)"
    echo "  $0 mail_000002                                              (Phishing email from the dataset)"
    echo "  $0 extraction/samples/suspicious/phishing_link.eml"
    echo "  $0 extraction/samples/suspicious/qr_phishing.eml"
    echo "  $0 extraction/data/normalized/mail_000001.json"
    echo "  $0 --report 8"
    exit 1
fi

INPUT_FILE="$1"

# Résolution automatique si un numéro ou un ID est passé (ex: "8" ou "mail_000008")
if [[ "$INPUT_FILE" =~ ^[0-9]+$ ]]; then
    PADDED=$(printf "mail_%06d.eml" "$INPUT_FILE")
    INPUT_FILE="$DATASET_DIR/$PADDED"
elif [[ "$INPUT_FILE" =~ ^mail_[0-9]+$ ]]; then
    INPUT_FILE="$DATASET_DIR/${INPUT_FILE}.eml"
fi

if [ ! -f "$INPUT_FILE" ]; then
    echo "[-] Error: file '$INPUT_FILE' does not exist."
    exit 1
fi

if ! curl -s --max-time 2 http://localhost:8000/health >/dev/null; then
    echo "[-] The AutoAgent API is unavailable on port 8000."
    if [ "$GENERATE_REPORT" = true ]; then
        echo "    Start the complete platform with: ./start.sh --report"
    else
        echo "    Start the platform with: ./start.sh"
    fi
    exit 2
fi

JSON_FILE=""

# Détecter si c'est un EML ou déjà un JSON
if [[ "$INPUT_FILE" == *.eml ]]; then
    if ! (exec 3<>/dev/tcp/127.0.0.1/1025) 2>/dev/null; then
        echo "[-] The SMTP extraction service is unavailable on port 1025."
        if [ "$GENERATE_REPORT" = true ]; then
            echo "    Start the complete platform with: ./start.sh --report"
        else
            echo "    Start the platform with: ./start.sh"
        fi
        exit 2
    fi

    # Snapshot du fichier le plus récent avant l'envoi
    PREV_LATEST="$(ls -t extraction/data/normalized/mail_*.json 2>/dev/null | head -n 1 || true)"
    
    echo "[*] Sending file through SMTP ingestion: $INPUT_FILE"
    "$PYTHON_BIN" extraction/scripts/replay.py "$INPUT_FILE" > /dev/null
    
    # Attendre que le JSON normalisé apparaisse
    for _ in {1..20}; do
        CURR_LATEST="$(ls -t extraction/data/normalized/mail_*.json 2>/dev/null | head -n 1 || true)"
        if [ -n "$CURR_LATEST" ] && [ "$CURR_LATEST" != "$PREV_LATEST" ]; then
            JSON_FILE="$CURR_LATEST"
            break
        fi
        sleep 0.1
    done

    if [ -z "$JSON_FILE" ]; then
        JSON_FILE="$(ls -t extraction/data/normalized/mail_*.json 2>/dev/null | head -n 1 || true)"
    fi
    echo "[+] Successfully normalized: $JSON_FILE"
elif [[ "$INPUT_FILE" == *.json ]]; then
    JSON_FILE="$INPUT_FILE"
else
    echo "[-] Unsupported format. Provide an .eml file, a .json file, or an ID."
    exit 1
fi

echo "[*] Running LLM analysis (AutoAgent + Qwen)..."

RESPONSE=$(curl -sS --fail-with-body -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  --data-binary @"$JSON_FILE")

# Affichage formaté
if command -v jq >/dev/null 2>&1; then
    echo "$RESPONSE" | jq .
else
    echo "$RESPONSE"
fi

if [ "$GENERATE_REPORT" = true ]; then
    echo ""
    echo "[*] Generating the optional Jev + GPT report..."
    if ! curl -s --max-time 3 http://localhost:8001/health >/dev/null; then
        echo "[-] The report service is unavailable on port 8001."
        echo "    Start the complete platform with: ./start.sh --report"
        exit 2
    fi

    REPORT_RESPONSE=$(curl -sS --fail-with-body -X POST "$REPORT_URL" \
      -H "Content-Type: application/json" \
      --data-binary @"$JSON_FILE")

    if command -v jq >/dev/null 2>&1; then
        echo "$REPORT_RESPONSE" | jq .
    else
        echo "$REPORT_RESPONSE"
    fi
fi
