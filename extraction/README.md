# Email Security Pipeline — phase 1

Pipeline local qui reçoit un email par SMTP, conserve le `.eml` original, extrait son contenu et ses pièces jointes, puis écrit **un JSON Pydantic unique et factuel**. Aucun modèle IA, verdict ou score de risque n'est inclus.

## Démarrage Docker

```bash
cp .env.example .env
docker compose up --build
```

Le serveur SMTP écoute alors sur `localhost:1025`. Dans un autre terminal :

```bash
python scripts/replay.py samples/benign/simple_text.eml
python scripts/replay.py samples/suspicious/phishing_link.eml
```

Les résultats sont écrits dans `data/raw/`, `data/attachments/` et `data/normalized/` sur l'hôte. Un email accepté produit exactement un fichier `data/normalized/mail_NNNNNN.json`.

## Développement local

Tesseract, libmagic et zbar doivent être installés sur la machine. Sur macOS :

```bash
brew install tesseract tesseract-lang libmagic zbar
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
pytest
```

Pour lancer le serveur sans Docker :

```bash
cp .env.example .env
# Adapter DATA_DIR=data dans .env pour une exécution locale.
python -m email_pipeline.main
```

## Samples de pièces jointes

Les emails texte/HTML sont versionnés directement. Les PDF inoffensifs sont générés avec :

```bash
python scripts/generate_samples.py
```

Cette commande crée `samples/attachments/invoice.pdf`, `scanned_invoice.pdf` et les emails correspondants. Aucun malware réel n'est utilisé.

## Extraction et sécurité

- PDF : texte natif d'abord, rasterisation + OCR seulement si le texte est inutilisable.
- Images : OCR et décodage QR local.
- Office : lecture passive de `.docx`, `.xlsx` et `.pptx`, sans macro.
- Autres types : erreur `unsupported` dans le JSON, sans interruption du pipeline.
- Les noms sont nettoyés, les tailles et délais sont bornés, les URLs ne sont jamais ouvertes et les pièces jointes ne sont jamais exécutées.
- SPF, DKIM et DMARC sont lus dans les headers existants ; le pipeline ne prétend pas effectuer une validation DNS.

## Configuration

Toutes les options figurent dans `.env.example`, notamment les tailles maximales, le seuil de texte PDF, la langue OCR, le timeout d'extraction et la conservation des fichiers de travail.

