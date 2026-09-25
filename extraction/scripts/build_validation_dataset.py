#!/usr/bin/env python3
"""Generate a balanced 100-email validation dataset for AI defense phishing detection.

Layout:
datasets/
└── phishing_validation/
    ├── source/
    │   └── Phishing_validation_emails.csv
    ├── emails/
    │   ├── mail_000001.eml
    │   ├── ...
    │   └── mail_000100.eml
    └── manifest.csv
"""
from __future__ import annotations

import csv
import datetime
from email.message import EmailMessage
from email.utils import format_datetime, formatdate, parsedate_to_datetime
from pathlib import Path
import random
import re

import pymupdf as fitz


ROOT = Path(__file__).resolve().parents[1]
DATASET_DIR = ROOT / "datasets" / "phishing_validation"
SOURCE_DIR = DATASET_DIR / "source"
EMAILS_DIR = DATASET_DIR / "emails"
INPUT_CSV = ROOT / "meajor_cleaned_preprocessed.csv"


COMMON_ENGLISH_WORDS = {
    "the", "to", "and", "a", "of", "in", "is", "you", "that", "it", "he",
    "was", "for", "on", "are", "as", "with", "his", "they", "i", "at",
    "be", "this", "have", "from", "or", "one", "had", "by", "word", "but",
    "not", "what", "all", "were", "we", "when", "your", "can", "said",
    "there", "use", "an", "each", "which", "she", "do", "how", "their",
    "if", "our", "will", "my", "me", "us", "please", "thanks", "team"
}


UNWANTED_WORDS = {
    "fuck", "porn", "sex", "viagra", "cialis", "horny", "adult", "dating",
    "erotic", "casino", "penis", "naked", "tadalafil", "soft tabs", "pills", "erection"
}


def score_coherence(text: str) -> float:
    words = [w.strip(".,;:!?\"'()[]{}") for w in text.lower().split()]
    words = [w for w in words if w]
    if len(words) < 20:
        return 0.0
    common_count = sum(1 for w in words if w in COMMON_ENGLISH_WORDS)
    return common_count / len(words)


def is_clean_readable(text: str, min_len: int = 70, max_len: int = 4000) -> bool:
    if not text:
        return False
    text_lower = text.lower()
    if any(w in text_lower for w in UNWANTED_WORDS):
        return False
    text = text.strip()
    if not (min_len <= len(text) <= max_len):
        return False
    if "<|EMOJI|>" in text or "<|SIMBOL|>" in text or "<|SYMBOL|>" in text:
        return False
    printable = sum(1 for c in text if 32 <= ord(c) <= 126 or c in "\n\r\t")
    if printable / len(text) < 0.94:
        return False
    return score_coherence(text) >= 0.28


def clean_body_text(body: str, urls_str: str) -> str:
    body = body.strip()
    body = body.replace("<|EMAIL_SEPARATOR|>", "\n\n")
    body = re.sub(r"<\|[A-Z0-9_]+\|>", "", body)

    if "[URL]" in body and urls_str and urls_str != "None":
        url_list = [u.strip().strip('"') for u in urls_str.splitlines() if u.strip().startswith("http")]
        for u in url_list:
            if "[URL]" in body:
                body = body.replace("[URL]", u, 1)
        body = body.replace("[URL]", "")

    body = re.sub(r"\n{3,}", "\n\n", body).strip()
    return body


def parse_rfc_date(date_str: str) -> str:
    if not date_str or date_str == "None":
        return formatdate(usegmt=True)
    try:
        dt = parsedate_to_datetime(date_str)
        return format_datetime(dt)
    except Exception:
        pass
    try:
        dt = datetime.datetime.fromisoformat(date_str)
        return format_datetime(dt)
    except Exception:
        pass
    return formatdate(usegmt=True)


def create_sample_pdf(title: str, text: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)  # A4
    page.insert_text((72, 72), title, fontsize=15)
    y = 120
    for line in text.splitlines():
        line_str = line.strip()
        if line_str:
            page.insert_text((72, y), line_str[:90], fontsize=10)
            y += 18
            if y > 780:
                break
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def select_candidates():
    print(f"Scanning and filtering {INPUT_CSV} for high-quality samples...")
    safe_buckets: dict[str, list[tuple[int, dict[str, str]]]] = {
        "safe_internal_communication": [],
        "safe_newsletter_and_links": [],
        "safe_business_invoice_discussion": [],
        "safe_multi_recipient": [],
        "safe_with_attachment": [],
    }
    phish_buckets: dict[str, list[tuple[int, dict[str, str]]]] = {
        "phishing_credential_harvesting": [],
        "phishing_financial_scam": [],
        "phishing_suspicious_urls": [],
        "phishing_social_engineering": [],
        "phishing_attachment_lure": [],
    }

    with open(INPUT_CSV, mode="r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for idx, r in enumerate(reader):
            subj = r.get("subject", "").strip()
            body = r.get("body", "").strip()
            lbl = r.get("label", "").strip()
            s_dom = r.get("sender_domain", "").strip()
            urls_str = r.get("urls", "")
            has_att = r.get("has_attachments", "").lower() == "true" or float(r.get("attachment_count", 0) or 0) > 0

            text_lower = (subj + " " + body).lower()
            s_lower = subj.lower()

            if not s_dom or not is_clean_readable(body, min_len=80, max_len=3500):
                continue
            if not subj or len(subj) < 4 or "<|" in subj or any(w in s_lower for w in UNWANTED_WORDS):
                continue

            has_url = float(r.get("url_count", 0) or 0) > 0 or ("http://" in urls_str or "https://" in urls_str)
            is_multi = ";" in r.get("receiver", "")

            if lbl == "0.0":
                if has_att:
                    safe_buckets["safe_with_attachment"].append((idx, r))
                elif is_multi and not has_url:
                    safe_buckets["safe_multi_recipient"].append((idx, r))
                elif any(w in text_lower for w in ["invoice", "billing", "expense report", "contract", "agreement", "budget review", "accounting", "purchase order"]) and not has_url:
                    safe_buckets["safe_business_invoice_discussion"].append((idx, r))
                elif has_url:
                    safe_buckets["safe_newsletter_and_links"].append((idx, r))
                else:
                    safe_buckets["safe_internal_communication"].append((idx, r))

            elif lbl == "1.0":
                if any(k in s_lower for k in ["invoice", "receipt", "pro-forma", "billing notice", "payment confirm", "account statement", "remittance"]):
                    phish_buckets["phishing_attachment_lure"].append((idx, r))
                elif any(w in text_lower for w in ["verify your account", "account access", "suspended account", "security update", "unauthorized access", "login to your account", "update your billing", "confirm your identity", "restore account"]):
                    phish_buckets["phishing_credential_harvesting"].append((idx, r))
                elif any(w in text_lower for w in ["lottery", "winner", "million dollars", "beneficiary", "inheritance", "wire transfer", "western union", "funds transfer", "compensation award"]):
                    phish_buckets["phishing_financial_scam"].append((idx, r))
                elif any(w in text_lower for w in ["strictly confidential", "urgent attention", "immediate response required", "legal action", "final notice", "penalty", "law enforcement"]):
                    phish_buckets["phishing_social_engineering"].append((idx, r))
                elif has_url:
                    phish_buckets["phishing_suspicious_urls"].append((idx, r))

    return safe_buckets, phish_buckets


def sample_balanced_dataset():
    safe_buckets, phish_buckets = select_candidates()

    rng = random.Random(42)

    quotas = {
        "safe_internal_communication": 15,
        "safe_newsletter_and_links": 15,
        "safe_business_invoice_discussion": 10,
        "safe_multi_recipient": 5,
        "safe_with_attachment": 5,
        "phishing_credential_harvesting": 15,
        "phishing_financial_scam": 12,
        "phishing_suspicious_urls": 10,
        "phishing_social_engineering": 8,
        "phishing_attachment_lure": 5,
    }

    selected_safe: list[tuple[str, int, dict[str, str]]] = []
    selected_phish: list[tuple[str, int, dict[str, str]]] = []

    for cat, quota in quotas.items():
        if cat.startswith("safe_"):
            pool = safe_buckets[cat]
            rng.shuffle(pool)
            chosen = pool[:quota]
            for idx, r in chosen:
                selected_safe.append((cat, idx, r))
        else:
            pool = phish_buckets[cat]
            rng.shuffle(pool)
            chosen = pool[:quota]
            for idx, r in chosen:
                selected_phish.append((cat, idx, r))

    assert len(selected_safe) == 50, f"Expected 50 safe, got {len(selected_safe)}"
    assert len(selected_phish) == 50, f"Expected 50 phish, got {len(selected_phish)}"

    combined = []
    for s, p in zip(selected_safe, selected_phish):
        combined.append(s)
        combined.append(p)

    return combined


def build_email(
    mail_id: str,
    category: str,
    orig_idx: int,
    row: dict[str, str],
) -> tuple[EmailMessage, dict[str, any]]:
    is_phish = row["label"].strip() == "1.0"
    sender_hash = row.get("sender", "")[:8] or "user"
    sender_domain = row.get("sender_domain", "").strip() or "example.org"
    receiver_hash = row.get("receiver", "")[:8] or "recipient"
    receiver_domain = row.get("receiver_domain", "").strip().split(";")[0] or "company.test"
    subject = row.get("subject", "").strip()
    urls_str = row.get("urls", "")
    date_header = parse_rfc_date(row.get("date", ""))

    msg = EmailMessage()
    msg["Message-ID"] = f"<{mail_id}@{sender_domain}>"
    msg["Date"] = date_header
    msg["Subject"] = subject

    if not is_phish:
        from_addr = f"employee_{sender_hash}@{sender_domain}"
        org_name = sender_domain.split(".")[0].capitalize()
        msg["From"] = f"\"{org_name} Team\" <{from_addr}>"
        to_addr = f"colleague_{receiver_hash}@{receiver_domain}"
        msg["To"] = to_addr
        spf_status = "pass"
        dkim_status = "pass"
        dmarc_status = "pass"
        msg["Authentication-Results"] = (
            f"mx.{receiver_domain}; spf=pass smtp.mailfrom={from_addr}; dkim=pass header.d={sender_domain}; dmarc=pass"
        )
        msg["Return-Path"] = f"<{from_addr}>"
        reply_to_addr = ""
    else:
        spf_status = "fail"
        dkim_status = "fail"
        dmarc_status = "fail"
        if category == "phishing_credential_harvesting":
            from_name = "Account Security Desk"
            from_addr = f"no-reply-alerts@{sender_domain}"
            reply_to_addr = "verify-account@secure-auth-login.top"
        elif category == "phishing_financial_scam":
            from_name = "Payment & Audit Committee"
            from_addr = f"notifications@{sender_domain}"
            reply_to_addr = "claims-disbursement@international-funds-transfer.xyz"
        elif category == "phishing_suspicious_urls":
            from_name = "Customer Support Update"
            from_addr = f"notice@{sender_domain}"
            reply_to_addr = "service-desk@portal-redirect-verify.biz"
        elif category == "phishing_social_engineering":
            from_name = "Office of the Director"
            from_addr = f"executive-notice@{sender_domain}"
            reply_to_addr = "confidential-channel@mail-direct-routing.online"
        else:  # phishing_attachment_lure
            from_name = "Electronic Billing System"
            from_addr = f"billing@{sender_domain}"
            reply_to_addr = "accounting-desk@payment-gateway-support.info"

        msg["From"] = f"\"{from_name}\" <{from_addr}>"
        msg["To"] = f"target-user@{receiver_domain}"
        if reply_to_addr:
            msg["Reply-To"] = reply_to_addr
        msg["Return-Path"] = f"<bounce@{sender_domain}>"
        msg["Authentication-Results"] = (
            f"mx.{receiver_domain}; spf=fail smtp.mailfrom={from_addr}; dkim=fail header.d={sender_domain}; dmarc=fail"
        )

    body_text = clean_body_text(row.get("body", ""), urls_str)

    attachment_added = False
    attachment_name = ""
    attachment_type = ""

    if category == "safe_with_attachment":
        attachment_name = f"quarterly_report_{mail_id}.pdf"
        attachment_type = "application/pdf"
        pdf_bytes = create_sample_pdf(
            f"OFFICIAL REPORT - {subject}",
            f"Reference: {mail_id}\nSender Domain: {sender_domain}\n\nSummary of operations:\n{body_text[:400]}\n\nStatus: Verified and approved by project coordinator.\nNo urgent action required.",
        )
        msg.set_content(body_text)
        msg.add_attachment(
            pdf_bytes,
            maintype="application",
            subtype="pdf",
            filename=attachment_name,
        )
        attachment_added = True

    elif category == "phishing_attachment_lure":
        attachment_name = f"invoice_notice_{mail_id}.pdf"
        attachment_type = "application/pdf"
        fake_url = "https://192.0.2.88/invoicing/pay?id=overdue-invoice"
        pdf_bytes = create_sample_pdf(
            f"URGENT PAYMENT DEMAND - {subject}",
            f"ACCOUNT NOTIFICATION: IMMEDIATE ATTENTION REQUIRED\n\n"
            f"Reference ID: {mail_id}\n"
            f"Outstanding Balance: $5,240.00 USD\n\n"
            f"Service termination will occur within 24 hours unless full payment is confirmed:\n"
            f"{fake_url}\n\n"
            f"Provide transaction confirmation code to billing desk.",
        )
        msg.set_content(body_text)
        msg.add_attachment(
            pdf_bytes,
            maintype="application",
            subtype="pdf",
            filename=attachment_name,
        )
        attachment_added = True

    else:
        msg.set_content(body_text)
        if "http://" in body_text or "https://" in body_text or "text/html" in row.get("content_types", ""):
            html_content = "<html><body>\n"
            for para in body_text.split("\n\n"):
                para_escaped = para.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                para_with_links = re.sub(
                    r"(https?://[^\s<>\"]+)",
                    r'<a href="\1">\1</a>',
                    para_escaped,
                )
                html_content += f"<p>{para_with_links}</p>\n"
            html_content += "</body></html>"
            msg.add_alternative(html_content, subtype="html")

    metadata = {
        "mail_id": mail_id,
        "file_name": f"{mail_id}.eml",
        "file_path": f"emails/{mail_id}.eml",
        "label": 1 if is_phish else 0,
        "label_name": "phishing" if is_phish else "safe",
        "category": category,
        "subject": subject,
        "sender": str(msg["From"]),
        "sender_domain": sender_domain,
        "receiver": str(msg["To"]),
        "receiver_domain": receiver_domain,
        "reply_to": reply_to_addr,
        "date": date_header,
        "url_count": int(float(row.get("url_count", 0) or 0)),
        "has_attachments": attachment_added,
        "attachment_name": attachment_name,
        "attachment_type": attachment_type,
        "spf_status": spf_status,
        "dkim_status": dkim_status,
        "dmarc_status": dmarc_status,
        "source": row.get("source", ""),
        "original_row_index": orig_idx,
    }

    return msg, metadata


def main():
    print("Selecting balanced candidates...")
    combined = sample_balanced_dataset()
    print(f"Selected {len(combined)} samples total.")

    EMAILS_DIR.mkdir(parents=True, exist_ok=True)
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)

    manifest_rows = []
    source_rows = []

    with open(INPUT_CSV, mode="r", encoding="utf-8", errors="replace") as f:
        reader = csv.reader(f)
        orig_header = next(reader)

    source_header = ["mail_id", "category"] + orig_header

    for i, (cat, orig_idx, row) in enumerate(combined, start=1):
        mail_id = f"mail_{i:06d}"
        msg, meta = build_email(mail_id, cat, orig_idx, row)

        eml_path = EMAILS_DIR / f"{mail_id}.eml"
        eml_path.write_bytes(msg.as_bytes())

        manifest_rows.append(meta)

        src_row = {"mail_id": mail_id, "category": cat}
        src_row.update(row)
        source_rows.append(src_row)

    source_csv_path = SOURCE_DIR / "Phishing_validation_emails.csv"
    with open(source_csv_path, mode="w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=source_header)
        writer.writeheader()
        writer.writerows(source_rows)
    print(f"Wrote {source_csv_path} with {len(source_rows)} rows.")

    manifest_csv_path = DATASET_DIR / "manifest.csv"
    manifest_fields = [
        "mail_id",
        "file_name",
        "file_path",
        "label",
        "label_name",
        "category",
        "subject",
        "sender",
        "sender_domain",
        "receiver",
        "receiver_domain",
        "reply_to",
        "date",
        "url_count",
        "has_attachments",
        "attachment_name",
        "attachment_type",
        "spf_status",
        "dkim_status",
        "dmarc_status",
        "source",
        "original_row_index",
    ]
    with open(manifest_csv_path, mode="w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=manifest_fields)
        writer.writeheader()
        writer.writerows(manifest_rows)
    print(f"Wrote {manifest_csv_path} with {len(manifest_rows)} rows.")

    print(f"Generated 100 .eml files in {EMAILS_DIR}")


if __name__ == "__main__":
    main()
