import json
import os
import sqlite3
from datetime import datetime, timezone

DB_PATH = os.environ.get("DB_PATH", "./troubleshooter.db")

_conn = None


def conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
        _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _init(_conn)
    return _conn


def _init(c):
    c.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS investigations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL REFERENCES users(id),
        namespace TEXT NOT NULL,
        deployment TEXT,
        cluster_context TEXT,
        status TEXT NOT NULL DEFAULT 'queued',
        failure_pattern TEXT,
        root_cause TEXT,
        confidence INTEGER,
        fix_commands TEXT,
        error TEXT,
        created_at TEXT NOT NULL
    );
    """)
    c.commit()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_user(username, password_hash) -> int:
    cur = conn().execute(
        "INSERT INTO users (username, password_hash, created_at) VALUES (?,?,?)",
        (username, password_hash, _now()),
    )
    conn().commit()
    return cur.lastrowid


def get_user(username):
    row = conn().execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    return dict(row) if row else None


def create_investigation(user_id, namespace, deployment, cluster_context=None) -> int:
    cur = conn().execute(
        "INSERT INTO investigations (user_id, namespace, deployment, cluster_context, created_at) "
        "VALUES (?,?,?,?,?)",
        (user_id, namespace, deployment, cluster_context, _now()),
    )
    conn().commit()
    return cur.lastrowid


def update_investigation(inv_id, **fields):
    if "fix_commands" in fields and fields["fix_commands"] is not None:
        fields["fix_commands"] = json.dumps(fields["fix_commands"])
    sets = ", ".join(f"{k}=?" for k in fields)
    conn().execute(
        f"UPDATE investigations SET {sets} WHERE id=?",
        (*fields.values(), inv_id),
    )
    conn().commit()


def get_investigation(inv_id, user_id):
    row = conn().execute(
        "SELECT * FROM investigations WHERE id=? AND user_id=?", (inv_id, user_id)
    ).fetchone()
    return _hydrate(row)


def list_investigations(user_id):
    rows = conn().execute(
        "SELECT * FROM investigations WHERE user_id=? ORDER BY id DESC LIMIT 50", (user_id,)
    ).fetchall()
    return [_hydrate(r) for r in rows]


def _hydrate(row):
    if row is None:
        return None
    d = dict(row)
    if d.get("fix_commands"):
        d["fix_commands"] = json.loads(d["fix_commands"])
    return d
