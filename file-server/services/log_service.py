"""Service for reading and parsing bot log files."""

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from config import config

# Regex pattern to parse log lines
# Format: 2024-01-15 10:30:45,123 - module.name - INFO - Message
LOG_PATTERN = re.compile(
    r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}) - ([\w.]+) - (\w+) - (.*)$"
)


@dataclass
class LogEntry:
    """Represents a single log entry."""

    timestamp: str
    logger: str
    level: str
    message: str

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "timestamp": self.timestamp,
            "logger": self.logger,
            "level": self.level,
            "message": self.message,
        }


@dataclass
class LogStats:
    """Statistics about the log file."""

    file_size_bytes: int
    file_size_mb: float
    last_modified: Optional[datetime]
    exists: bool

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "file_size_bytes": self.file_size_bytes,
            "file_size_mb": round(self.file_size_mb, 2),
            "last_modified": self.last_modified.isoformat() if self.last_modified else None,
            "exists": self.exists,
        }


class LogService:
    """Service for reading and parsing log files."""

    def __init__(self, log_path: Optional[Path] = None):
        """Initialize the log service."""
        self.log_path = log_path or Path(config.download_path) / "bot.log"

    def get_log_stats(self) -> LogStats:
        """Get statistics about the log file."""
        if not self.log_path.exists():
            return LogStats(
                file_size_bytes=0,
                file_size_mb=0.0,
                last_modified=None,
                exists=False,
            )

        stat = self.log_path.stat()
        return LogStats(
            file_size_bytes=stat.st_size,
            file_size_mb=stat.st_size / (1024 * 1024),
            last_modified=datetime.fromtimestamp(stat.st_mtime),
            exists=True,
        )

    def parse_log_line(self, line: str) -> Optional[LogEntry]:
        """Parse a single log line into a LogEntry."""
        line = line.strip()
        if not line:
            return None

        match = LOG_PATTERN.match(line)
        if match:
            return LogEntry(
                timestamp=match.group(1),
                logger=match.group(2),
                level=match.group(3),
                message=match.group(4),
            )

        # Return unparsed lines as INFO level with raw content
        return LogEntry(
            timestamp="",
            logger="",
            level="INFO",
            message=line,
        )

    def read_logs(
        self,
        lines: int = 200,
        level_filter: Optional[str] = None,
        search: Optional[str] = None,
    ) -> list[LogEntry]:
        """
        Read recent log entries with optional filtering.

        Args:
            lines: Maximum number of lines to return
            level_filter: Filter by log level (INFO, WARNING, ERROR, DEBUG)
            search: Search term to filter messages

        Returns:
            List of LogEntry objects, most recent last
        """
        if not self.log_path.exists():
            return []

        # Read the file and get last N lines
        try:
            with open(self.log_path, "r", encoding="utf-8", errors="replace") as f:
                all_lines = f.readlines()
        except (IOError, OSError):
            return []

        # Parse all lines first
        entries: list[LogEntry] = []
        for line in all_lines:
            entry = self.parse_log_line(line)
            if entry:
                entries.append(entry)

        # Apply level filter
        if level_filter and level_filter.upper() != "ALL":
            level_upper = level_filter.upper()
            entries = [e for e in entries if e.level.upper() == level_upper]

        # Apply search filter (case-insensitive)
        if search:
            search_lower = search.lower()
            entries = [
                e
                for e in entries
                if search_lower in e.message.lower()
                or search_lower in e.logger.lower()
            ]

        # Return last N entries
        return entries[-lines:]


# Global instance
log_service = LogService()
