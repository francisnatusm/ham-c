"""Send account emails over SMTP (welcome + deletion)."""

from __future__ import annotations

import logging
import os
import smtplib
import ssl
from email.message import EmailMessage
from html import escape
from threading import Thread

log = logging.getLogger(__name__)


def smtp_configured() -> bool:
    return bool(os.getenv("SMTP_HOST") and os.getenv("SMTP_USER") and os.getenv("SMTP_PASSWORD"))


def public_app_url() -> str:
    return (os.getenv("HAMC_PUBLIC_URL") or "http://127.0.0.1:5000").rstrip("/")


def _send(msg: EmailMessage) -> None:
    host = os.getenv("SMTP_HOST", "")
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER", "")
    password = os.getenv("SMTP_PASSWORD", "")
    use_ssl = os.getenv("SMTP_SSL", "").lower() in {"1", "true", "yes"}
    context = ssl.create_default_context()
    if use_ssl or port == 465:
        with smtplib.SMTP_SSL(host, port, context=context, timeout=20) as smtp:
            smtp.login(user, password)
            smtp.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=20) as smtp:
            smtp.ehlo()
            smtp.starttls(context=context)
            smtp.ehlo()
            smtp.login(user, password)
            smtp.send_message(msg)


def _from_header() -> str:
    explicit = os.getenv("SMTP_FROM", "").strip()
    if explicit:
        return explicit
    user = os.getenv("SMTP_USER", "").strip()
    return f"HAM-C <{user}>" if user else "HAM-C"


def send_email(to_email: str, subject: str, text_body: str, html_body: str) -> bool:
    if not smtp_configured():
        log.warning("SMTP not configured; skipped email to %s (%s)", to_email, subject)
        return False
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = _from_header()
    msg["To"] = to_email
    msg.set_content(text_body)
    msg.add_alternative(html_body, subtype="html")
    try:
        _send(msg)
        log.info("Sent email to %s (%s)", to_email, subject)
        return True
    except Exception:
        log.exception("Failed to send email to %s (%s)", to_email, subject)
        return False


def send_email_async(to_email: str, subject: str, text_body: str, html_body: str) -> None:
    Thread(
        target=send_email,
        args=(to_email, subject, text_body, html_body),
        daemon=True,
    ).start()


def send_welcome_email(to_email: str, display_name: str, nickname: str) -> None:
    link = public_app_url()
    name = display_name or nickname or "there"
    safe = escape(name)
    subject = "Welcome to HAM-C — your account is ready"
    text = (
        f"Hi {name},\n\n"
        "Thank you for creating a HAM-C account.\n"
        "Your account was created successfully.\n\n"
        f"Open HAM-C here:\n{link}\n\n"
        "Sign in with the email and password you registered.\n\n"
        "— HAM-C\n"
        "Hierarchical Auditable Memory for ChatGPT\n"
    )
    html = f"""\
<html>
  <body style="font-family:Segoe UI,Arial,sans-serif;color:#0b1f3a;line-height:1.5;">
    <h2 style="color:#0b1f3a;">Welcome to HAM-C</h2>
    <p>Hi {safe},</p>
    <p>Thank you for creating a HAM-C account. Your account was created successfully.</p>
    <p>
      <a href="{escape(link)}" style="display:inline-block;padding:10px 16px;background:#1f6fb2;color:#fff;text-decoration:none;border-radius:8px;">
        Open HAM-C
      </a>
    </p>
    <p style="color:#556;">Or copy this link: <a href="{escape(link)}">{escape(link)}</a></p>
    <p>Sign in with the email and password you registered.</p>
    <p style="margin-top:24px;color:#556;font-size:13px;">
      — HAM-C<br>Hierarchical Auditable Memory for ChatGPT
    </p>
  </body>
</html>
"""
    send_email_async(to_email, subject, text, html)


def send_account_deleted_email(to_email: str, display_name: str, nickname: str) -> None:
    link = public_app_url()
    name = display_name or nickname or "there"
    safe = escape(name)
    subject = "Your HAM-C account has been deleted"
    text = (
        f"Hi {name},\n\n"
        "This confirms that your HAM-C account has been deleted.\n"
        "Your chats and saved facts for that account were removed.\n\n"
        "If you want to use HAM-C again, you can create a new account here:\n"
        f"{link}\n\n"
        "— HAM-C\n"
    )
    html = f"""\
<html>
  <body style="font-family:Segoe UI,Arial,sans-serif;color:#0b1f3a;line-height:1.5;">
    <h2 style="color:#0b1f3a;">Account deleted</h2>
    <p>Hi {safe},</p>
    <p>This confirms that your HAM-C account has been deleted. Your chats and saved facts for that account were removed.</p>
    <p>If you want to use HAM-C again, you can create a new account:</p>
    <p>
      <a href="{escape(link)}" style="display:inline-block;padding:10px 16px;background:#1f6fb2;color:#fff;text-decoration:none;border-radius:8px;">
        Open HAM-C
      </a>
    </p>
    <p style="color:#556;">Or copy this link: <a href="{escape(link)}">{escape(link)}</a></p>
    <p style="margin-top:24px;color:#556;font-size:13px;">— HAM-C</p>
  </body>
</html>
"""
    send_email_async(to_email, subject, text, html)
