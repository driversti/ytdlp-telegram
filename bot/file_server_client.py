import logging
from dataclasses import dataclass
from typing import Optional

import httpx

from config import get_config

logger = logging.getLogger(__name__)


@dataclass
class DownloadLink:
    """Result of generating a download link."""

    token: str
    url: str


class FileServerClient:
    """HTTP client for communicating with the file server."""

    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=10.0)
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    def _get_internal_url(self) -> str:
        """Get the internal file server URL."""
        config = get_config()
        return config.file_server_url

    async def generate_download_link(self, filepath: str) -> Optional[DownloadLink]:
        """
        Generate a download link for a file.

        Args:
            filepath: Absolute path to the file

        Returns:
            DownloadLink with token and public URL, or None on failure
        """
        try:
            client = await self._get_client()
            response = await client.post(
                f"{self._get_internal_url()}/api/tokens",
                json={"filepath": filepath},
            )

            if response.status_code == 200:
                data = response.json()
                return DownloadLink(
                    token=data["token"],
                    url=data["url"],
                )
            else:
                logger.error(
                    f"Failed to generate token: {response.status_code} - {response.text}"
                )
                return None

        except httpx.RequestError as e:
            logger.error(f"Request error generating token: {e}")
            return None

    async def delete_file(self, token: str) -> bool:
        """
        Delete a file by its token.

        Args:
            token: The file token

        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            client = await self._get_client()
            response = await client.delete(
                f"{self._get_internal_url()}/api/files/{token}"
            )

            if response.status_code == 200:
                return True
            else:
                logger.error(
                    f"Failed to delete file: {response.status_code} - {response.text}"
                )
                return False

        except httpx.RequestError as e:
            logger.error(f"Request error deleting file: {e}")
            return False


file_server_client = FileServerClient()
