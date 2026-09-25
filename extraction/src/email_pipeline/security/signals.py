from __future__ import annotations

import re

from email_pipeline.schemas.email_schema import (
    Attachment,
    Authentication,
    ContentSignals,
    Sender,
    TechnicalSignals,
    URLFinding,
)
from email_pipeline.urls.analyzer import is_suspicious


RULES: dict[str, tuple[str, ...]] = {
    "credential": (
        r"\bmot de passe\b", r"\bpassword\b", r"\bidentifiants?\b", r"\blogin\b",
        r"\bcode de connexion\b", r"\bverify your account\b",
    ),
    "payment": (
        r"\bpaiement\b", r"\bpayment\b", r"\bfacture\b", r"\binvoice\b",
        r"\bvirement\b", r"\bbank transfer\b", r"\bcarte bancaire\b",
    ),
    "urgent": (
        r"\burgent\b", r"\bimmédiatement\b", r"\bimmediately\b", r"\bexpire(?:ra| aujourd'hui)?\b",
        r"\bderni(?:er|ère) avertissement\b", r"\bact now\b",
    ),
    "threat": (
        r"\bsuspendu\b", r"\bblocked\b", r"\bfermé\b", r"\bclosed\b",
        r"\bpoursuite\b", r"\bpenalty\b", r"\bsupprimé\b",
    ),
    "secrecy": (
        r"\bconfidentiel\b", r"\bconfidential\b", r"\bne (?:le )?dites? à personne\b",
        r"\bkeep (?:this )?secret\b",
    ),
    "personal": (
        r"\bnuméro de sécurité sociale\b", r"\bsocial security\b", r"\bpièce d'identité\b",
        r"\bpassport\b", r"\bdate de naissance\b", r"\bcoordonnées bancaires\b",
    ),
}


def _matches(text: str, category: str) -> bool:
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in RULES[category])


def build_content_signals(
    text: str, attachments: list[Attachment], urls: list[URLFinding]
) -> ContentSignals:
    return ContentSignals(
        contains_credential_request=_matches(text, "credential"),
        contains_payment_request=_matches(text, "payment"),
        contains_urgent_language=_matches(text, "urgent"),
        contains_threat_language=_matches(text, "threat"),
        contains_secrecy_request=_matches(text, "secrecy"),
        contains_personal_data_request=_matches(text, "personal"),
        contains_external_link=bool(urls),
        contains_attachment=bool(attachments),
        contains_qr_code=any(attachment.qr_codes for attachment in attachments),
    )


def build_technical_signals(
    authentication: Authentication,
    sender: Sender,
    attachments: list[Attachment],
    urls: list[URLFinding],
) -> TechnicalSignals:
    return TechnicalSignals(
        spf_failed=authentication.spf in {"fail", "softfail", "permerror"},
        dkim_failed=authentication.dkim in {"fail", "permerror"},
        dmarc_failed=authentication.dmarc in {"fail", "permerror"},
        reply_to_mismatch=sender.from_reply_to_mismatch,
        return_path_mismatch=sender.from_return_path_mismatch,
        url_count=len(urls),
        suspicious_url_count=sum(is_suspicious(url) for url in urls),
        attachment_count=len(attachments),
        executable_attachment_count=sum(a.security.contains_executable for a in attachments),
        encrypted_attachment_count=sum(a.security.encrypted for a in attachments),
        qr_code_count=sum(len(a.qr_codes) for a in attachments),
    )

