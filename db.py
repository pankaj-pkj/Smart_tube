"""SQLite storage layer. Ek hi file DB, koi external database nahi (budget friendly)."""

import json
import os
import sqlite3
import threading
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# DB_PATH env se badla ja sakta hai. Render/Docker jaise jagah par jahan project folder
# restart par reset ho jaata hai, isse DB ko mounted disk ke andar rakh sakte ho —
# warna har restart par saari keys, campaigns aur schedule mit jayenge.
DB_PATH = os.environ.get("DB_PATH") or os.path.join(BASE_DIR, "smarttube.db")

_local = threading.local()

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS campaigns (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    name             TEXT NOT NULL,
    platform         TEXT NOT NULL,              -- youtube | instagram | both
    video_path       TEXT NOT NULL,
    video_name       TEXT,
    thumb_path       TEXT,
    title_tpl        TEXT NOT NULL,
    description      TEXT,
    tags             TEXT,
    privacy          TEXT DEFAULT 'public',      -- public | unlisted | private
    category_id      TEXT DEFAULT '22',
    made_for_kids    INTEGER DEFAULT 0,
    comment_tpl      TEXT,
    pin_comment      INTEGER DEFAULT 0,
    ig_caption_tpl   TEXT,
    ig_comment_tpl   TEXT,
    ig_share_to_feed INTEGER DEFAULT 1,
    interval_minutes INTEGER NOT NULL DEFAULT 60,
    total_uploads    INTEGER NOT NULL DEFAULT 24,
    start_at         TEXT NOT NULL,              -- ISO UTC
    status           TEXT NOT NULL DEFAULT 'running',  -- running | paused | done
    created_at       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS uploads (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id   INTEGER NOT NULL,
    platform      TEXT NOT NULL,                 -- youtube | instagram
    seq           INTEGER NOT NULL,
    scheduled_at  TEXT NOT NULL,                 -- ISO UTC
    status        TEXT NOT NULL DEFAULT 'pending',
                  -- pending | running | success | failed | skipped
    title         TEXT,
    remote_id     TEXT,
    remote_url    TEXT,
    comment_id    TEXT,
    comment_text  TEXT,
    progress      INTEGER DEFAULT 0,
    attempts      INTEGER DEFAULT 0,
    error         TEXT,
    started_at    TEXT,
    finished_at   TEXT,
    FOREIGN KEY (campaign_id) REFERENCES campaigns (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_uploads_due
    ON uploads (status, scheduled_at);

CREATE TABLE IF NOT EXISTS logs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT NOT NULL,
    level       TEXT NOT NULL,                   -- info | warn | error
    source      TEXT,
    message     TEXT NOT NULL,
    campaign_id INTEGER,
    upload_id   INTEGER
);
"""


def utcnow():
    return datetime.now(timezone.utc).replace(microsecond=0)


def iso(dt):
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def parse_iso(text):
    if not text:
        return None
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def get_db():
    """Har thread ko apna connection (scheduler alag thread mein chalta hai)."""
    conn = getattr(_local, "conn", None)
    if conn is None:
        folder = os.path.dirname(DB_PATH)
        if folder:
            os.makedirs(folder, exist_ok=True)
        conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        _local.conn = conn
    return conn


def init_db():
    conn = get_db()
    conn.executescript(SCHEMA)
    conn.commit()


def query(sql, args=(), one=False):
    cur = get_db().execute(sql, args)
    rows = cur.fetchall()
    cur.close()
    if one:
        return rows[0] if rows else None
    return rows


def execute(sql, args=()):
    conn = get_db()
    cur = conn.execute(sql, args)
    conn.commit()
    last_id = cur.lastrowid
    cur.close()
    return last_id


# ---------------------------------------------------------------- settings


def get_setting(key, default=None):
    row = query("SELECT value FROM settings WHERE key = ?", (key,), one=True)
    return row["value"] if row else default


def set_setting(key, value):
    execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )


def get_config(key, env_key, default=""):
    """Pehle DB dekho, warna environment variable.

    Free hosting (Render free plan waghera) par project folder restart ke baad reset
    ho jaata hai, isliye /enter page se save ki hui keys gayab ho jaati hain. Env var
    mein rakhi keys restart ke baad bhi bachi rehti hain, isliye wo fallback hai.
    """
    return get_setting(key) or os.environ.get(env_key, "") or default


def get_json(key, default=None):
    raw = get_setting(key)
    if not raw:
        return default
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return default


def set_json(key, value):
    set_setting(key, json.dumps(value))


def delete_setting(key):
    execute("DELETE FROM settings WHERE key = ?", (key,))


# ---------------------------------------------------------------- logging


def log(message, level="info", source=None, campaign_id=None, upload_id=None):
    execute(
        "INSERT INTO logs (ts, level, source, message, campaign_id, upload_id) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (iso(utcnow()), level, source, str(message)[:4000], campaign_id, upload_id),
    )
    # Log table ko chhota rakho, sasta host disk bhar na jaye.
    execute(
        "DELETE FROM logs WHERE id < (SELECT MAX(id) - 2000 FROM logs)"
    )
