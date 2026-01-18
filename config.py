import os
from dataclasses import dataclass
from dotenv import load_dotenv

__version__ = "0.1.2"

load_dotenv()


@dataclass(frozen=True)
class Config:
    """Application configuration loaded from environment variables."""

    telegram_bot_token: str
    allowed_user_ids: set[int]
    ollama_url: str
    ollama_model: str
    download_path: str
    max_file_size_mb: int

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables."""
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not token:
            raise ValueError("TELEGRAM_BOT_TOKEN environment variable is required")

        allowed_ids_str = os.getenv("ALLOWED_USER_IDS", "")
        allowed_ids = set()
        if allowed_ids_str:
            allowed_ids = {int(uid.strip()) for uid in allowed_ids_str.split(",") if uid.strip()}

        return cls(
            telegram_bot_token=token,
            allowed_user_ids=allowed_ids,
            ollama_url=os.getenv("OLLAMA_URL", "http://localhost:11434"),
            ollama_model=os.getenv("OLLAMA_MODEL", "llama3.2:3b"),
            download_path=os.getenv("DOWNLOAD_PATH", "/downloads"),
            max_file_size_mb=int(os.getenv("MAX_FILE_SIZE_MB", "50")),
        )

    @property
    def max_file_size_bytes(self) -> int:
        """Return max file size in bytes."""
        return self.max_file_size_mb * 1024 * 1024


# Global config instance
config = Config.from_env() if os.getenv("TELEGRAM_BOT_TOKEN") else None


def get_config() -> Config:
    """Get the global config instance, loading it if necessary."""
    global config
    if config is None:
        config = Config.from_env()
    return config
