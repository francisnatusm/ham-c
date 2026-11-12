"""SQLite / Turso store for users, chats, messages, facts, and summaries."""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from hamc.db import connect_store_db


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class Store:
    def __init__(self, path: Path | None = None, *, conn=None, ephemeral: bool = False):
        """
        path: local SQLite file (ignored when Turso env vars are set).
        conn: optional pre-opened connection (tests).
        """
        if conn is not None:
            self.conn = conn
            self.path = path
            self.ephemeral = ephemeral
        else:
            local = path or Path("data") / "hamc.db"
            self.conn, self.ephemeral = connect_store_db(local)
            self.path = local
        self._migrate()

    def close(self) -> None:
        self.conn.close()

    def _migrate(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS chats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL DEFAULT 'New chat',
                created_at TEXT NOT NULL,
                deleted INTEGER NOT NULL DEFAULT 0,
                user_id INTEGER,
                guest_id TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                used_facts TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL,
                FOREIGN KEY (chat_id) REFERENCES chats(id)
            );
            CREATE TABLE IF NOT EXISTS facts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                source_chat_id INTEGER,
                status TEXT NOT NULL DEFAULT 'active',
                confirmed INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                user_id INTEGER,
                guest_id TEXT,
                FOREIGN KEY (source_chat_id) REFERENCES chats(id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
            CREATE TABLE IF NOT EXISTS summaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                text TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (chat_id) REFERENCES chats(id)
            );
            CREATE TABLE IF NOT EXISTS password_resets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL,
                code_hash TEXT NOT NULL,
                reset_token TEXT,
                attempts INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                used_at TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_password_resets_email
                ON password_resets(email);
            """
        )
        self._ensure_column("chats", "user_id", "INTEGER")
        self._ensure_column("chats", "guest_id", "TEXT")
        self._ensure_column("facts", "user_id", "INTEGER")
        self._ensure_column("facts", "guest_id", "TEXT")
        self._ensure_column("users", "display_name", "TEXT")
        self._ensure_column("users", "nickname", "TEXT")
        self.conn.commit()

    def _ensure_column(self, table: str, column: str, decl: str) -> None:
        cols = set()
        for r in self.conn.execute(f"PRAGMA table_info({table})").fetchall():
            d = dict(r)
            name = d.get("name") or d.get("Name") or d.get("0")
            if name is None and len(d) >= 2:
                # pragma tuple order: cid, name, type, ...
                vals = list(d.values())
                name = vals[1] if len(vals) > 1 else vals[0]
            if name is not None:
                cols.add(str(name))
        if column not in cols:
            self.conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")

    def _as_dict(self, row) -> dict | None:
        if row is None:
            return None
        return {str(k): v for k, v in dict(row).items()}

    def _as_fact(self, row) -> dict | None:
        """Normalize fact rows. Quote-safe for Turso/libSQL (`key` is awkward)."""
        d = self._as_dict(row)
        if not d:
            return None
        lower = {str(k).lower(): v for k, v in d.items()}
        fact_key = lower.get("key", lower.get("fact_key"))
        value = lower.get("value")
        if fact_key is None or value is None:
            return None
        return {
            "id": lower.get("id"),
            "key": str(fact_key),
            "value": str(value),
            "source_chat_id": lower.get("source_chat_id"),
            "status": lower.get("status"),
            "confirmed": lower.get("confirmed"),
            "created_at": lower.get("created_at"),
            "updated_at": lower.get("updated_at"),
            "user_id": lower.get("user_id"),
            "guest_id": lower.get("guest_id"),
        }

    # --- users ---
    def create_user(
        self,
        email: str,
        password_hash: str,
        display_name: str | None = None,
        nickname: str | None = None,
    ) -> dict:
        email = email.strip().lower()
        name = (display_name or email.split("@")[0]).strip()[:80] or "User"
        nick = (nickname or name.split()[0]).strip()[:40] or "User"
        cur = self.conn.execute(
            """
            INSERT INTO users (email, password_hash, created_at, display_name, nickname)
            VALUES (?, ?, ?, ?, ?)
            """,
            (email, password_hash, utc_now(), name, nick),
        )
        self.conn.commit()
        return self.get_user(cur.lastrowid)

    def get_user(self, user_id: int) -> dict | None:
        row = self.conn.execute(
            "SELECT id, email, display_name, nickname, created_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        return dict(row) if row else None

    def get_user_by_email(self, email: str) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM users WHERE email = ?", (email.strip().lower(),)
        ).fetchone()
        return dict(row) if row else None

    def update_user_profile(
        self,
        user_id: int,
        display_name: str,
        nickname: str | None = None,
    ) -> dict | None:
        name = display_name.strip()[:80]
        if not name:
            return None
        nick = (nickname if nickname is not None else name.split()[0]).strip()[:40]
        if not nick:
            return None
        self.conn.execute(
            "UPDATE users SET display_name = ?, nickname = ? WHERE id = ?",
            (name, nick, user_id),
        )
        self.conn.commit()
        return self.get_user(user_id)

    def update_user_password(self, user_id: int, password_hash: str) -> bool:
        cur = self.conn.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (password_hash, user_id),
        )
        self.conn.commit()
        return cur.rowcount > 0

    # --- password reset ---
    def create_password_reset(
        self, email: str, code_hash: str, expires_at: str
    ) -> int:
        email = email.strip().lower()
        # Invalidate older unused codes for this email
        self.conn.execute(
            """
            UPDATE password_resets
            SET used_at = ?
            WHERE email = ? AND used_at IS NULL
            """,
            (utc_now(), email),
        )
        cur = self.conn.execute(
            """
            INSERT INTO password_resets
                (email, code_hash, created_at, expires_at)
            VALUES (?, ?, ?, ?)
            """,
            (email, code_hash, utc_now(), expires_at),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def latest_password_reset(self, email: str) -> dict | None:
        row = self.conn.execute(
            """
            SELECT * FROM password_resets
            WHERE email = ? AND used_at IS NULL
            ORDER BY id DESC LIMIT 1
            """,
            (email.strip().lower(),),
        ).fetchone()
        return dict(row) if row else None

    def bump_password_reset_attempts(self, reset_id: int) -> None:
        self.conn.execute(
            "UPDATE password_resets SET attempts = attempts + 1 WHERE id = ?",
            (reset_id,),
        )
        self.conn.commit()

    def set_password_reset_token(self, reset_id: int, reset_token: str) -> None:
        self.conn.execute(
            "UPDATE password_resets SET reset_token = ? WHERE id = ?",
            (reset_token, reset_id),
        )
        self.conn.commit()

    def get_password_reset_by_token(self, email: str, reset_token: str) -> dict | None:
        row = self.conn.execute(
            """
            SELECT * FROM password_resets
            WHERE email = ? AND reset_token = ? AND used_at IS NULL
            ORDER BY id DESC LIMIT 1
            """,
            (email.strip().lower(), reset_token),
        ).fetchone()
        return dict(row) if row else None

    def mark_password_reset_used(self, reset_id: int) -> None:
        self.conn.execute(
            "UPDATE password_resets SET used_at = ? WHERE id = ?",
            (utc_now(), reset_id),
        )
        self.conn.commit()

    def delete_user(self, user_id: int) -> bool:
        """Remove account and soft-delete that user's chats/facts."""
        now = utc_now()
        user = self.get_user(user_id)
        if not user:
            return False
        chat_ids = [
            r["id"]
            for r in self.conn.execute(
                "SELECT id FROM chats WHERE user_id = ?", (user_id,)
            ).fetchall()
        ]
        self.conn.execute(
            "UPDATE facts SET status = 'deleted', updated_at = ? WHERE user_id = ?",
            (now, user_id),
        )
        if chat_ids:
            placeholders = ",".join("?" * len(chat_ids))
            self.conn.execute(
                f"UPDATE chats SET deleted = 1 WHERE id IN ({placeholders})",
                chat_ids,
            )
        self.conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        self.conn.commit()
        return True

    def _owner_clause(self, user_id: int | None, guest_id: str | None, alias: str = "") -> tuple[str, tuple]:
        prefix = f"{alias}." if alias else ""
        if user_id is not None:
            return f"{prefix}user_id = ?", (user_id,)
        if guest_id:
            return f"{prefix}guest_id = ? AND {prefix}user_id IS NULL", (guest_id,)
        return "1 = 0", ()

    def owns_chat(self, chat_id: int, user_id: int | None, guest_id: str | None) -> bool:
        clause, args = self._owner_clause(user_id, guest_id)
        row = self.conn.execute(
            f"SELECT id FROM chats WHERE id = ? AND deleted = 0 AND ({clause})",
            (chat_id, *args),
        ).fetchone()
        return row is not None

    def owns_fact(self, fact_id: int, user_id: int | None, guest_id: str | None) -> bool:
        clause, args = self._owner_clause(user_id, guest_id)
        row = self.conn.execute(
            f"SELECT id FROM facts WHERE id = ? AND ({clause})",
            (fact_id, *args),
        ).fetchone()
        return row is not None

    def create_chat(
        self,
        title: str = "New chat",
        user_id: int | None = None,
        guest_id: str | None = None,
    ) -> dict:
        cur = self.conn.execute(
            """
            INSERT INTO chats (title, created_at, user_id, guest_id)
            VALUES (?, ?, ?, ?)
            """,
            (title, utc_now(), user_id, guest_id if user_id is None else None),
        )
        self.conn.commit()
        return self.get_chat(cur.lastrowid, user_id=user_id, guest_id=guest_id)

    def get_chat(
        self,
        chat_id: int,
        user_id: int | None = None,
        guest_id: str | None = None,
    ) -> dict | None:
        if user_id is None and not guest_id:
            row = self.conn.execute(
                "SELECT * FROM chats WHERE id = ? AND deleted = 0", (chat_id,)
            ).fetchone()
            return dict(row) if row else None
        clause, args = self._owner_clause(user_id, guest_id)
        row = self.conn.execute(
            f"SELECT * FROM chats WHERE id = ? AND deleted = 0 AND ({clause})",
            (chat_id, *args),
        ).fetchone()
        return dict(row) if row else None

    def list_chats(self, user_id: int | None = None, guest_id: str | None = None) -> list[dict]:
        clause, args = self._owner_clause(user_id, guest_id)
        rows = self.conn.execute(
            f"SELECT * FROM chats WHERE deleted = 0 AND ({clause}) ORDER BY id DESC",
            args,
        ).fetchall()
        return [dict(r) for r in rows]

    def set_chat_title(self, chat_id: int, title: str) -> None:
        self.conn.execute(
            "UPDATE chats SET title = ? WHERE id = ?", (title[:80], chat_id)
        )
        self.conn.commit()

    def add_message(
        self, chat_id: int, role: str, content: str, used_facts: list | None = None
    ) -> dict:
        payload = json.dumps(used_facts or [])
        cur = self.conn.execute(
            """
            INSERT INTO messages (chat_id, role, content, used_facts, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (chat_id, role, content, payload, utc_now()),
        )
        self.conn.commit()
        row = self.conn.execute(
            "SELECT * FROM messages WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
        return self._message(row)

    def list_messages(self, chat_id: int) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM messages WHERE chat_id = ? ORDER BY id", (chat_id,)
        ).fetchall()
        return [self._message(r) for r in rows]

    def _message(self, row) -> dict:
        item = dict(row)
        item["used_facts"] = json.loads(item.get("used_facts") or "[]")
        return item

    def latest_summary(self, chat_id: int) -> str | None:
        row = self.conn.execute(
            "SELECT text FROM summaries WHERE chat_id = ? ORDER BY id DESC LIMIT 1",
            (chat_id,),
        ).fetchone()
        return row["text"] if row else None

    def add_summary(self, chat_id: int, text: str) -> None:
        self.conn.execute(
            "INSERT INTO summaries (chat_id, text, created_at) VALUES (?, ?, ?)",
            (chat_id, text, utc_now()),
        )
        self.conn.commit()

    def upsert_fact(
        self,
        key: str,
        value: str,
        source_chat_id: int,
        confirmed: bool = False,
        user_id: int | None = None,
        guest_id: str | None = None,
    ) -> dict:
        key = key.strip().lower()
        value = value.strip()
        now = utc_now()
        clause, args = self._owner_clause(user_id, guest_id)
        # Quote "key" — reserved-ish on Turso/libSQL and caused KeyError 'key' in prod
        existing = self.conn.execute(
            f'SELECT * FROM facts WHERE "key" = ? AND status = \'active\' AND ({clause})',
            (key, *args),
        ).fetchone()
        if existing:
            ex = self._as_fact(existing) or self._as_dict(existing) or {}
            ex_id = ex.get("id")
            if ex_id is not None:
                self.conn.execute(
                    """
                    UPDATE facts
                    SET status = 'superseded', updated_at = ?
                    WHERE id = ?
                    """,
                    (now, ex_id),
                )
        self.conn.execute(
            """
            INSERT INTO facts
                ("key", value, source_chat_id, status, confirmed, created_at, updated_at, user_id, guest_id)
            VALUES (?, ?, ?, 'active', ?, ?, ?, ?, ?)
            """,
            (
                key,
                value,
                source_chat_id,
                1 if confirmed else 0,
                now,
                now,
                user_id,
                guest_id if user_id is None else None,
            ),
        )
        self.conn.commit()
        # Re-fetch by owner + key (do not trust lastrowid on Turso)
        row = self.conn.execute(
            f"""
            SELECT * FROM facts
            WHERE "key" = ? AND status = 'active' AND ({clause})
            ORDER BY id DESC LIMIT 1
            """,
            (key, *args),
        ).fetchone()
        fact = self._as_fact(row)
        if fact:
            return fact
        # Absolute fallback so the demo never dies on a driver quirk
        return {
            "id": None,
            "key": key,
            "value": value,
            "source_chat_id": source_chat_id,
            "status": "active",
            "confirmed": 1 if confirmed else 0,
            "created_at": now,
            "updated_at": now,
            "user_id": user_id,
            "guest_id": guest_id if user_id is None else None,
        }

    def active_facts(
        self, user_id: int | None = None, guest_id: str | None = None
    ) -> list[dict]:
        clause, args = self._owner_clause(user_id, guest_id)
        rows = self.conn.execute(
            f"""
            SELECT * FROM facts
            WHERE status = 'active' AND ({clause})
            ORDER BY updated_at DESC, id DESC
            """,
            args,
        ).fetchall()
        out = []
        for r in rows:
            fact = self._as_fact(r)
            if fact:
                out.append(fact)
        return out

    def get_fact(self, fact_id: int) -> dict | None:
        row = self.conn.execute("SELECT * FROM facts WHERE id = ?", (fact_id,)).fetchone()
        return self._as_fact(row)

    def delete_fact(self, fact_id: int) -> dict | None:
        fact = self.get_fact(fact_id)
        if not fact:
            return None
        self.conn.execute(
            "UPDATE facts SET status = 'deleted', updated_at = ? WHERE id = ?",
            (utc_now(), fact_id),
        )
        self.conn.commit()
        return self.get_fact(fact_id)

    def delete_chat(self, chat_id: int) -> list[dict]:
        """Delete the chat and every fact that came from it."""
        now = utc_now()
        rows = self.conn.execute(
            """
            SELECT * FROM facts
            WHERE source_chat_id = ? AND status = 'active'
            """,
            (chat_id,),
        ).fetchall()
        removed = [f for f in (self._as_fact(r) for r in rows) if f]
        self.conn.execute(
            "UPDATE facts SET status = 'deleted', updated_at = ? WHERE source_chat_id = ? AND status = 'active'",
            (now, chat_id),
        )
        self.conn.execute(
            "UPDATE chats SET deleted = 1 WHERE id = ?", (chat_id,)
        )
        self.conn.commit()
        return removed
