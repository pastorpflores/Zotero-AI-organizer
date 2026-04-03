import sqlite3
import datetime
from pathlib import Path

class StateManager:
    def __init__(self, db_path: str = "processed.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize the processed items database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS processed_items (
                    item_id TEXT,
                    action TEXT,
                    timestamp DATETIME,
                    PRIMARY KEY (item_id, action)
                )
            """)

    def is_processed(self, item_id: str, action: str) -> bool:
        """Check if an item has already been processed for a specific action."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT 1 FROM processed_items WHERE item_id = ? AND action = ?",
                (str(item_id), action)
            )
            return cursor.fetchone() is not None

    def mark_processed(self, item_id: str, action: str):
        """Mark an item as processed for a specific action."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO processed_items (item_id, action, timestamp) VALUES (?, ?, ?)",
                (str(item_id), action, datetime.datetime.now())
            )
