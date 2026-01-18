import json
import logging
import re
import time
from dataclasses import dataclass
from typing import Optional

import httpx

from config import get_config
from bot.downloader import extract_urls

logger = logging.getLogger(__name__)

# Cache TTL for LLM availability check (in seconds)
LLM_AVAILABILITY_CACHE_TTL = 300  # 5 minutes


@dataclass
class ParsedIntent:
    """Parsed user intent from natural language."""

    urls: list[str]
    wants_audio: bool
    wants_video: bool
    is_download_request: bool
    suggested_filename: Optional[str] = None
    raw_message: str = ""


class LLMService:
    """Service for interacting with Ollama for natural language processing."""

    def __init__(self):
        self.config = get_config()
        self._available: Optional[bool] = None
        self._available_checked_at: float = 0.0

    def _is_cache_valid(self) -> bool:
        """Check if the cached availability status is still valid."""
        if self._available is None:
            return False
        return (time.monotonic() - self._available_checked_at) < LLM_AVAILABILITY_CACHE_TTL

    def invalidate_cache(self) -> None:
        """Invalidate the availability cache, forcing a recheck on next call."""
        self._available = None
        self._available_checked_at = 0.0

    async def is_available(self) -> bool:
        """Check if Ollama is available (with TTL caching)."""
        if self._is_cache_valid():
            return self._available

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.config.ollama_url}/api/tags")
                self._available = response.status_code == 200
        except (httpx.RequestError, httpx.TimeoutException) as e:
            logger.warning(f"Ollama not available: {e}")
            self._available = False

        self._available_checked_at = time.monotonic()
        return self._available

    async def parse_intent(self, message: str) -> ParsedIntent:
        """
        Parse user message to extract download intent.

        Uses LLM to understand natural language, with fallback to simple heuristics.
        """
        # Extract URLs first
        urls = extract_urls(message)

        # Quick check: if no URLs and not a download-related keyword, not a download request
        download_keywords = [
            "download", "grab", "get", "save", "fetch", "dl",
            "audio", "video", "music", "song", "mp3", "mp4"
        ]
        message_lower = message.lower()
        has_download_keyword = any(kw in message_lower for kw in download_keywords)

        if not urls and not has_download_keyword:
            return ParsedIntent(
                urls=[],
                wants_audio=False,
                wants_video=False,
                is_download_request=False,
                raw_message=message,
            )

        # Try LLM parsing if available
        if await self.is_available():
            try:
                llm_result = await self._parse_with_llm(message)
                if llm_result:
                    # Merge with extracted URLs (LLM might miss some)
                    all_urls = list(set(urls + llm_result.urls))
                    return ParsedIntent(
                        urls=all_urls,
                        wants_audio=llm_result.wants_audio,
                        wants_video=llm_result.wants_video,
                        is_download_request=llm_result.is_download_request or bool(all_urls),
                        suggested_filename=llm_result.suggested_filename,
                        raw_message=message,
                    )
            except Exception as e:
                logger.warning(f"LLM parsing failed, using heuristics: {e}")

        # Fallback: heuristic parsing
        return self._parse_heuristic(message, urls)

    async def _parse_with_llm(self, message: str) -> Optional[ParsedIntent]:
        """Parse message using Ollama LLM."""
        prompt = f"""Analyze this message and extract download intent. Respond with JSON only.

Message: "{message}"

Extract:
1. urls: Array of URLs found in the message
2. wants_audio: true if user wants audio/music/mp3 format
3. wants_video: true if user wants video format
4. is_download_request: true if user wants to download something
5. suggested_filename: A clean filename suggestion if mentioned

Respond with valid JSON only, no explanation:
{{"urls": [], "wants_audio": false, "wants_video": false, "is_download_request": false, "suggested_filename": null}}"""

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.config.ollama_url}/api/generate",
                    json={
                        "model": self.config.ollama_model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "temperature": 0.1,
                            "num_predict": 200,
                        }
                    }
                )

                if response.status_code != 200:
                    return None

                result = response.json()
                response_text = result.get("response", "")

                # Extract JSON from response
                json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group())
                    return ParsedIntent(
                        urls=data.get("urls", []),
                        wants_audio=data.get("wants_audio", False),
                        wants_video=data.get("wants_video", False),
                        is_download_request=data.get("is_download_request", False),
                        suggested_filename=data.get("suggested_filename"),
                        raw_message=message,
                    )

        except json.JSONDecodeError:
            logger.warning("Failed to parse LLM JSON response")
        except Exception as e:
            logger.error(f"LLM request failed: {e}")

        return None

    def _parse_heuristic(self, message: str, urls: list[str]) -> ParsedIntent:
        """Parse message using simple heuristics."""
        message_lower = message.lower()

        # Audio indicators
        audio_keywords = ["audio", "music", "song", "mp3", "sound", "soundtrack"]
        wants_audio = any(kw in message_lower for kw in audio_keywords)

        # Video indicators
        video_keywords = ["video", "mp4", "movie", "clip", "watch"]
        wants_video = any(kw in message_lower for kw in video_keywords)

        # Download intent
        download_keywords = ["download", "grab", "get", "save", "fetch", "dl"]
        is_download = any(kw in message_lower for kw in download_keywords) or bool(urls)

        return ParsedIntent(
            urls=urls,
            wants_audio=wants_audio,
            wants_video=wants_video,
            is_download_request=is_download,
            raw_message=message,
        )

    async def suggest_filename(self, title: str, uploader: str = "") -> str:
        """Use LLM to suggest a clean filename."""
        if not await self.is_available():
            return title

        prompt = f"""Suggest a clean, descriptive filename for this media.
Title: "{title}"
Uploader: "{uploader}"

Rules:
- Remove special characters that are not filesystem-safe
- Keep it concise but descriptive
- Remove redundant information (like channel name if already in title)
- Keep the essence of the title

Respond with just the suggested filename, no quotes, no extension:"""

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    f"{self.config.ollama_url}/api/generate",
                    json={
                        "model": self.config.ollama_model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "temperature": 0.3,
                            "num_predict": 100,
                        }
                    }
                )

                if response.status_code == 200:
                    result = response.json()
                    suggested = result.get("response", "").strip()
                    if suggested and len(suggested) < 200:
                        return suggested

        except Exception as e:
            logger.warning(f"Filename suggestion failed: {e}")

        return title


# Global service instance
llm_service = LLMService()
