"""User service for file server - thin wrapper to access users database."""

import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from config import config

logger = logging.getLogger(__name__)


@dataclass
class User:
    """Record of a user."""

    id: int
    telegram_id: int
    username: Optional[str]
    first_name: Optional[str]
    last_name: Optional[str]
    status: str  # pending, approved, denied
    source: str  # request, admin_added
    created_at: datetime
    updated_at: datetime
    approved_at: Optional[datetime]
    approved_by: Optional[int]

    @classmethod
    def from_row(cls, row: tuple) -> "User":
        return cls(
            id=row[0],
            telegram_id=row[1],
            username=row[2],
            first_name=row[3],
            last_name=row[4],
            status=row[5],
            source=row[6],
            created_at=datetime.fromisoformat(row[7]),
            updated_at=datetime.fromisoformat(row[8]),
            approved_at=datetime.fromisoformat(row[9]) if row[9] else None,
            approved_by=row[10],
        )

    @property
    def display_name(self) -> str:
        """Get a display name for the user."""
        if self.first_name:
            if self.last_name:
                return f"{self.first_name} {self.last_name}"
            return self.first_name
        if self.username:
            return f"@{self.username}"
        return str(self.telegram_id)


class UserService:
    """Service for accessing users from the database."""

    def __init__(self):
        self.db_path = Path(config.download_path) / ".users.db"

    def _ensure_db_exists(self):
        """Ensure the database and table exist."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        telegram_id INTEGER NOT NULL UNIQUE,
                        username TEXT,
                        first_name TEXT,
                        last_name TEXT,
                        status TEXT NOT NULL DEFAULT 'pending',
                        source TEXT NOT NULL DEFAULT 'request',
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        approved_at TEXT,
                        approved_by INTEGER
                    )
                """)
                conn.commit()
        except sqlite3.Error:
            logger.exception("Failed to ensure users database exists")

    def get_pending_requests(self) -> list[User]:
        """Get all pending access requests."""
        self._ensure_db_exists()
        try:
            with sqlite3.connect(self.db_path) as conn:
                rows = conn.execute(
                    "SELECT * FROM users WHERE status = 'pending' ORDER BY created_at DESC"
                ).fetchall()
                return [User.from_row(row) for row in rows]
        except sqlite3.Error:
            logger.exception("Failed to get pending requests")
            return []

    def get_approved_users(self) -> list[User]:
        """Get all approved users from the database."""
        self._ensure_db_exists()
        try:
            with sqlite3.connect(self.db_path) as conn:
                rows = conn.execute(
                    "SELECT * FROM users WHERE status = 'approved' ORDER BY approved_at DESC"
                ).fetchall()
                return [User.from_row(row) for row in rows]
        except sqlite3.Error:
            logger.exception("Failed to get approved users")
            return []

    def get_denied_users(self) -> list[User]:
        """Get all denied users from the database."""
        self._ensure_db_exists()
        try:
            with sqlite3.connect(self.db_path) as conn:
                rows = conn.execute(
                    "SELECT * FROM users WHERE status = 'denied' ORDER BY updated_at DESC"
                ).fetchall()
                return [User.from_row(row) for row in rows]
        except sqlite3.Error:
            logger.exception("Failed to get denied users")
            return []

    def get_all_users(self) -> list[User]:
        """Get all users from the database."""
        self._ensure_db_exists()
        try:
            with sqlite3.connect(self.db_path) as conn:
                rows = conn.execute(
                    "SELECT * FROM users ORDER BY created_at DESC"
                ).fetchall()
                return [User.from_row(row) for row in rows]
        except sqlite3.Error:
            logger.exception("Failed to get all users")
            return []

    def get_user(self, telegram_id: int) -> Optional[User]:
        """Get a user by their Telegram ID."""
        self._ensure_db_exists()
        try:
            with sqlite3.connect(self.db_path) as conn:
                row = conn.execute(
                    "SELECT * FROM users WHERE telegram_id = ?",
                    (telegram_id,),
                ).fetchone()
                return User.from_row(row) if row else None
        except sqlite3.Error:
            logger.exception("Failed to get user")
            return None

    def add_user(self, telegram_id: int) -> bool:
        """Add a user directly (approved status)."""
        self._ensure_db_exists()
        now = datetime.utcnow().isoformat()
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO users (telegram_id, status, source, created_at, updated_at, approved_at)
                    VALUES (?, 'approved', 'admin_added', ?, ?, ?)
                    """,
                    (telegram_id, now, now, now),
                )
                conn.commit()
                logger.info(f"Added user {telegram_id} via web admin")
                return True
        except sqlite3.IntegrityError:
            logger.warning(f"User {telegram_id} already exists")
            return False
        except sqlite3.Error:
            logger.exception("Failed to add user")
            return False

    def approve_user(self, telegram_id: int) -> bool:
        """Approve a user's access request."""
        self._ensure_db_exists()
        now = datetime.utcnow().isoformat()
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    """
                    UPDATE users
                    SET status = 'approved', updated_at = ?, approved_at = ?
                    WHERE telegram_id = ?
                    """,
                    (now, now, telegram_id),
                )
                conn.commit()
                if cursor.rowcount > 0:
                    logger.info(f"Approved user {telegram_id} via web admin")
                    return True
                return False
        except sqlite3.Error:
            logger.exception("Failed to approve user")
            return False

    def deny_user(self, telegram_id: int) -> bool:
        """Deny a user's access request."""
        self._ensure_db_exists()
        now = datetime.utcnow().isoformat()
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    """
                    UPDATE users
                    SET status = 'denied', updated_at = ?
                    WHERE telegram_id = ?
                    """,
                    (now, telegram_id),
                )
                conn.commit()
                if cursor.rowcount > 0:
                    logger.info(f"Denied user {telegram_id} via web admin")
                    return True
                return False
        except sqlite3.Error:
            logger.exception("Failed to deny user")
            return False

    def remove_user(self, telegram_id: int) -> bool:
        """Remove a user from the database."""
        self._ensure_db_exists()
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "DELETE FROM users WHERE telegram_id = ?",
                    (telegram_id,),
                )
                conn.commit()
                if cursor.rowcount > 0:
                    logger.info(f"Removed user {telegram_id} via web admin")
                    return True
                return False
        except sqlite3.Error:
            logger.exception("Failed to remove user")
            return False


# Global service instance
user_service = UserService()
