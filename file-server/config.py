import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    """File server configuration loaded from environment variables."""

    download_path: str
    port: int
    public_url: str

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables."""
        return cls(
            download_path=os.getenv("DOWNLOAD_PATH", "/downloads"),
            port=int(os.getenv("FILE_SERVER_PORT", "8080")),
            public_url=os.getenv("FILE_SERVER_PUBLIC_URL", "http://localhost:8080"),
        )


config = Config.from_env()
