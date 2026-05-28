import sqlite3
from datetime import datetime, timezone

DB_PATH = "monitor.db"

def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH)
    c.execute("""
        CREATE TABLE IF NOT EXISTS seen_posts (
            post_id TEXT PRIMARY KEY,
            notified_at TEXT NOT NULL
        )
    """)
    c.commit()
    return c

def is_seen(post_id: str) -> bool:
    with _conn() as c:
        return c.execute(
            "SELECT 1 FROM seen_posts WHERE post_id = ?", (post_id,)
        ).fetchone() is not None

def mark_seen(post_id: str) -> None:
    with _conn() as c:
        c.execute(
            "INSERT OR IGNORE INTO seen_posts (post_id, notified_at) VALUES (?, ?)",
            (post_id, datetime.now(timezone.utc).isoformat()),
        )
        c.commit()
