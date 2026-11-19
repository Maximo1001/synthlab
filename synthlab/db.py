"""Acceso a SQLite. Una conexión por petición, WAL, claves foráneas y busy_timeout."""

from __future__ import annotations

import contextlib
import sqlite3
import time
from importlib import resources
from pathlib import Path

from flask import current_app, g


def now() -> int:
    return int(time.time())


def connect(path: str) -> sqlite3.Connection:
    con = sqlite3.connect(path, timeout=10, isolation_level=None)  # autocommit; tx explícitas
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("PRAGMA busy_timeout = 5000")
    return con


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = connect(current_app.config["DATABASE"])
    return g.db


def close_db(_exc: BaseException | None = None) -> None:
    con = g.pop("db", None)
    if con is not None:
        con.close()


def init_db(path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    con = connect(path)
    try:
        con.execute("PRAGMA journal_mode = WAL")
        schema = resources.files("synthlab").joinpath("schema.sql").read_text(encoding="utf-8")
        con.executescript(schema)
    finally:
        con.close()
    with contextlib.suppress(OSError):  # BD con hashes y PII: sólo legible por el servicio
        Path(path).chmod(0o600)


def query_one(sql: str, params: tuple = ()) -> sqlite3.Row | None:
    return get_db().execute(sql, params).fetchone()


def query_all(sql: str, params: tuple = ()) -> list[sqlite3.Row]:
    return get_db().execute(sql, params).fetchall()


def execute(sql: str, params: tuple = ()) -> sqlite3.Cursor:
    return get_db().execute(sql, params)
