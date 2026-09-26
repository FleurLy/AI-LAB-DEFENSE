#!/usr/bin/env bash
set -e

# Surveillance automatique du dossier d'extraction (extraction/data/normalized).
# Dès qu'un email est totalement extrait/normalisé (le pipeline écrit d'abord
# un .json.tmp puis le renomme en .json une fois terminé), ce script envoie
# automatiquement le JSON à l'API LLM d'analyse de sécurité (comme le fait
# analyze_mail.sh, mais sans action manuelle).

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

NORMALIZED_DIR="extraction/data/normalized"
LLM_URL="http://localhost:8000/analyze"

mkdir -p "$NORMALIZED_DIR"

SEEN_FILE="$(mktemp)"
trap 'rm -f "$SEEN_FILE"' EXIT

echo "=========================================================="
echo "👀 Surveillance automatique de : $NORMALIZED_DIR"
echo "   Dès qu'un email est extrait (JSON finalisé), il est envoyé"
echo "   automatiquement au LLM ($LLM_URL)."
echo "   Ctrl+C pour arrêter."
echo "=========================================================="

# On ignore les emails déjà présents au démarrage pour ne pas les
# ré-analyser (seuls les NOUVEAUX emails extraits seront traités).
ls "$NORMALIZED_DIR"/mail_*.json 2>/dev/null > "$SEEN_FILE" || true

while true; do
    for JSON_FILE in "$NORMALIZED_DIR"/mail_*.json; do
        [ -e "$JSON_FILE" ] || continue

        # Fichier temporaire = extraction pas encore terminée -> on ignore
        [[ "$JSON_FILE" == *.tmp ]] && continue

        if ! grep -qxF "$JSON_FILE" "$SEEN_FILE" 2>/dev/null; then
            echo "$JSON_FILE" >> "$SEEN_FILE"
            echo ""
            echo "[+] Extraction terminée pour : $JSON_FILE"
            echo "[*] Lancement automatique de l'analyse LLM (AutoAgent + Qwen)..."

            RESPONSE=$(curl -s -X POST "$LLM_URL" \
                -H "Content-Type: application/json" \
                --data-binary @"$JSON_FILE") || {
                    echo "[-] Erreur : impossible de contacter l'API LLM ($LLM_URL)."
                    continue
                }

            if command -v jq >/dev/null 2>&1; then
                echo "$RESPONSE" | jq .
            else
                echo "$RESPONSE"
            fi
        fi
    done
    sleep 2
done