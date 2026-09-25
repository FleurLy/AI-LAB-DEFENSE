from email.message import EmailMessage

from email_pipeline.mail.parser import MailParser


def test_simple_text_email_is_parsed() -> None:
    message = EmailMessage()
    message["From"] = "Alice <alice@example.org>"
    message["To"] = "Bob <bob@example.net>"
    message["Cc"] = "team@example.net"
    message["Reply-To"] = "Help <help@example.org>"
    message["Subject"] = "Café et sécurité"
    message.set_content("Bonjour à tous")

    parsed = MailParser().parse(message.as_bytes())

    assert parsed.from_name == "Alice"
    assert parsed.from_address == "alice@example.org"
    assert parsed.reply_to_address == "help@example.org"
    assert parsed.to == ["bob@example.net"]
    assert parsed.cc == ["team@example.net"]
    assert parsed.subject == "Café et sécurité"
    assert parsed.body_text == "Bonjour à tous"


def test_html_only_email_gets_readable_text_with_link() -> None:
    message = EmailMessage()
    message["From"] = "sender@example.org"
    message["To"] = "reader@example.net"
    message["Subject"] = "HTML"
    message.set_content(
        '<html><body><p>Bienvenue</p><a href="https://example.org/login">Connexion</a></body></html>',
        subtype="html",
    )

    parsed = MailParser().parse(message.as_bytes())

    assert "Bienvenue" in parsed.body_text
    assert "Connexion (https://example.org/login)" in parsed.body_text
    assert parsed.body_html.startswith("<html>")
    assert parsed.body_text_derived_from_html is True


def test_multipart_attachment_is_separated() -> None:
    message = EmailMessage()
    message["From"] = "sender@example.org"
    message["To"] = "reader@example.net"
    message.set_content("Body")
    message.add_attachment(b"hello", maintype="application", subtype="octet-stream", filename="note.bin")

    parsed = MailParser().parse(message.as_bytes())

    assert parsed.body_text == "Body"
    assert len(parsed.attachments) == 1
    assert parsed.attachments[0].filename == "note.bin"
    assert parsed.attachments[0].payload == b"hello"
