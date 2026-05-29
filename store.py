import sqlite3
from datetime import datetime, timezone

DB_PATH = "monitor.db"


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH)
    c.execute("""
        CREATE TABLE IF NOT EXISTS seen_posts (
            post_id     TEXT NOT NULL,
            category_id TEXT NOT NULL,
            seen_at     TEXT NOT NULL,
            PRIMARY KEY (post_id, category_id)
        )
    """)
    c.commit()
    return c


def is_seen(post_id: str, category_id: str) -> bool:
    with _conn() as c:
        return c.execute(
            "SELECT 1 FROM seen_posts WHERE post_id = ? AND category_id = ?",
            (post_id, category_id),
        ).fetchone() is not None


def mark_seen(post_id: str, category_id: str) -> None:
    with _conn() as c:
        c.execute(
            "INSERT OR IGNORE INTO seen_posts (post_id, category_id, seen_at) VALUES (?, ?, ?)",
            (post_id, category_id, datetime.now(timezone.utc).isoformat()),
        )
        c.commit()
