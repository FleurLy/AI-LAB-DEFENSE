#!/usr/bin/env bash
set -e

# Démarrage complet de tous les services (Ollama + Docker Extraction + Docker LLM)
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

ENABLE_REPORT=false
if [ "${1:-}" = "--report" ]; then
    ENABLE_REPORT=true
elif [ -n "${1:-}" ]; then
    echo "Usage: $0 [--report]"
    exit 1
fi

echo "=========================================================="
echo "🚀 Starting the complete AI-LAB-DEFENSE platform"
echo "=========================================================="

# 1. Vérification d'Ollama (Machine hôte pour le GPU)
echo "[1/3] Checking Ollama..."
if ! curl -s http://127.0.0.1:11434/api/tags > /dev/null 2>&1; then
    echo "[*] Ollama was not detected on port 11434. Starting it in the background..."
    if command -v brew >/dev/null 2>&1 && brew services list 2>/dev/null | grep -q ollama; then
        brew services start ollama
    else
        ollama serve > /dev/null 2>&1 &
    fi
    # Attendre que le port soit prêt
    for _ in {1..15}; do
        if curl -s http://127.0.0.1:11434/api/tags > /dev/null 2>&1; then
            break
        fi
        sleep 1
    done
fi
echo "[+] Ollama is running at http://127.0.0.1:11434"

# 2. Vérification du modèle
echo "[2/3] Checking the LLM model (qwen2.5:3b)..."
if ! ollama list | grep -q "qwen2.5:3b"; then
    echo "[*] Model not found. Downloading it now..."
    ollama pull qwen2.5:3b
else
    echo "[+] Model qwen2.5:3b is available."
fi

# 3. Démarrage des conteneurs Docker en arrière-plan
if [ "$ENABLE_REPORT" = true ]; then
    echo "[3/3] Starting containers (SMTP + AutoAgent + Jev/GPT report)..."
    docker compose --profile report up -d
else
    echo "[3/3] Starting Docker containers (SMTP extraction + LLM API)..."
    docker compose up -d
fi

wait_for_http() {
    local name="$1"
    local url="$2"
    for _ in {1..60}; do
        if curl -s --max-time 1 "$url" >/dev/null; then
            echo "[+] $name is ready."
            return 0
        fi
        sleep 1
    done
    echo "[-] $name did not become available: $url"
    docker compose --profile report ps
    return 1
}

wait_for_smtp() {
    # OCR/PDF imports can make the very first SMTP startup take over 90 seconds.
    for _ in {1..180}; do
        if (exec 3<>/dev/tcp/127.0.0.1/1025) 2>/dev/null; then
            echo "[+] The SMTP service is ready."
            return 0
        fi
        sleep 1
    done
    echo "[-] The SMTP service did not become available on port 1025."
    docker compose --profile report ps
    return 1
}

echo "[*] Waiting for all services to become ready..."
wait_for_smtp
wait_for_http "The AutoAgent API" "http://127.0.0.1:8000/health"
if [ "$ENABLE_REPORT" = true ]; then
    wait_for_http "The Jev/GPT report API" "http://127.0.0.1:8001/health"
fi

echo ""
echo "=========================================================="
echo "✅ All services are running and ready!"
echo " - SMTP ingestion: localhost:1025"
echo " - LLM Security API: http://localhost:8000"
if [ "$ENABLE_REPORT" = true ]; then
    echo " - Optional Jev/GPT report: http://localhost:8001"
fi
echo "=========================================================="
echo ""
echo "👉 Commands you can run now:"
echo "  ./analyze_mail.sh 8"
echo "  ./analyze_mail.sh extraction/samples/suspicious/phishing_link.eml"
echo "  ./analyze_mail.sh 1"
echo ""
