import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from config import config
from services.token_service import token_service

logger = logging.getLogger(__name__)


@dataclass
class FileInfo:
    """Information about a file."""

    filepath: str
    filename: str
    size_bytes: int
    size_mb: float
    platform: str
    created_at: datetime
    token: Optional[str] = None


class FileService:
    """Service for managing downloaded files."""

    def __init__(self):
        self.download_path = Path(config.download_path)

    def _get_platform_from_path(self, filepath: Path) -> str:
        """Extract platform name from filepath."""
        relative = filepath.relative_to(self.download_path)
        parts = relative.parts
        if len(parts) > 1:
            return parts[0]
        return "unknown"

    def _is_valid_media_file(self, filepath: Path) -> bool:
        """Check if file is a valid media file."""
        valid_extensions = {".mp4", ".webm", ".mkv", ".mp3", ".m4a", ".opus", ".wav"}
        return filepath.suffix.lower() in valid_extensions

    def _is_safe_path(self, filepath: str) -> bool:
        """
        Validate that the path is within the download directory.
        Prevents path traversal attacks.
        """
        try:
            resolved = Path(filepath).resolve()
            download_resolved = self.download_path.resolve()
            return resolved.is_relative_to(download_resolved)
        except (ValueError, RuntimeError):
            return False

    def list_files(self) -> list[FileInfo]:
        """
        List all downloaded media files with their info.

        Returns:
            List of FileInfo objects
        """
        files = []
        tokens = token_service.get_all_tokens()
        token_by_path = {info["filepath"]: token for token, info in tokens.items()}

        for media_file in self.download_path.rglob("*"):
            if not media_file.is_file():
                continue
            if not self._is_valid_media_file(media_file):
                continue
            if media_file.name.startswith("."):
                continue

            filepath_str = str(media_file)
            stat = media_file.stat()

            files.append(
                FileInfo(
                    filepath=filepath_str,
                    filename=media_file.name,
                    size_bytes=stat.st_size,
                    size_mb=stat.st_size / (1024 * 1024),
                    platform=self._get_platform_from_path(media_file),
                    created_at=datetime.fromtimestamp(stat.st_mtime),
                    token=token_by_path.get(filepath_str),
                )
            )

        files.sort(key=lambda f: f.created_at, reverse=True)
        return files

    def list_files_by_platform(self) -> dict[str, list[FileInfo]]:
        """
        List all files grouped by platform.

        Returns:
            Dict mapping platform name to list of FileInfo
        """
        files = self.list_files()
        grouped: dict[str, list[FileInfo]] = {}

        for file_info in files:
            platform = file_info.platform
            if platform not in grouped:
                grouped[platform] = []
            grouped[platform].append(file_info)

        return grouped

    def get_file_by_token(self, token: str) -> Optional[FileInfo]:
        """
        Get file info by token.

        Args:
            token: The download token

        Returns:
            FileInfo if found and valid, None otherwise
        """
        filepath = token_service.get_filepath(token)
        if not filepath:
            return None

        if not self._is_safe_path(filepath):
            logger.warning(f"Unsafe path detected for token {token}: {filepath}")
            return None

        path = Path(filepath)
        if not path.exists():
            return None

        token_info = token_service.get_token_info(token)
        stat = path.stat()

        return FileInfo(
            filepath=filepath,
            filename=path.name,
            size_bytes=stat.st_size,
            size_mb=stat.st_size / (1024 * 1024),
            platform=self._get_platform_from_path(path),
            created_at=datetime.fromtimestamp(stat.st_mtime),
            token=token,
        )

    def delete_file_by_token(self, token: str) -> bool:
        """
        Delete a file by its token.

        Args:
            token: The download token

        Returns:
            True if deleted successfully, False otherwise
        """
        filepath = token_service.get_filepath(token)
        if not filepath:
            logger.warning(f"Token not found: {token}")
            return False

        if not self._is_safe_path(filepath):
            logger.warning(f"Unsafe path for token {token}: {filepath}")
            return False

        path = Path(filepath)
        try:
            if path.exists():
                path.unlink()
                logger.info(f"Deleted file: {filepath}")

            token_service.delete_token(token)
            return True
        except OSError as e:
            logger.error(f"Failed to delete file {filepath}: {e}")
            return False

    def get_or_create_token(self, filepath: str) -> Optional[str]:
        """
        Get existing token for filepath or create a new one.

        Args:
            filepath: Absolute path to the file

        Returns:
            Token UUID or None if invalid path
        """
        if not self._is_safe_path(filepath):
            logger.warning(f"Unsafe path rejected: {filepath}")
            return None

        path = Path(filepath)
        if not path.exists():
            logger.warning(f"File does not exist: {filepath}")
            return None

        existing = token_service.find_token_by_filepath(filepath)
        if existing:
            return existing

        size_bytes = path.stat().st_size
        return token_service.generate_token(filepath, size_bytes)


file_service = FileService()
