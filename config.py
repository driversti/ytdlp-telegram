import os
from dataclasses import dataclass
from dotenv import load_dotenv

__version__ = "0.1.11"

load_dotenv()


@dataclass(frozen=True)
class Config:
    """Application configuration loaded from environment variables."""

    telegram_bot_token: str
    allowed_user_ids: set[int]
    admin_user_id: int | None
    ollama_url: str
    ollama_model: str
    download_path: str
    max_file_size_mb: int
    file_server_url: str
    file_server_public_url: str
    download_timeout: int
    format_detection_timeout: int
    llm_timeout: int

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

        admin_user_id_str = os.getenv("ADMIN_USER_ID", "")
        admin_user_id = int(admin_user_id_str) if admin_user_id_str.strip() else None

        return cls(
            telegram_bot_token=token,
            allowed_user_ids=allowed_ids,
            admin_user_id=admin_user_id,
            ollama_url=os.getenv("OLLAMA_URL", "http://localhost:11434"),
            ollama_model=os.getenv("OLLAMA_MODEL", "llama3.2:3b"),
            download_path=os.getenv("DOWNLOAD_PATH", "/downloads"),
            max_file_size_mb=int(os.getenv("MAX_FILE_SIZE_MB", "50")),
            file_server_url=os.getenv("FILE_SERVER_URL", "http://localhost:8080"),
            file_server_public_url=os.getenv("FILE_SERVER_PUBLIC_URL", "http://localhost:8080"),
            download_timeout=int(os.getenv("DOWNLOAD_TIMEOUT", "1800")),  # 30 minutes
            format_detection_timeout=int(os.getenv("FORMAT_DETECTION_TIMEOUT", "30")),
            llm_timeout=int(os.getenv("LLM_TIMEOUT", "30")),
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
