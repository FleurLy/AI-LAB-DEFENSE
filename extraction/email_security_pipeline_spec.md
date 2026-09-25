# Cahier des charges — Pipeline local d’analyse d’emails

## 1. Objectif

Construire une première version complète du pipeline d’ingestion et de normalisation des emails.

La **phase 1** du projet doit s’arrêter à la génération d’un **JSON unique, complet et normalisé pour chaque email reçu**.

Le modèle IA (Gemma, modèle entraîné maison, etc.) sera branché dans une phase suivante.

Le pipeline doit permettre de recevoir un email depuis :

- un serveur SMTP local pour la démonstration ;
- plus tard Gmail API ;
- plus tard IMAP pour les boîtes mail génériques.

Le système doit être entièrement dockerisé.

---

# 2. Principe général

Le pipeline cible est :

```text
Email reçu
    ↓
SMTP / Gmail / IMAP
    ↓
Mail Receiver
    ↓
Sauvegarde du mail brut (.eml)
    ↓
MIME Parser
    ↓
Extraction :
    ├── headers
    ├── body text/plain
    ├── body text/html
    ├── URLs
    └── pièces jointes
            ↓
      Attachment Manager
            ├── PDF
            ├── images
            ├── Office
            ├── QR codes
            └── autres fichiers
    ↓
Analyse technique
    ├── SPF
    ├── DKIM
    ├── DMARC
    ├── From / Reply-To
    ├── Return-Path
    └── URLs
    ↓
Normalisation
    ↓
UN SEUL JSON COMPLET PAR EMAIL
```

Le fichier JSON produit doit être directement consommable par n’importe quel modèle.

Le modèle ne doit pas avoir besoin :

- d’ouvrir un PDF ;
- de lire une image ;
- de parser un email ;
- de faire de l’OCR ;
- d’extraire des URLs ;
- de comparer les domaines ;
- d’interpréter les headers SMTP.

Tout ce travail doit être fait avant l’appel au modèle.

---

# 3. Architecture Docker

Pour la première version, garder l’architecture simple.

## Services

```yaml
services:
  mail-service:
    # réception SMTP + parsing + extraction + génération JSON
```

Dans une version ultérieure, on pourra séparer :

```yaml
services:
  smtp:
  ingestor:
  extractor:
  analyzer:
  ai:
  api:
  dashboard:
```

Mais pour le MVP du hackathon, un seul conteneur Python est suffisant.

---

# 4. Serveur SMTP local

Le conteneur doit embarquer un serveur SMTP local.

Port recommandé :

```text
1025
```

Bibliothèque Python recommandée :

```text
aiosmtpd
```

Exemple :

```text
localhost:1025
```

À chaque réception d’un email :

1. récupérer le message MIME brut ;
2. générer un identifiant interne ;
3. sauvegarder immédiatement le mail original au format `.eml` ;
4. lancer le pipeline de parsing et d’extraction.

Le `.eml` original doit toujours être conservé.

Exemple :

```text
/data/raw/mail_000001.eml
```

---

# 5. Structure des données locales

Utiliser une structure similaire à :

```text
data/
├── raw/
│   ├── mail_000001.eml
│   └── mail_000002.eml
│
├── attachments/
│   ├── mail_000001/
│   │   ├── facture.pdf
│   │   └── qr_code.png
│   └── mail_000002/
│
├── work/
│   └── mail_000001/
│       ├── page_1.png
│       └── page_2.png
│
└── normalized/
    ├── mail_000001.json
    └── mail_000002.json
```

Le dossier `work/` contient uniquement les fichiers temporaires générés pendant l’extraction.

---

# 6. Parsing des emails

Utiliser les bibliothèques Python standard lorsque possible :

```python
email
email.parser
email.policy
```

Le parser doit extraire au minimum :

- From ;
- To ;
- Cc ;
- Reply-To ;
- Return-Path ;
- Subject ;
- Date ;
- Message-ID ;
- Received ;
- Authentication-Results ;
- body text/plain ;
- body text/html ;
- pièces jointes.

Le parser doit correctement gérer les encodages MIME et Unicode.

---

# 7. Corps de l’email

Conserver :

```json
{
  "body_text": "...",
  "body_html": "..."
}
```

`body_text` est la représentation principale destinée aux modèles.

Si l’email contient uniquement du HTML :

1. conserver le HTML original ;
2. produire une version texte nettoyée.

Le texte nettoyé doit conserver au maximum :

- texte visible ;
- labels de boutons ;
- URLs associées ;
- ordre logique du contenu.

---

# 8. Gestionnaire de pièces jointes

Créer un composant dédié :

```text
AttachmentManager
```

Son rôle est de transformer toutes les pièces jointes en données directement compréhensibles.

Pour chaque pièce jointe, détecter :

- nom de fichier ;
- extension ;
- MIME déclaré ;
- MIME réel si possible ;
- taille ;
- hash SHA-256 ;
- présence éventuelle d’URL ;
- présence éventuelle de QR code ;
- contenu textuel ;
- méthode d’extraction utilisée ;
- erreurs éventuelles.

Ne jamais exécuter une pièce jointe.

---

# 9. Gestion des PDF

La logique doit être :

```text
PDF
 ↓
essayer extraction texte
 ↓
texte suffisamment exploitable ?
 ├── OUI
 │    ↓
 │  utiliser ce texte
 │
 └── NON
      ↓
   convertir les pages en images
      ↓
      OCR
      ↓
   concaténer le texte
```

Bibliothèque recommandée :

```text
PyMuPDF
```

Le système doit privilégier l’extraction texte car elle est :

- plus rapide ;
- plus légère ;
- plus adaptée à une exécution CPU.

La conversion image/OCR ne doit être utilisée qu’en fallback.

---

# 10. Critère « texte PDF exploitable »

Créer une fonction :

```python
is_text_usable(text: str) -> bool
```

Elle peut notamment vérifier :

- longueur minimale ;
- proportion de caractères imprimables ;
- ratio de lettres/chiffres ;
- absence de texte totalement vide ;
- absence de contenu constitué majoritairement de caractères incohérents.

Le seuil exact doit être configurable.

Exemple :

```python
MIN_EXTRACTED_TEXT_LENGTH = 30
```

---

# 11. Gestion des images

Pour les images :

```text
image
 ↓
OCR
 ↓
texte
```

Le résultat final doit être stocké dans :

```json
"content_text": "..."
```

La pièce jointe doit également indiquer :

```json
"extraction": {
  "method": "ocr",
  "success": true
}
```

Prévoir également la détection de QR codes.

Un QR code détecté doit être décodé et son contenu ajouté au JSON.

---

# 12. Fichiers Office

Prévoir au minimum :

- `.docx`
- `.xlsx`
- `.pptx`

Objectif : extraire du texte sans exécuter de macros ni de contenu actif.

Si l’extraction n’est pas disponible ou échoue :

```json
{
  "extraction": {
    "success": false,
    "method": "unsupported",
    "error": "..."
  }
}
```

Le pipeline ne doit jamais crasher à cause d’une pièce jointe non supportée.

---

# 13. Hash des pièces jointes

Calculer systématiquement :

```text
SHA-256
```

Exemple :

```json
"sha256": "..."
```

Le hash doit être calculé sur le fichier original reçu.

---

# 14. URLs

Extraire les URLs depuis :

- body texte ;
- body HTML ;
- PDF ;
- documents Office ;
- texte OCR ;
- QR codes.

Chaque URL doit idéalement contenir :

```json
{
  "source": "email_body",
  "url": "https://example.com/login",
  "display_text": "Connexion",
  "domain": "example.com",
  "scheme": "https",
  "uses_ip_address": false,
  "uses_punycode": false,
  "is_shortened": false,
  "display_domain_mismatch": false
}
```

Les valeurs impossibles à déterminer peuvent être `null`.

Le champ `source` doit permettre d’identifier l’origine :

```text
email_body
email_html
attachment:<filename>
qr_code:<filename>
```

---

# 15. Analyse des domaines

Extraire les domaines de :

- From ;
- Reply-To ;
- Return-Path.

Puis calculer :

```json
{
  "from_reply_to_mismatch": true,
  "from_return_path_mismatch": true
}
```

Ces informations doivent être calculées en code.

Le modèle IA ne doit pas avoir à faire cette comparaison lui-même.

---

# 16. SPF, DKIM et DMARC

Extraire les résultats à partir des headers lorsqu’ils sont présents.

Valeurs possibles recommandées :

```text
pass
fail
softfail
neutral
none
temperror
permerror
unknown
```

Exemple :

```json
"authentication": {
  "spf": "fail",
  "dkim": "pass",
  "dmarc": "fail"
}
```

Important :

sur le serveur SMTP local de démonstration, SPF/DKIM/DMARC peuvent être absents ou artificiels.

Le pipeline doit donc gérer :

```text
unknown
```

sans erreur.

---

# 17. Signaux sémantiques

La première version peut calculer quelques signaux simples à partir du texte avec des règles déterministes.

Exemples :

```json
"content_signals": {
  "contains_credential_request": true,
  "contains_payment_request": false,
  "contains_urgent_language": true,
  "contains_threat_language": false,
  "contains_secrecy_request": false,
  "contains_personal_data_request": false,
  "contains_external_link": true,
  "contains_attachment": true,
  "contains_qr_code": false
}
```

Ces signaux doivent être considérés comme des faits/extractions.

Ils ne doivent pas contenir de score final de risque.

---

# 18. Signaux techniques

Créer également :

```json
"technical_signals": {
  "spf_failed": true,
  "dkim_failed": false,
  "dmarc_failed": true,
  "reply_to_mismatch": true,
  "return_path_mismatch": true,
  "url_count": 2,
  "suspicious_url_count": 1,
  "attachment_count": 1,
  "executable_attachment_count": 0,
  "encrypted_attachment_count": 0,
  "qr_code_count": 0
}
```

Pour le MVP, `suspicious_url_count` peut être calculé avec des règles simples.

Ne pas implémenter de sandbox réseau complexe dans cette première version.

---

# 19. JSON UNIQUE PAR EMAIL

Principe fondamental :

```text
1 email = 1 JSON
```

Ne jamais produire :

```text
email.json
attachments.json
security.json
```

mais :

```text
mail_000001.json
```

qui contient toutes les informations.

---

# 20. Schéma JSON v1 définitif

Exemple complet :

```json
{
  "schema_version": "1.0",

  "email": {
    "internal_id": "mail_000001",

    "from": {
      "name": "Microsoft Security",
      "address": "security@example.com"
    },

    "reply_to": {
      "name": null,
      "address": "support@other-domain.com"
    },

    "to": [
      "user@company.com"
    ],

    "cc": [],

    "subject": "URGENT - Votre mot de passe expire",

    "body_text": "Bonjour, votre mot de passe expire aujourd'hui...",

    "body_html": "<html>...</html>",

    "language": "fr",

    "sent_at": "2026-09-25T18:30:00Z",

    "message_id": "<abc123@example.com>"
  },

  "attachments": [
    {
      "name": "facture.pdf",

      "mime_type_declared": "application/pdf",

      "mime_type_detected": "application/pdf",

      "size_bytes": 184532,

      "sha256": "abc123...",

      "content_text": "FACTURE N°4582\nMontant : 4 850 €...",

      "visual_description": null,

      "extraction": {
        "method": "text",
        "success": true,
        "error": null
      },

      "urls": [
        "https://example.com/payment"
      ],

      "qr_codes": [],

      "security": {
        "extension_mime_mismatch": false,
        "encrypted": false,
        "contains_macro": false,
        "contains_executable": false
      }
    },

    {
      "name": "qr_code.png",

      "mime_type_declared": "image/png",

      "mime_type_detected": "image/png",

      "size_bytes": 48321,

      "sha256": "def456...",

      "content_text": "Scannez ce QR code pour confirmer votre compte.",

      "visual_description": null,

      "extraction": {
        "method": "ocr",
        "success": true,
        "error": null
      },

      "urls": [],

      "qr_codes": [
        "https://fake-login.example"
      ],

      "security": {
        "extension_mime_mismatch": false,
        "encrypted": false,
        "contains_macro": false,
        "contains_executable": false
      }
    }
  ],

  "urls": [
    {
      "source": "email_body",

      "display_text": "Se connecter",

      "url": "https://micros0ft-login.example.xyz",

      "domain": "micros0ft-login.example.xyz",

      "scheme": "https",

      "uses_ip_address": false,

      "uses_punycode": false,

      "is_shortened": false,

      "display_domain_mismatch": true
    },

    {
      "source": "qr_code:qr_code.png",

      "display_text": null,

      "url": "https://fake-login.example",

      "domain": "fake-login.example",

      "scheme": "https",

      "uses_ip_address": false,

      "uses_punycode": false,

      "is_shortened": false,

      "display_domain_mismatch": null
    }
  ],

  "authentication": {
    "spf": "fail",
    "dkim": "none",
    "dmarc": "fail"
  },

  "sender": {
    "from_domain": "example.com",

    "reply_to_domain": "other-domain.com",

    "return_path": "bounce@another-domain.com",

    "return_path_domain": "another-domain.com",

    "from_reply_to_mismatch": true,

    "from_return_path_mismatch": true
  },

  "routing": {
    "source": "smtp",

    "received_at": "2026-09-25T18:30:02Z",

    "received_hops": 4
  },

  "content_signals": {
    "contains_credential_request": true,

    "contains_payment_request": false,

    "contains_urgent_language": true,

    "contains_threat_language": true,

    "contains_secrecy_request": false,

    "contains_personal_data_request": false,

    "contains_external_link": true,

    "contains_attachment": true,

    "contains_qr_code": true
  },

  "technical_signals": {
    "spf_failed": true,

    "dkim_failed": false,

    "dmarc_failed": true,

    "reply_to_mismatch": true,

    "return_path_mismatch": true,

    "url_count": 2,

    "suspicious_url_count": 2,

    "attachment_count": 2,

    "executable_attachment_count": 0,

    "encrypted_attachment_count": 0,

    "qr_code_count": 1
  }
}
```

---

# 21. Règle importante : ne pas produire de score de risque ici

Le pipeline d’extraction ne doit PAS écrire :

```json
{
  "risk_score": 87
}
```

ou :

```json
{
  "verdict": "phishing"
}
```

Ces champs seront produits plus tard par le modèle IA.

Le JSON d’entrée doit rester aussi factuel que possible.

---

# 22. Composants Python proposés

Organisation recommandée :

```text
src/
├── main.py
│
├── smtp/
│   ├── __init__.py
│   └── server.py
│
├── mail/
│   ├── __init__.py
│   ├── parser.py
│   ├── normalizer.py
│   └── models.py
│
├── attachments/
│   ├── __init__.py
│   ├── manager.py
│   ├── pdf.py
│   ├── image.py
│   ├── office.py
│   ├── qr.py
│   └── common.py
│
├── urls/
│   ├── __init__.py
│   ├── extractor.py
│   └── analyzer.py
│
├── security/
│   ├── __init__.py
│   ├── authentication.py
│   ├── sender.py
│   └── signals.py
│
├── schemas/
│   ├── __init__.py
│   └── email_schema.py
│
└── config.py
```

---

# 23. Modèles de données

Utiliser de préférence :

```text
Pydantic
```

pour définir le schéma interne.

Avantages :

- validation ;
- sérialisation JSON ;
- champs optionnels ;
- documentation automatique ;
- compatibilité API ultérieure.

Exemple conceptuel :

```python
class Attachment(BaseModel):
    name: str
    mime_type_declared: str | None
    mime_type_detected: str | None
    size_bytes: int
    sha256: str
    content_text: str
    extraction: ExtractionResult
    urls: list[str]
    qr_codes: list[str]
    security: AttachmentSecurity
```

Le fichier JSON final doit être généré à partir de ces modèles.

---

# 24. Script de replay

Créer un script :

```text
scripts/replay.py
```

Usage :

```bash
python scripts/replay.py samples/phishing.eml
```

Le script doit envoyer le mail via SMTP au serveur local :

```text
localhost:1025
```

Ainsi le pipeline réellement testé est :

```text
sample.eml
 ↓
SMTP
 ↓
Docker
 ↓
réception
 ↓
parsing
 ↓
extraction
 ↓
JSON
```

Ne pas contourner SMTP pour les tests end-to-end.

---

# 25. Samples

Créer quelques exemples de test :

```text
samples/
├── benign/
│   ├── simple_text.eml
│   └── newsletter.eml
│
├── suspicious/
│   ├── phishing_link.eml
│   ├── invoice_pdf.eml
│   ├── scanned_pdf.eml
│   ├── qr_phishing.eml
│   └── reply_to_mismatch.eml
│
└── attachments/
    ├── invoice.pdf
    ├── scanned_invoice.pdf
    └── qr_code.png
```

Ne pas inclure de malware réel.

---

# 26. Dockerfile

Le projet doit fournir un :

```text
Dockerfile
```

et un :

```text
docker-compose.yml
```

Commande cible :

```bash
docker compose up --build
```

Après lancement, le serveur SMTP doit être disponible sur :

```text
localhost:1025
```

---

# 27. Volumes Docker

Monter le dossier `data/` comme volume.

Exemple conceptuel :

```yaml
volumes:
  - ./data:/app/data
```

Le JSON produit doit donc rester accessible depuis la machine hôte.

---

# 28. Configuration

Toutes les valeurs configurables doivent être centralisées.

Exemple :

```env
SMTP_HOST=0.0.0.0
SMTP_PORT=1025

DATA_DIR=/app/data

MIN_PDF_TEXT_LENGTH=30

KEEP_WORK_FILES=true

LOG_LEVEL=INFO
```

Créer :

```text
.env.example
```

Ne pas committer de secrets.

---

# 29. Logging

Ajouter des logs simples.

Exemple :

```text
[INFO] Email received: mail_000001
[INFO] Subject: Facture urgente
[INFO] Attachments: 2
[INFO] Extracting facture.pdf
[INFO] PDF text extraction successful
[INFO] QR code detected in qr_code.png
[INFO] Generated /data/normalized/mail_000001.json
```

Une erreur sur une PJ ne doit pas arrêter le traitement du mail complet.

---

# 30. Robustesse

Le pipeline doit continuer même si :

- une PJ est corrompue ;
- le PDF est chiffré ;
- le MIME est incorrect ;
- l’OCR échoue ;
- le QR code est invalide ;
- l’encodage du mail est incorrect ;
- SPF/DKIM/DMARC sont absents ;
- un fichier n’est pas supporté.

Les erreurs doivent être enregistrées dans le JSON lorsque pertinent.

---

# 31. Sécurité

Règles obligatoires :

1. ne jamais exécuter une pièce jointe ;
2. ne jamais lancer de macro Office ;
3. ne jamais exécuter de JavaScript contenu dans un PDF ;
4. ne pas ouvrir automatiquement les URLs ;
5. traiter tous les emails et PJ comme non fiables ;
6. nettoyer les noms de fichiers avant écriture disque ;
7. empêcher les chemins du type :

```text
../../etc/passwd
```

8. imposer une taille maximale configurable aux PJ ;
9. imposer une taille maximale configurable aux emails ;
10. prévoir des timeouts pour les extracteurs.

---

# 32. Tests unitaires

Créer des tests pour :

```text
tests/
├── test_mail_parser.py
├── test_pdf_extraction.py
├── test_image_extraction.py
├── test_url_extraction.py
├── test_sender_analysis.py
├── test_json_schema.py
└── test_end_to_end.py
```

Tests importants :

- email texte simple ;
- HTML uniquement ;
- PDF texte ;
- PDF scanné ;
- image avec OCR ;
- QR code ;
- From != Reply-To ;
- Return-Path différent ;
- PJ inconnue ;
- PJ corrompue ;
- email multipart.

---

# 33. Critères d’acceptation du MVP

Le MVP est terminé lorsque :

## Test 1

Commande :

```bash
docker compose up --build
```

Le serveur démarre sans erreur.

---

## Test 2

Commande :

```bash
python scripts/replay.py samples/benign/simple_text.eml
```

Un JSON apparaît dans :

```text
data/normalized/
```

---

## Test 3

Un email contenant un PDF texte produit :

```json
{
  "attachments": [
    {
      "content_text": "...",
      "extraction": {
        "method": "text",
        "success": true
      }
    }
  ]
}
```

---

## Test 4

Un PDF scanné produit :

```json
{
  "attachments": [
    {
      "content_text": "...",
      "extraction": {
        "method": "ocr",
        "success": true
      }
    }
  ]
}
```

---

## Test 5

Une image contenant un QR code produit :

```json
{
  "qr_codes": [
    "https://..."
  ]
}
```

---

## Test 6

Un email avec From et Reply-To différents produit :

```json
{
  "sender": {
    "from_reply_to_mismatch": true
  }
}
```

---

## Test 7

Le JSON final respecte toujours le schéma défini.

---

# 34. Phase suivante — hors scope pour le moment

Une fois le pipeline stable :

```text
JSON normalisé
       ↓
AutoAgent
       ↓
modèle local interchangeable
       ↓
Gemma E2B / E4B / autre modèle
       ↓
JSON de décision
```

Le modèle sera interchangeable.

Le choix initial probable pour une machine Apple Silicon 8 Go est un petit modèle quantifié.

Mais le pipeline d’extraction ne doit dépendre d’aucun modèle particulier.

---

# 35. Principe d’interface avec l’IA

L’interface future doit rester :

```text
normalized_email.json
        ↓
      model
        ↓
classification_result.json
```

Le modèle doit recevoir le JSON déjà prêt.

Aucun parsing de pièce jointe ne doit être confié au modèle.

---

# 36. Contraintes de développement pour Codex

Codex doit :

1. créer une implémentation réellement fonctionnelle ;
2. éviter les placeholders inutiles ;
3. fournir un `README.md` avec les commandes exactes ;
4. fournir un `.env.example` ;
5. fournir les tests ;
6. fournir des samples simples ;
7. utiliser des types Python ;
8. utiliser Pydantic pour les structures JSON ;
9. gérer proprement les exceptions ;
10. documenter les dépendances ;
11. ne jamais exécuter les pièces jointes ;
12. garder le code modulaire ;
13. ne pas intégrer Gemma ou AutoAgent dans cette première phase ;
14. garantir qu’un email produit exactement un JSON normalisé ;
15. maintenir une séparation nette entre :
    - réception ;
    - parsing ;
    - extraction ;
    - analyse technique ;
    - normalisation.

---

# 37. Résultat attendu

À la fin, l’expérience utilisateur doit être :

```bash
git clone <repo>
cd <repo>

cp .env.example .env

docker compose up --build
```

Puis dans un autre terminal :

```bash
python scripts/replay.py samples/suspicious/phishing_link.eml
```

Résultat :

```text
data/normalized/mail_000001.json
```

Le fichier contient toutes les données exploitables du mail.

Ce fichier doit ensuite pouvoir être donné directement :

- à Gemma ;
- à un autre LLM ;
- à un classifieur entraîné ;
- à AutoAgent ;
- à une API ;
- à un système de scoring.

---

# 38. Priorité absolue

La priorité de cette phase est :

> Transformer de manière fiable n’importe quel email reçu en un JSON unique, propre, stable, explicite et directement exploitable par un modèle.

Ne pas commencer la partie IA tant que ce pipeline n’est pas correctement testé.
