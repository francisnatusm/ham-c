from pathlib import Path
import sys

from dotenv import dotenv_values, load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")
v = dotenv_values(ROOT / ".env")

placeholders = {
    "SMTP_USER": "your.email@gmail.com",
    "SMTP_PASSWORD": "your-16-char-app-password",
    "SMTP_FROM": "HAM-C <your.email@gmail.com>",
}

for key in (
    "SMTP_HOST",
    "SMTP_PORT",
    "SMTP_USER",
    "SMTP_PASSWORD",
    "SMTP_FROM",
    "HAMC_PUBLIC_URL",
):
    val = (v.get(key) or "").strip()
    if not val:
        print(f"{key}: EMPTY")
    elif placeholders.get(key) == val:
        print(f"{key}: STILL PLACEHOLDER")
    else:
        print(f"{key}: set ({len(val)} chars)")

from hamc.mailer import smtp_configured

print("smtp_configured:", smtp_configured())
