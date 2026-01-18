import asyncio
import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable, Optional
from collections import deque

import yt_dlp

from bot.storage import get_platform_directory, sanitize_filename, get_file_size_mb
from config import get_config

logger = logging.getLogger(__name__)


class DownloadFormat(Enum):
    AUDIO = "audio"
    VIDEO = "video"


class DownloadQuality(Enum):
    AUDIO_128 = "audio_128"
    AUDIO_192 = "audio_192"
    AUDIO_320 = "audio_320"
    AUDIO_BEST = "audio_best"
    VIDEO_480 = "video_480"
    VIDEO_720 = "video_720"
    VIDEO_1080 = "video_1080"
    VIDEO_BEST = "video_best"


@dataclass
class DownloadTask:
    """Represents a single download task."""

    url: str
    quality: DownloadQuality
    chat_id: int
    message_id: int
    progress_callback: Optional[Callable[[float, str], asyncio.Future]] = None
    original_url: str = ""  # Full URL if truncated

    def __post_init__(self):
        if not self.original_url:
            self.original_url = self.url


@dataclass
class DownloadResult:
    """Result of a download operation."""

    success: bool
    filepath: Optional[Path] = None
    title: str = ""
    duration: int = 0
    filesize_mb: float = 0.0
    error_message: str = ""
    is_playlist: bool = False
    playlist_count: int = 0


@dataclass
class MediaInfo:
    """Information about media from URL."""

    title: str
    duration: int
    is_playlist: bool
    playlist_count: int
    thumbnail: Optional[str] = None
    uploader: str = ""
    url: str = ""


class DownloadQueue:
    """Sequential download queue with position tracking."""

    def __init__(self):
        self._queue: deque[DownloadTask] = deque()
        self._current_task: Optional[DownloadTask] = None
        self._lock = asyncio.Lock()
        self._processing = False
        self._processor_task: Optional[asyncio.Task] = None

    async def add(self, task: DownloadTask) -> int:
        """
        Add a task to the queue.

        Returns:
            Position in queue (1-based, 0 means processing immediately)
        """
        async with self._lock:
            self._queue.append(task)
            position = len(self._queue)

            # Start processor if not running
            if not self._processing:
                self._processing = True
                self._processor_task = asyncio.create_task(self._process_queue())

            return position if self._current_task else 0

    async def get_position(self, chat_id: int, message_id: int) -> int:
        """Get position of a task in queue."""
        async with self._lock:
            for i, task in enumerate(self._queue):
                if task.chat_id == chat_id and task.message_id == message_id:
                    return i + 1
            return 0

    async def _process_queue(self):
        """Process tasks in the queue sequentially."""
        while True:
            async with self._lock:
                if not self._queue:
                    self._processing = False
                    self._current_task = None
                    return

                self._current_task = self._queue.popleft()

            try:
                await self._execute_download(self._current_task)
            except Exception as e:
                logger.error(f"Error processing download task: {e}")

            async with self._lock:
                self._current_task = None

    async def _execute_download(self, task: DownloadTask):
        """Execute a single download task."""
        downloader = Downloader()

        async def progress_wrapper(percent: float, status: str):
            if task.progress_callback:
                await task.progress_callback(percent, status)

        result = await downloader.download(
            url=task.original_url,
            quality=task.quality,
            progress_callback=progress_wrapper,
        )

        # Notify completion through callback with result
        if task.progress_callback:
            if result.success:
                await task.progress_callback(100, f"complete|{result.filepath}|{result.title}|{result.filesize_mb}")
            else:
                await task.progress_callback(-1, f"error|{result.error_message}")


# URL detection regex
URL_PATTERN = re.compile(
    r"https?://(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b[-a-zA-Z0-9()@:%_\+.~#?&//=]*"
)


def extract_urls(text: str) -> list[str]:
    """Extract all URLs from text."""
    return URL_PATTERN.findall(text)


class Downloader:
    """yt-dlp wrapper for downloading media."""

    def __init__(self):
        self.config = get_config()

    def _get_format_string(self, quality: DownloadQuality) -> str:
        """Get yt-dlp format string for quality."""
        format_map = {
            DownloadQuality.AUDIO_128: "bestaudio[abr<=128]/bestaudio",
            DownloadQuality.AUDIO_192: "bestaudio[abr<=192]/bestaudio",
            DownloadQuality.AUDIO_320: "bestaudio[abr<=320]/bestaudio",
            DownloadQuality.AUDIO_BEST: "bestaudio/best",
            DownloadQuality.VIDEO_480: "bestvideo[height<=480]+bestaudio/best[height<=480]",
            DownloadQuality.VIDEO_720: "bestvideo[height<=720]+bestaudio/best[height<=720]",
            DownloadQuality.VIDEO_1080: "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
            DownloadQuality.VIDEO_BEST: "bestvideo+bestaudio/best",
        }
        return format_map.get(quality, "best")

    def _is_audio_format(self, quality: DownloadQuality) -> bool:
        """Check if quality is audio format."""
        return quality.value.startswith("audio")

    async def get_info(self, url: str) -> Optional[MediaInfo]:
        """Get media information without downloading."""

        def _extract_info():
            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
                "extract_flat": "in_playlist",
            }

            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)

                    if info is None:
                        return None

                    is_playlist = info.get("_type") == "playlist"
                    entries = info.get("entries", [])

                    return MediaInfo(
                        title=info.get("title", "Unknown"),
                        duration=info.get("duration", 0) or 0,
                        is_playlist=is_playlist,
                        playlist_count=len(entries) if is_playlist else 1,
                        thumbnail=info.get("thumbnail"),
                        uploader=info.get("uploader", ""),
                        url=url,
                    )
            except Exception as e:
                logger.error(f"Failed to get info for {url}: {e}")
                return None

        return await asyncio.get_event_loop().run_in_executor(None, _extract_info)

    async def download(
        self,
        url: str,
        quality: DownloadQuality,
        progress_callback: Optional[Callable[[float, str], asyncio.Future]] = None,
    ) -> DownloadResult:
        """
        Download media from URL.

        Args:
            url: The URL to download
            quality: Quality setting
            progress_callback: Async callback for progress updates (percent, status)

        Returns:
            DownloadResult with success status and file info
        """
        is_audio = self._is_audio_format(quality)
        platform_dir = get_platform_directory(url)

        # Prepare yt-dlp options
        ydl_opts = {
            "format": self._get_format_string(quality),
            "outtmpl": str(platform_dir / "%(title)s.%(ext)s"),
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,  # Download single video by default
        }

        if is_audio:
            ydl_opts.update({
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": quality.value.split("_")[1] if "_" in quality.value else "192",
                }],
            })

        # Progress hook
        last_progress = [0]

        def progress_hook(d):
            if d["status"] == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
                downloaded = d.get("downloaded_bytes", 0)

                if total > 0:
                    percent = (downloaded / total) * 100
                    # Only update every 5%
                    if percent - last_progress[0] >= 5:
                        last_progress[0] = percent
                        if progress_callback:
                            asyncio.create_task(progress_callback(percent, "downloading"))

            elif d["status"] == "finished":
                if progress_callback:
                    asyncio.create_task(progress_callback(95, "processing"))

        ydl_opts["progress_hooks"] = [progress_hook]

        def _download():
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)

                    if info is None:
                        return DownloadResult(
                            success=False,
                            error_message="Could not extract media information"
                        )

                    title = info.get("title", "Unknown")
                    duration = info.get("duration", 0) or 0

                    # Find the downloaded file
                    if is_audio:
                        ext = "mp3"
                    else:
                        ext = info.get("ext", "mp4")

                    safe_title = sanitize_filename(title)
                    filepath = platform_dir / f"{safe_title}.{ext}"

                    # Handle potential yt-dlp naming variations
                    if not filepath.exists():
                        # Try to find the file with original title
                        for f in platform_dir.iterdir():
                            if f.stem.startswith(safe_title[:50]) and f.suffix == f".{ext}":
                                filepath = f
                                break

                    if not filepath.exists():
                        # Last resort: find most recent file
                        files = list(platform_dir.glob(f"*.{ext}"))
                        if files:
                            filepath = max(files, key=lambda x: x.stat().st_mtime)
                        else:
                            return DownloadResult(
                                success=False,
                                error_message="Downloaded file not found"
                            )

                    filesize_mb = get_file_size_mb(filepath)

                    return DownloadResult(
                        success=True,
                        filepath=filepath,
                        title=title,
                        duration=duration,
                        filesize_mb=filesize_mb,
                    )

            except yt_dlp.utils.DownloadError as e:
                error_msg = str(e)
                # Clean up common error messages
                if "Video unavailable" in error_msg:
                    error_msg = "Video is unavailable or private"
                elif "Sign in" in error_msg:
                    error_msg = "This content requires authentication"
                elif "age" in error_msg.lower():
                    error_msg = "Age-restricted content cannot be downloaded"

                return DownloadResult(success=False, error_message=error_msg)
            except Exception as e:
                logger.error(f"Download error: {e}")
                return DownloadResult(success=False, error_message=str(e))

        return await asyncio.get_event_loop().run_in_executor(None, _download)


# Global queue instance
download_queue = DownloadQueue()
