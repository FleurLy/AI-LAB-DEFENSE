import re
import difflib
import joblib
from pathlib import Path
from urllib.parse import urlparse

# ============================================================
# 0. CHARGEMENT DU MODÈLE ENTRAÎNÉ (agent/spam_email_classifier/model)
# ============================================================
HERE = Path(__file__).resolve().parent
SPAM_MODEL_PATH = HERE / "spam_email_classifier" / "model" / "spam_tfidf_loreg.joblib"

_MODEL = None  # cache, chargé une seule fois (lazy)


def get_model():
    """Charge (une seule fois) et retourne le modèle spam entraîné (TF-IDF + LogReg)."""
    global _MODEL
    if _MODEL is None:
        if not SPAM_MODEL_PATH.exists():
            raise FileNotFoundError(
                f"Modèle introuvable à {SPAM_MODEL_PATH}. "
                "Vérifie que agent/spam_email_classifier/model/ contient bien le .joblib."
            )
        _MODEL = joblib.load(SPAM_MODEL_PATH)
    return _MODEL

# ============================================================
# 1. CHECK EXPÉDITEUR (sender)
# ============================================================
KNOWN_DOMAINS = ["paypal.com", "google.com", "amazon.com", "microsoft.com"]  # à étendre

def check_expediteur(data: dict) -> dict:
    sender = data.get("sender", "")
    reply_to = data.get("reply_to", "")
    flags = []
    score = 0.0

    domain = sender.split("@")[-1].lower() if "@" in sender else ""

    # Typosquatting : distance avec domaines connus
    for known in KNOWN_DOMAINS:
        ratio = difflib.SequenceMatcher(None, domain, known).ratio()
        if 0.75 < ratio < 1.0:  # proche mais pas identique
            flags.append(f"typosquatting_possible_{known}")
            score += 0.5

    # Mismatch From / Reply-To
    if reply_to and reply_to.split("@")[-1].lower() != domain:
        flags.append("reply_to_mismatch")
        score += 0.4

    # Caractères suspects (chiffres à la place de lettres, ex: paypa1)
    if re.search(r'\d', domain.split(".")[0]):
        flags.append("domain_contains_digit_substitution")
        score += 0.3

    return {"score": min(score, 1.0), "flags": flags}


# ============================================================
# 2. CHECK DESTINATAIRE (to)
# ============================================================
def check_destinataire(data: dict) -> dict:
    to = data.get("to", "")
    flags = []
    score = 0.0

    # Envoi en masse / liste suspecte (plusieurs destinataires inconnus)
    if isinstance(to, list) and len(to) > 20:
        flags.append("mass_recipient_list")
        score += 0.4

    # Destinataire générique (souvent utilisé en phishing de masse)
    if isinstance(to, str) and any(x in to.lower() for x in ["undisclosed", "no-reply-list"]):
        flags.append("generic_recipient")
        score += 0.3

    return {"score": min(score, 1.0), "flags": flags}


# ============================================================
# 3. CHECK DOMAINE (analyse séparée, ex: whois-like local ou heuristique)
# ============================================================
SUSPICIOUS_TLDS = [".ru", ".tk", ".xyz", ".top", ".click", ".info"]

def check_domaine(data: dict) -> dict:
    sender = data.get("sender", "")
    domain = sender.split("@")[-1].lower() if "@" in sender else ""
    flags = []
    score = 0.0

    if any(domain.endswith(tld) for tld in SUSPICIOUS_TLDS):
        flags.append("suspicious_tld")
        score += 0.4

    # Sous-domaines multiples (ex: secure.paypal.verify-account.com)
    if domain.count(".") > 2:
        flags.append("excessive_subdomains")
        score += 0.3

    # Tirets multiples (souvent utilisé pour imiter un vrai domaine)
    if domain.count("-") >= 2:
        flags.append("multiple_hyphens_in_domain")
        score += 0.3

    return {"score": min(score, 1.0), "flags": flags}


# ============================================================
# 4. CHECK PIÈCES JOINTES
# ============================================================
DANGEROUS_EXT = [".exe", ".scr", ".bat", ".js", ".vbs", ".cmd", ".msi"]

def check_pieces_jointes(data: dict) -> dict:
    attachments = data.get("attachments", [])
    flags = []
    score = 0.0

    for fname in attachments:
        fname_lower = fname.lower()

        # Double extension (facture.pdf.exe)
        parts = fname_lower.split(".")
        if len(parts) > 2:
            flags.append(f"double_extension:{fname}")
            score += 0.5

        # Extension dangereuse
        if any(fname_lower.endswith(ext) for ext in DANGEROUS_EXT):
            flags.append(f"dangerous_extension:{fname}")
            score += 0.6

    return {"score": min(score, 1.0), "flags": flags}


# ============================================================
# 5. CHECK CONTENU — via ton modèle déjà entraîné
# ============================================================
def check_contenu(data: dict, model=None) -> dict:
    """
    model : ton modèle déjà entraîné (scikit-learn, ou autre),
    qui expose model.predict_proba() ou équivalent.
    Si non fourni, on charge automatiquement le modèle entraîné
    présent dans agent/spam_email_classifier/model/.
    """
    if model is None:
        model = get_model()

    subject = data.get("subject", "")
    body = data.get("body", "")
    text = f"{subject} {body}"

    # Adapter l'input du modèle : la plupart des modèles sklearn
    # attendent une liste de strings, pas un JSON brut.
    # -> on extrait juste le texte pertinent du JSON avant de l'envoyer au modèle.
    proba = model.predict_proba([text])[0][1]  # proba classe "fraude"

    flags = []
    if proba > 0.7:
        flags.append("high_ml_confidence_phishing")

    return {"score": float(proba), "flags": flags}