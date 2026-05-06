"""SQLite-backed idempotency store for processed reactions."""

from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path


class ProcessedStore:
    def __init__(self, db_path: str):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._db_path = db_path
        self._lock = threading.Lock()
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS processed_reactions (
                    channel TEXT NOT NULL,
                    message_ts TEXT NOT NULL,
                    PRIMARY KEY (channel, message_ts)
                )
                """
            )
            conn.commit()

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self._db_path, timeout=10.0)
        try:
            yield conn
        finally:
            conn.close()

    def claim(self, channel: str, message_ts: str) -> bool:
        """Atomically claim a (channel, ts). Returns True on first claim, False if already claimed."""
        with self._lock, self._connect() as conn:
            try:
                conn.execute(
                    "INSERT INTO processed_reactions (channel, message_ts) VALUES (?, ?)",
                    (channel, message_ts),
                )
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                return False
