"""User management service using SQLite."""

import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from config import get_config

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
    """Service for managing users."""

    def __init__(self):
        self.config = get_config()
        self.db_path = Path(self.config.download_path) / ".users.db"
        self._init_db()

    def _init_db(self):
        """Initialize the SQLite database."""
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
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_users_telegram_id
                    ON users(telegram_id)
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_users_status
                    ON users(status)
                """)
                conn.commit()
                logger.info(f"Users database initialized at {self.db_path}")
        except sqlite3.Error:
            logger.exception("Failed to initialize users database")

    def is_user_allowed(self, telegram_id: int) -> bool:
        """
        Check if a user is allowed to use the bot.

        First checks env-based allowed_user_ids, then checks DB for approved users.
        """
        # First check env-based whitelist (always takes priority)
        if telegram_id in self.config.allowed_user_ids:
            return True

        # Then check DB for approved users
        try:
            with sqlite3.connect(self.db_path) as conn:
                row = conn.execute(
                    "SELECT status FROM users WHERE telegram_id = ?",
                    (telegram_id,),
                ).fetchone()
                return row is not None and row[0] == "approved"
        except sqlite3.Error:
            logger.exception("Failed to check user status")
            return False

    def get_user(self, telegram_id: int) -> Optional[User]:
        """Get a user by their Telegram ID."""
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

    def get_user_status(self, telegram_id: int) -> Optional[str]:
        """Get the status of a user (pending, approved, denied)."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                row = conn.execute(
                    "SELECT status FROM users WHERE telegram_id = ?",
                    (telegram_id,),
                ).fetchone()
                return row[0] if row else None
        except sqlite3.Error:
            logger.exception("Failed to get user status")
            return None

    def create_access_request(
        self,
        telegram_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
    ) -> bool:
        """
        Create an access request for a user.

        Returns True if request was created, False if user already exists.
        """
        now = datetime.utcnow().isoformat()
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO users (telegram_id, username, first_name, last_name, status, source, created_at, updated_at)
                    VALUES (?, ?, ?, ?, 'pending', 'request', ?, ?)
                    """,
                    (telegram_id, username, first_name, last_name, now, now),
                )
                conn.commit()
                logger.info(f"Created access request for user {telegram_id}")
                return True
        except sqlite3.IntegrityError:
            # User already exists
            logger.warning(f"Access request already exists for user {telegram_id}")
            return False
        except sqlite3.Error:
            logger.exception("Failed to create access request")
            return False

    def approve_user(self, telegram_id: int, approved_by: int) -> bool:
        """Approve a user's access request."""
        now = datetime.utcnow().isoformat()
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    """
                    UPDATE users
                    SET status = 'approved', updated_at = ?, approved_at = ?, approved_by = ?
                    WHERE telegram_id = ?
                    """,
                    (now, now, approved_by, telegram_id),
                )
                conn.commit()
                if cursor.rowcount > 0:
                    logger.info(f"Approved user {telegram_id} by admin {approved_by}")
                    return True
                return False
        except sqlite3.Error:
            logger.exception("Failed to approve user")
            return False

    def deny_user(self, telegram_id: int, denied_by: int) -> bool:
        """Deny a user's access request."""
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
                    logger.info(f"Denied user {telegram_id} by admin {denied_by}")
                    return True
                return False
        except sqlite3.Error:
            logger.exception("Failed to deny user")
            return False

    def add_user(
        self,
        telegram_id: int,
        added_by: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
    ) -> bool:
        """Add a user directly (by admin)."""
        now = datetime.utcnow().isoformat()
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO users (telegram_id, username, first_name, last_name, status, source, created_at, updated_at, approved_at, approved_by)
                    VALUES (?, ?, ?, ?, 'approved', 'admin_added', ?, ?, ?, ?)
                    """,
                    (telegram_id, username, first_name, last_name, now, now, now, added_by),
                )
                conn.commit()
                logger.info(f"Added user {telegram_id} by admin {added_by}")
                return True
        except sqlite3.IntegrityError:
            # User already exists - update status to approved
            try:
                cursor = conn.execute(
                    """
                    UPDATE users
                    SET status = 'approved', source = 'admin_added', updated_at = ?, approved_at = ?, approved_by = ?
                    WHERE telegram_id = ?
                    """,
                    (now, now, added_by, telegram_id),
                )
                conn.commit()
                if cursor.rowcount > 0:
                    logger.info(f"Updated existing user {telegram_id} to approved by admin {added_by}")
                    return True
                return False
            except sqlite3.Error:
                logger.exception("Failed to update existing user")
                return False
        except sqlite3.Error:
            logger.exception("Failed to add user")
            return False

    def remove_user(self, telegram_id: int) -> bool:
        """Remove a user from the database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "DELETE FROM users WHERE telegram_id = ?",
                    (telegram_id,),
                )
                conn.commit()
                if cursor.rowcount > 0:
                    logger.info(f"Removed user {telegram_id}")
                    return True
                return False
        except sqlite3.Error:
            logger.exception("Failed to remove user")
            return False

    def get_pending_requests(self) -> list[User]:
        """Get all pending access requests."""
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
        try:
            with sqlite3.connect(self.db_path) as conn:
                rows = conn.execute(
                    "SELECT * FROM users WHERE status = 'approved' ORDER BY approved_at DESC"
                ).fetchall()
                return [User.from_row(row) for row in rows]
        except sqlite3.Error:
            logger.exception("Failed to get approved users")
            return []

    def get_all_users(self) -> list[User]:
        """Get all users from the database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                rows = conn.execute(
                    "SELECT * FROM users ORDER BY created_at DESC"
                ).fetchall()
                return [User.from_row(row) for row in rows]
        except sqlite3.Error:
            logger.exception("Failed to get all users")
            return []


# Global service instance
user_service = UserService()
