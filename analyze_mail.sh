#!/usr/bin/env bash
set -e

# Script d'analyse d'email de bout en bout (EML ou JSON -> LLM Security Analysis)
# Supporte les chemins de fichiers, les IDs du dataset (ex: 8 ou mail_000008), et la recherche.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

MANIFEST="extraction/datasets/phishing_validation/manifest.csv"
DATASET_DIR="extraction/datasets/phishing_validation/emails"

# Commande de recherche dans le dataset
if [ "$1" = "search" ] && [ -n "$2" ]; then
    QUERY="$2"
    echo "=== Recherche dans le dataset pour '$QUERY' ==="
    echo "ID            | LABEL    | SUJET"
    echo "--------------+----------+--------------------------------------------------"
    grep -i "$QUERY" "$MANIFEST" | awk -F',' '{printf "%-13s | %-8s | %s\n", $1, $5, $7}' | head -n 15
    exit 0
fi

# Commande de listing des emails du dataset
if [ "$1" = "list" ]; then
    FILTER="${2:-all}"
    echo "=== Échantillons du dataset ($FILTER) ==="
    echo "ID            | LABEL    | SUJET"
    echo "--------------+----------+--------------------------------------------------"
    if [ "$FILTER" = "phishing" ]; then
        grep ",phishing," "$MANIFEST" | awk -F',' '{printf "%-13s | %-8s | %s\n", $1, $5, $7}' | head -n 10
    elif [ "$FILTER" = "safe" ]; then
        grep ",safe," "$MANIFEST" | awk -F',' '{printf "%-13s | %-8s | %s\n", $1, $5, $7}' | head -n 10
    else
        awk -F',' 'NR>1 {printf "%-13s | %-8s | %s\n", $1, $5, $7}' "$MANIFEST" | head -n 15
    fi
    echo ""
    echo "Pour tester l'un d'eux : ./analyze_mail.sh <ID> (ex: ./analyze_mail.sh mail_000008 ou ./analyze_mail.sh 8)"
    exit 0
fi

if [ -z "$1" ]; then
    echo "Usage: $0 <fichier.eml | fichier.json | ID du dataset (ex: 8 ou mail_000008)>"
    echo ""
    echo "Options utiles :"
    echo "  $0 search <mot-clé>      Rechercher un mail dans le dataset (ex: paypal, account, bank...)"
    echo "  $0 list [phishing|safe]  Lister des exemples d'emails du dataset"
    echo ""
    echo "Exemples directs :"
    echo "  $0 8                                                        (Mail PayPal phishing du dataset)"
    echo "  $0 mail_000002                                              (Mail phishing du dataset)"
    echo "  $0 extraction/samples/suspicious/phishing_link.eml"
    echo "  $0 extraction/samples/suspicious/qr_phishing.eml"
    echo "  $0 extraction/data/normalized/mail_000001.json"
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
    echo "[-] Erreur : Le fichier '$INPUT_FILE' n'existe pas."
    exit 1
fi

JSON_FILE=""

# Détecter si c'est un EML ou déjà un JSON
if [[ "$INPUT_FILE" == *.eml ]]; then
    # Snapshot du fichier le plus récent avant l'envoi
    PREV_LATEST="$(ls -t extraction/data/normalized/mail_*.json 2>/dev/null | head -n 1 || true)"
    
    echo "[*] Ingestion SMTP du fichier : $INPUT_FILE"
    python3 extraction/scripts/replay.py "$INPUT_FILE" > /dev/null
    
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
    echo "[+] Normalisé avec succès : $JSON_FILE"
elif [[ "$INPUT_FILE" == *.json ]]; then
    JSON_FILE="$INPUT_FILE"
else
    echo "[-] Format non reconnu. Fournissez un fichier .eml, .json ou un ID."
    exit 1
fi

echo "[*] Analyse par le LLM (AutoAgent + Qwen)..."

RESPONSE=$(curl -s -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  --data-binary @"$JSON_FILE")

# Affichage formaté
if command -v jq >/dev/null 2>&1; then
    echo "$RESPONSE" | jq .
else
    echo "$RESPONSE"
fi
