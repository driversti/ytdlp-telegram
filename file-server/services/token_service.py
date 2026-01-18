import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Optional

from config import config

logger = logging.getLogger(__name__)

TOKENS_FILE = Path(config.download_path) / ".tokens.json"


class TokenService:
    """Service for managing file download tokens."""

    def __init__(self):
        self._lock = Lock()
        self._ensure_tokens_file()

    def _ensure_tokens_file(self) -> None:
        """Ensure the tokens file exists."""
        if not TOKENS_FILE.exists():
            TOKENS_FILE.write_text("{}")

    def _load_tokens(self) -> dict:
        """Load tokens from file."""
        try:
            return json.loads(TOKENS_FILE.read_text())
        except (json.JSONDecodeError, FileNotFoundError):
            return {}

    def _save_tokens(self, tokens: dict) -> None:
        """Save tokens to file."""
        TOKENS_FILE.write_text(json.dumps(tokens, indent=2))

    def generate_token(self, filepath: str, size_bytes: int) -> str:
        """
        Generate a new token for a file.

        Args:
            filepath: Absolute path to the file
            size_bytes: File size in bytes

        Returns:
            The generated token UUID
        """
        with self._lock:
            tokens = self._load_tokens()
            token = str(uuid.uuid4())
            tokens[token] = {
                "filepath": filepath,
                "created_at": datetime.utcnow().isoformat() + "Z",
                "size_bytes": size_bytes,
            }
            self._save_tokens(tokens)
            logger.info(f"Generated token {token} for {filepath}")
            return token

    def get_filepath(self, token: str) -> Optional[str]:
        """
        Get the filepath for a token.

        Args:
            token: The token UUID

        Returns:
            The filepath if token exists, None otherwise
        """
        tokens = self._load_tokens()
        entry = tokens.get(token)
        if entry:
            return entry.get("filepath")
        return None

    def get_token_info(self, token: str) -> Optional[dict]:
        """
        Get full token information.

        Args:
            token: The token UUID

        Returns:
            Token info dict if exists, None otherwise
        """
        tokens = self._load_tokens()
        return tokens.get(token)

    def delete_token(self, token: str) -> bool:
        """
        Delete a token.

        Args:
            token: The token UUID

        Returns:
            True if token was deleted, False if not found
        """
        with self._lock:
            tokens = self._load_tokens()
            if token in tokens:
                del tokens[token]
                self._save_tokens(tokens)
                logger.info(f"Deleted token {token}")
                return True
            return False

    def get_all_tokens(self) -> dict:
        """Get all tokens with their info."""
        return self._load_tokens()

    def find_token_by_filepath(self, filepath: str) -> Optional[str]:
        """
        Find a token by filepath.

        Args:
            filepath: The file path to search for

        Returns:
            Token UUID if found, None otherwise
        """
        tokens = self._load_tokens()
        for token, info in tokens.items():
            if info.get("filepath") == filepath:
                return token
        return None

    def cleanup_orphaned_tokens(self) -> int:
        """
        Remove tokens for files that no longer exist.

        Returns:
            Number of tokens removed
        """
        with self._lock:
            tokens = self._load_tokens()
            to_remove = []
            for token, info in tokens.items():
                filepath = info.get("filepath")
                if filepath and not Path(filepath).exists():
                    to_remove.append(token)

            for token in to_remove:
                del tokens[token]
                logger.info(f"Cleaned up orphaned token {token}")

            if to_remove:
                self._save_tokens(tokens)

            return len(to_remove)


token_service = TokenService()
