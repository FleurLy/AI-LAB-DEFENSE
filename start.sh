#!/usr/bin/env bash
set -e

# Démarrage complet de tous les services (Ollama + Docker Extraction + Docker LLM)
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

echo "=========================================================="
echo "🚀 Démarrage complet de la plateforme AI-LAB-DEFENSE"
echo "=========================================================="

# 1. Vérification d'Ollama (Machine hôte pour le GPU)
echo "[1/3] Vérification d'Ollama..."
if ! curl -s http://127.0.0.1:11434/api/tags > /dev/null 2>&1; then
    echo "[*] Ollama non détecté sur le port 11434. Démarrage en arrière-plan..."
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
echo "[+] Ollama est actif sur http://127.0.0.1:11434"

# 2. Vérification du modèle
echo "[2/3] Vérification du modèle LLM (qwen2.5:3b)..."
if ! ollama list | grep -q "qwen2.5:3b"; then
    echo "[*] Modèle absent, téléchargement en cours..."
    ollama pull qwen2.5:3b
else
    echo "[+] Modèle qwen2.5:3b disponible."
fi

# 3. Démarrage des conteneurs Docker en arrière-plan
echo "[3/3] Démarrage des conteneurs Docker (Extraction SMTP + API LLM)..."
docker compose up -d

echo ""
echo "=========================================================="
echo "✅ Tous les services sont démarrés et opérationnels !"
echo " - Ingestion SMTP : localhost:1025"
echo " - API LLM Security : http://localhost:8000"
echo "=========================================================="
echo ""
echo "👉 Commandes pour tester immédiatement :"
echo "  ./analyze_mail.sh 8"
echo "  ./analyze_mail.sh extraction/samples/suspicious/phishing_link.eml"
echo "  ./analyze_mail.sh 1"
echo ""
