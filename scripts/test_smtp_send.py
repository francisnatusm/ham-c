"""One-shot SMTP test: sends a short mail to SMTP_USER."""

from pathlib import Path
import sys

from dotenv import load_dotenv
import os

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from hamc.mailer import send_email, smtp_configured, public_app_url

if not smtp_configured():
    print("SMTP not configured")
    raise SystemExit(1)

to_addr = os.getenv("SMTP_USER", "").strip()
link = public_app_url()
ok = send_email(
    to_addr,
    "HAM-C SMTP test",
    f"SMTP works. Open HAM-C: {link}\n",
    f"<p>SMTP works.</p><p><a href='{link}'>Open HAM-C</a></p>",
)
print("sent_ok:", ok, "to:", to_addr)
raise SystemExit(0 if ok else 1)
