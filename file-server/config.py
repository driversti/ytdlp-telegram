import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    """File server configuration loaded from environment variables."""

    download_path: str
    port: int
    public_url: str
    admin_password: str | None
    telegram_bot_token: str | None

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables."""
        admin_password = os.getenv("ADMIN_PASSWORD", "").strip() or None
        telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip() or None
        return cls(
            download_path=os.getenv("DOWNLOAD_PATH", "/downloads"),
            port=int(os.getenv("FILE_SERVER_PORT", "8080")),
            public_url=os.getenv("FILE_SERVER_PUBLIC_URL", "http://localhost:8080"),
            admin_password=admin_password,
            telegram_bot_token=telegram_bot_token,
        )


config = Config.from_env()
