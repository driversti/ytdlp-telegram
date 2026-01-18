"""Download statistics and history service using SQLite."""

import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from config import get_config

logger = logging.getLogger(__name__)


@dataclass
class DownloadRecord:
    """Record of a single download."""

    id: int
    url: str
    platform: str
    format_type: str  # 'audio' or 'video'
    quality: str
    filesize_mb: float
    title: str
    user_id: int
    timestamp: datetime

    @classmethod
    def from_row(cls, row: tuple) -> "DownloadRecord":
        return cls(
            id=row[0],
            url=row[1],
            platform=row[2],
            format_type=row[3],
            quality=row[4],
            filesize_mb=row[5],
            title=row[6],
            user_id=row[7],
            timestamp=datetime.fromisoformat(row[8]),
        )


@dataclass
class UserStats:
    """Statistics for a single user."""

    user_id: int
    total_downloads: int
    total_size_mb: float
    audio_downloads: int
    video_downloads: int
    favorite_platform: str


@dataclass
class OverallStats:
    """Overall download statistics."""

    total_downloads: int
    total_size_mb: float
    downloads_this_month: int
    size_this_month_mb: float
    platforms: dict[str, int]  # platform -> count
    users: dict[int, UserStats]


class StatsService:
    """Service for tracking download statistics."""

    def __init__(self):
        self.config = get_config()
        self.db_path = Path(self.config.download_path) / ".stats.db"
        self._init_db()

    def _init_db(self):
        """Initialize the SQLite database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS downloads (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        url TEXT NOT NULL,
                        platform TEXT NOT NULL,
                        format_type TEXT NOT NULL,
                        quality TEXT NOT NULL,
                        filesize_mb REAL NOT NULL,
                        title TEXT NOT NULL,
                        user_id INTEGER NOT NULL,
                        timestamp TEXT NOT NULL
                    )
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_downloads_timestamp
                    ON downloads(timestamp)
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_downloads_user_id
                    ON downloads(user_id)
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_downloads_platform
                    ON downloads(platform)
                """)
                conn.commit()
                logger.info(f"Stats database initialized at {self.db_path}")
        except sqlite3.Error:
            logger.exception("Failed to initialize stats database")

    def record_download(
        self,
        url: str,
        platform: str,
        format_type: str,
        quality: str,
        filesize_mb: float,
        title: str,
        user_id: int,
    ) -> Optional[int]:
        """
        Record a completed download.

        Returns:
            The record ID, or None if failed
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO downloads (url, platform, format_type, quality, filesize_mb, title, user_id, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (url, platform, format_type, quality, filesize_mb, title, user_id, datetime.utcnow().isoformat()),
                )
                conn.commit()
                return cursor.lastrowid
        except sqlite3.Error:
            logger.exception("Failed to record download")
            return None

    def get_overall_stats(self) -> OverallStats:
        """Get overall download statistics."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Total counts
                total_row = conn.execute(
                    "SELECT COUNT(*), COALESCE(SUM(filesize_mb), 0) FROM downloads"
                ).fetchone()
                total_downloads = total_row[0]
                total_size_mb = total_row[1]

                # This month
                first_of_month = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                month_row = conn.execute(
                    "SELECT COUNT(*), COALESCE(SUM(filesize_mb), 0) FROM downloads WHERE timestamp >= ?",
                    (first_of_month.isoformat(),),
                ).fetchone()
                downloads_this_month = month_row[0]
                size_this_month_mb = month_row[1]

                # Platform breakdown
                platform_rows = conn.execute(
                    "SELECT platform, COUNT(*) as cnt FROM downloads GROUP BY platform ORDER BY cnt DESC"
                ).fetchall()
                platforms = {row[0]: row[1] for row in platform_rows}

                # Per-user stats
                user_rows = conn.execute("""
                    SELECT
                        user_id,
                        COUNT(*) as total,
                        COALESCE(SUM(filesize_mb), 0) as size,
                        SUM(CASE WHEN format_type = 'audio' THEN 1 ELSE 0 END) as audio,
                        SUM(CASE WHEN format_type = 'video' THEN 1 ELSE 0 END) as video
                    FROM downloads
                    GROUP BY user_id
                """).fetchall()

                users = {}
                for row in user_rows:
                    user_id = row[0]
                    # Get favorite platform for this user
                    fav_row = conn.execute(
                        "SELECT platform FROM downloads WHERE user_id = ? GROUP BY platform ORDER BY COUNT(*) DESC LIMIT 1",
                        (user_id,),
                    ).fetchone()
                    favorite_platform = fav_row[0] if fav_row else "unknown"

                    users[user_id] = UserStats(
                        user_id=user_id,
                        total_downloads=row[1],
                        total_size_mb=row[2],
                        audio_downloads=row[3],
                        video_downloads=row[4],
                        favorite_platform=favorite_platform,
                    )

                return OverallStats(
                    total_downloads=total_downloads,
                    total_size_mb=total_size_mb,
                    downloads_this_month=downloads_this_month,
                    size_this_month_mb=size_this_month_mb,
                    platforms=platforms,
                    users=users,
                )
        except sqlite3.Error:
            logger.exception("Failed to get overall stats")
            return OverallStats(
                total_downloads=0,
                total_size_mb=0.0,
                downloads_this_month=0,
                size_this_month_mb=0.0,
                platforms={},
                users={},
            )

    def get_user_stats(self, user_id: int) -> Optional[UserStats]:
        """Get statistics for a specific user."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                row = conn.execute(
                    """
                    SELECT
                        COUNT(*) as total,
                        COALESCE(SUM(filesize_mb), 0) as size,
                        SUM(CASE WHEN format_type = 'audio' THEN 1 ELSE 0 END) as audio,
                        SUM(CASE WHEN format_type = 'video' THEN 1 ELSE 0 END) as video
                    FROM downloads
                    WHERE user_id = ?
                    """,
                    (user_id,),
                ).fetchone()

                if row[0] == 0:
                    return None

                # Get favorite platform
                fav_row = conn.execute(
                    "SELECT platform FROM downloads WHERE user_id = ? GROUP BY platform ORDER BY COUNT(*) DESC LIMIT 1",
                    (user_id,),
                ).fetchone()
                favorite_platform = fav_row[0] if fav_row else "unknown"

                return UserStats(
                    user_id=user_id,
                    total_downloads=row[0],
                    total_size_mb=row[1],
                    audio_downloads=row[2],
                    video_downloads=row[3],
                    favorite_platform=favorite_platform,
                )
        except sqlite3.Error:
            logger.exception("Failed to get user stats")
            return None

    def get_recent_downloads(self, limit: int = 10, user_id: Optional[int] = None) -> list[DownloadRecord]:
        """Get recent downloads, optionally filtered by user."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                if user_id:
                    rows = conn.execute(
                        "SELECT * FROM downloads WHERE user_id = ? ORDER BY timestamp DESC LIMIT ?",
                        (user_id, limit),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT * FROM downloads ORDER BY timestamp DESC LIMIT ?",
                        (limit,),
                    ).fetchall()

                return [DownloadRecord.from_row(row) for row in rows]
        except sqlite3.Error:
            logger.exception("Failed to get recent downloads")
            return []

    def get_storage_by_platform(self) -> dict[str, float]:
        """Get total storage used per platform in MB."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                rows = conn.execute(
                    "SELECT platform, COALESCE(SUM(filesize_mb), 0) FROM downloads GROUP BY platform"
                ).fetchall()
                return {row[0]: row[1] for row in rows}
        except sqlite3.Error:
            logger.exception("Failed to get storage by platform")
            return {}


# Global service instance
stats_service = StatsService()
