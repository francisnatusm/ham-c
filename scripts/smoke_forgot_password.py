"""Smoke-test forgot-password verify + reset without SMTP."""
from __future__ import annotations

import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from werkzeug.security import check_password_hash, generate_password_hash

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hamc.store import Store  # noqa: E402


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        store = Store(Path(tmp) / "t.db")
        user = store.create_user(
            "reset.user@example.com",
            generate_password_hash("oldpass1"),
            display_name="Reset User",
            nickname="Reset",
        )
        code = "123456"
        expires = (datetime.now(timezone.utc) + timedelta(minutes=15)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        rid = store.create_password_reset(
            user["email"], generate_password_hash(code), expires
        )
        row = store.latest_password_reset(user["email"])
        assert row and row["id"] == rid
        assert check_password_hash(row["code_hash"], code)

        token = "test-reset-token"
        store.set_password_reset_token(rid, token)
        got = store.get_password_reset_by_token(user["email"], token)
        assert got and got["id"] == rid

        store.update_user_password(user["id"], generate_password_hash("newpass1"))
        store.mark_password_reset_used(rid)
        auth = store.get_user_by_email(user["email"])
        assert check_password_hash(auth["password_hash"], "newpass1")
        assert not check_password_hash(auth["password_hash"], "oldpass1")
        assert store.latest_password_reset(user["email"]) is None
        store.close()
        print("ok forgot-password store flow")


if __name__ == "__main__":
    main()
