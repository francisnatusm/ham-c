"""Database connection helpers: local SQLite or persistent Turso/libSQL."""

from __future__ import annotations

import logging
import os
import sqlite3
from pathlib import Path

log = logging.getLogger(__name__)

# Set True when running on Vercel with only /tmp SQLite (data will vanish).
EPHEMERAL_DB = False


class DictRow(dict):
    """sqlite3.Row-like mapping that also allows integer index access."""

    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)

    def keys(self):
        return super().keys()


class CompatCursor:
    def __init__(self, cursor):
        self._cursor = cursor
        self.description = getattr(cursor, "description", None)
        self.lastrowid = getattr(cursor, "lastrowid", None)
        self.rowcount = getattr(cursor, "rowcount", -1)

    def _wrap_row(self, row):
        if row is None:
            return None
        if isinstance(row, dict):
            return DictRow(row)
        cols = [d[0] for d in (self.description or [])]
        return DictRow(zip(cols, row))

    def fetchone(self):
        return self._wrap_row(self._cursor.fetchone())

    def fetchall(self):
        rows = self._cursor.fetchall() or []
        return [self._wrap_row(r) for r in rows]

    def execute(self, sql, params=()):
        self._cursor.execute(sql, params)
        self.description = getattr(self._cursor, "description", None)
        self.lastrowid = getattr(self._cursor, "lastrowid", None)
        self.rowcount = getattr(self._cursor, "rowcount", -1)
        return self


class CompatConnection:
    """Make libsql connections behave like sqlite3 (dict rows + helpers)."""

    def __init__(self, conn):
        self._conn = conn

    def execute(self, sql, params=()):
        cur = self._conn.execute(sql, params)
        return CompatCursor(cur)

    def executescript(self, script: str):
        if hasattr(self._conn, "executescript"):
            self._conn.executescript(script)
            return
        for part in script.split(";"):
            stmt = part.strip()
            if stmt:
                self._conn.execute(stmt)

    def commit(self):
        self._conn.commit()

    def close(self):
        self._conn.close()


def turso_configured() -> bool:
    url = (os.getenv("TURSO_DATABASE_URL") or os.getenv("LIBSQL_URL") or "").strip()
    token = (os.getenv("TURSO_AUTH_TOKEN") or os.getenv("LIBSQL_AUTH_TOKEN") or "").strip()
    return bool(url and token)


def connect_store_db(local_path: Path):
    """
    Return (connection, ephemeral: bool).

    Prefer Turso/libSQL when TURSO_DATABASE_URL + TURSO_AUTH_TOKEN are set.
    Locally, use a normal SQLite file. On Vercel without Turso, /tmp is used
    but marked ephemeral (accounts will not survive cold starts).
    """
    global EPHEMERAL_DB
    url = (os.getenv("TURSO_DATABASE_URL") or os.getenv("LIBSQL_URL") or "").strip()
    token = (os.getenv("TURSO_AUTH_TOKEN") or os.getenv("LIBSQL_AUTH_TOKEN") or "").strip()

    if url and token:
        import libsql

        raw = libsql.connect(database=url, auth_token=token)
        EPHEMERAL_DB = False
        log.info("Connected to persistent Turso/libSQL database")
        return CompatConnection(raw), False

    on_vercel = bool(os.getenv("VERCEL"))
    if on_vercel:
        path = Path("/tmp/hamc.db")
        EPHEMERAL_DB = True
        log.error(
            "VERCEL without TURSO_DATABASE_URL/TURSO_AUTH_TOKEN — "
            "using /tmp/hamc.db (WIPED on cold start). Accounts will disappear."
        )
    else:
        path = local_path
        path.parent.mkdir(parents=True, exist_ok=True)
        EPHEMERAL_DB = False
        log.info("Connected to local SQLite at %s", path)

    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn, EPHEMERAL_DB
