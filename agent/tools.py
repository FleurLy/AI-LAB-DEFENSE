import re
import difflib
import ipaddress
import joblib
from pathlib import Path
from typing import Any

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
                f"Model not found at {SPAM_MODEL_PATH}. "
                "Make sure agent/spam_email_classifier/model/ contains the .joblib file."
            )
        _MODEL = joblib.load(SPAM_MODEL_PATH)
    return _MODEL

# ============================================================
# 1. CHECK EXPÉDITEUR (sender)
# ============================================================
KNOWN_DOMAINS = ["paypal.com", "google.com", "amazon.com", "microsoft.com"]  # à étendre


def _email_section(data: dict[str, Any]) -> dict[str, Any]:
    email = data.get("email", {})
    return email if isinstance(email, dict) else {}


def _address(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        address = value.get("address")
        return address if isinstance(address, str) else ""
    return ""


def check_expediteur(data: dict) -> dict:
    email = _email_section(data)
    sender = _address(email.get("from", data.get("sender", "")))
    reply_to = _address(email.get("reply_to", data.get("reply_to", "")))
    authentication = data.get("authentication", {})
    authentication = authentication if isinstance(authentication, dict) else {}
    sender_signals = data.get("sender", {})
    sender_signals = sender_signals if isinstance(sender_signals, dict) else {}
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
    if (
        sender_signals.get("from_reply_to_mismatch") is True
        or (reply_to and reply_to.split("@")[-1].lower() != domain)
    ):
        flags.append("reply_to_mismatch")
        score += 0.4

    for protocol in ("spf", "dkim", "dmarc"):
        if str(authentication.get(protocol, "")).lower() == "fail":
            flags.append(f"{protocol}_failed")
            score += 0.15

    # Caractères suspects (chiffres à la place de lettres, ex: paypa1)
    if re.search(r'\d', domain.split(".")[0]):
        flags.append("domain_contains_digit_substitution")
        score += 0.3

    return {"score": min(score, 1.0), "flags": flags}


# ============================================================
# 2. CHECK DESTINATAIRE (to)
# ============================================================
def check_destinataire(data: dict) -> dict:
    email = _email_section(data)
    to = email.get("to", data.get("to", ""))
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
    urls = data.get("urls", [])
    urls = urls if isinstance(urls, list) else []
    flags = []
    score = 0.0

    for entry in urls:
        if not isinstance(entry, dict):
            continue
        domain = str(entry.get("domain") or "").lower().strip(".")
        if entry.get("uses_ip_address") is True:
            flags.append(f"raw_ip_url:{domain}")
            score += 0.6
        else:
            try:
                ipaddress.ip_address(domain)
            except ValueError:
                pass
            else:
                flags.append(f"raw_ip_url:{domain}")
                score += 0.6
        if entry.get("uses_punycode") is True or "xn--" in domain:
            flags.append(f"punycode_domain:{domain}")
            score += 0.5
        if entry.get("display_domain_mismatch") is True:
            flags.append(f"display_domain_mismatch:{domain}")
            score += 0.5
        if any(domain.endswith(tld) for tld in SUSPICIOUS_TLDS):
            flags.append(f"suspicious_tld:{domain}")
            score += 0.4
        if domain.count(".") > 2:
            flags.append(f"excessive_subdomains:{domain}")
            score += 0.3
        if domain.count("-") >= 2:
            flags.append(f"multiple_hyphens:{domain}")
            score += 0.3

    return {"score": min(score, 1.0), "flags": sorted(set(flags))}


# ============================================================
# 4. CHECK PIÈCES JOINTES
# ============================================================
DANGEROUS_EXT = [".exe", ".scr", ".bat", ".js", ".vbs", ".cmd", ".msi"]

def check_pieces_jointes(data: dict) -> dict:
    attachments = data.get("attachments", [])
    flags = []
    score = 0.0

    for attachment in attachments:
        if isinstance(attachment, dict):
            fname = str(attachment.get("name") or "")
            security = attachment.get("security", {})
            security = security if isinstance(security, dict) else {}
        else:
            fname = str(attachment)
            security = {}
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

        if security.get("extension_mime_mismatch") is True:
            flags.append(f"extension_mime_mismatch:{fname}")
            score += 0.5
        if security.get("contains_macro") is True:
            flags.append(f"contains_macro:{fname}")
            score += 0.6
        if security.get("contains_executable") is True:
            flags.append(f"contains_executable:{fname}")
            score += 0.8
        if security.get("encrypted") is True:
            flags.append(f"encrypted_attachment:{fname}")
            score += 0.25

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

    email = _email_section(data)
    subject = email.get("subject", data.get("subject", ""))
    body = email.get("body_text", data.get("body", ""))
    text = f"{subject} {body}"

    # Adapter l'input du modèle : la plupart des modèles sklearn
    # attendent une liste de strings, pas un JSON brut.
    # -> on extrait juste le texte pertinent du JSON avant de l'envoyer au modèle.
    proba = model.predict_proba([text])[0][1]  # proba classe "fraude"

    flags = []
    if proba > 0.7:
        flags.append("high_ml_confidence_phishing")

    return {"score": float(proba), "flags": flags}


def run_security_tools(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Run every deterministic security tool against one normalized email."""

    return {
        "check_expediteur": check_expediteur(data),
        "check_destinataire": check_destinataire(data),
        "check_domaine": check_domaine(data),
        "check_pieces_jointes": check_pieces_jointes(data),
        "check_contenu": check_contenu(data),
    }
