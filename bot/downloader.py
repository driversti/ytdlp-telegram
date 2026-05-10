import asyncio
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable, Optional, Union
from collections import deque

import yt_dlp

# Dedicated thread pool for downloads to avoid default executor issues
_download_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="ytdlp")

from bot.storage import get_platform_directory, sanitize_filename, get_file_size_mb
from config import get_config

logger = logging.getLogger(__name__)


# Default YouTube player clients. The yt-dlp default (`android_vr`) cannot
# extract unlisted videos — they surface as "This video is not available".
# `mweb`/`web`/`android`/`ios` handle unlisted; the POT-server provides the
# GVS PO Token they require for media URLs.
_YOUTUBE_EXTRACTOR_ARGS = {
    "youtube": {
        "player_client": ["mweb", "web", "android", "ios"],
    },
}


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
    quality: Union[DownloadQuality, "DynamicQuality"]
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


@dataclass
class PlaylistEntry:
    """Represents a single entry in a playlist."""

    url: str
    title: str
    duration: int = 0
    index: int = 0


@dataclass
class PlaylistInfo:
    """Information about a playlist."""

    title: str
    playlist_id: str
    entries: list[PlaylistEntry]
    uploader: str = ""

    @property
    def count(self) -> int:
        return len(self.entries)


@dataclass
class VideoFormat:
    """Represents an available video quality option."""
    height: int  # e.g., 720, 1080, 2160

    @property
    def label(self) -> str:
        return f"{self.height}p"


@dataclass
class AudioFormat:
    """Represents an available audio quality option."""
    bitrate: int  # e.g., 128, 192, 320

    @property
    def label(self) -> str:
        return f"{self.bitrate} kbps"


@dataclass
class AvailableFormats:
    """Container for available formats from a URL."""
    video_formats: list[VideoFormat]
    audio_formats: list[AudioFormat]
    error: Optional[str] = None


@dataclass
class DynamicQuality:
    """Quality setting for dynamically detected values."""
    is_audio: bool
    value: int  # height for video, bitrate for audio

    def get_format_string(self) -> str:
        if self.is_audio:
            return f"bestaudio[abr<={self.value}]/bestaudio/best"
        else:
            # Priority order:
            # 1. Separate video+audio streams at requested height (highest quality)
            # 2. Separate streams up to requested height
            # 3. Combined format at exact height
            # 4. Any best available
            return f"bestvideo[height={self.value}]+bestaudio/bestvideo[height<={self.value}]+bestaudio/best[height={self.value}]/best"


class DownloadQueue:
    """Sequential download queue - one download at a time."""

    def __init__(self):
        self._queue: deque[DownloadTask] = deque()
        self._current_task: Optional[DownloadTask] = None
        self._lock = asyncio.Lock()
        self._processing = False

    @property
    def active_count(self) -> int:
        """Number of currently active downloads."""
        return 1 if self._current_task else 0

    async def add(self, task: DownloadTask) -> int:
        """Add a task to the queue."""
        async with self._lock:
            self._queue.append(task)
            queue_position = len(self._queue)

            # Start processor if not running
            if not self._processing:
                self._processing = True
                asyncio.create_task(self._process_queue())

            # Return position (0 if we're first and nothing is running)
            if self._current_task is None and queue_position == 1:
                return 0
            return queue_position

    async def get_position(self, chat_id: int, message_id: int) -> int:
        """Get position of a task in queue."""
        async with self._lock:
            for i, task in enumerate(self._queue):
                if task.chat_id == chat_id and task.message_id == message_id:
                    return i + 1
            return 0

    async def get_queue_status(self) -> tuple[int, int]:
        """Get queue status (active_count, queue_length)."""
        async with self._lock:
            return self.active_count, len(self._queue)

    async def _process_queue(self):
        """Process tasks sequentially - one at a time."""
        while True:
            async with self._lock:
                if not self._queue:
                    self._processing = False
                    self._current_task = None
                    return

                task = self._queue.popleft()
                self._current_task = task

            try:
                await self._execute_download(task)
            except Exception:
                logger.exception(f"Error processing download task for: {task.original_url}")
            finally:
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
            try:
                if result.success:
                    await task.progress_callback(100, f"complete|{result.filepath}|{result.title}|{result.filesize_mb}")
                else:
                    await task.progress_callback(-1, f"error|{result.error_message}")
            except Exception:
                logger.exception(f"Error in progress callback for {task.original_url}")


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

    def _get_format_string(self, quality: Union[DownloadQuality, DynamicQuality]) -> str:
        """Get yt-dlp format string for quality."""
        if isinstance(quality, DynamicQuality):
            return quality.get_format_string()

        format_map = {
            DownloadQuality.AUDIO_128: "bestaudio[abr<=128]/bestaudio/best",
            DownloadQuality.AUDIO_192: "bestaudio[abr<=192]/bestaudio/best",
            DownloadQuality.AUDIO_320: "bestaudio[abr<=320]/bestaudio/best",
            DownloadQuality.AUDIO_BEST: "bestaudio/best",
            # Prefer separate streams for highest quality, then fall back to combined
            DownloadQuality.VIDEO_480: "bestvideo[height<=480]+bestaudio/best[height<=480]/best",
            DownloadQuality.VIDEO_720: "bestvideo[height<=720]+bestaudio/best[height<=720]/best",
            DownloadQuality.VIDEO_1080: "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best",
            DownloadQuality.VIDEO_BEST: "bestvideo+bestaudio/best",
        }
        return format_map.get(quality, "best")

    def _is_audio_format(self, quality: Union[DownloadQuality, DynamicQuality]) -> bool:
        """Check if quality is audio format."""
        if isinstance(quality, DynamicQuality):
            return quality.is_audio
        return quality.value.startswith("audio")

    def _round_to_standard_bitrate(self, bitrate: float) -> int:
        """Round bitrate to nearest standard value."""
        standard_bitrates = [64, 96, 128, 160, 192, 256, 320]
        return min(standard_bitrates, key=lambda x: abs(x - bitrate))

    async def get_available_formats(self, url: str, timeout: int = 30) -> AvailableFormats:
        """
        Get available video and audio formats for a URL.

        Args:
            url: The URL to analyze
            timeout: Timeout in seconds for format extraction

        Returns:
            AvailableFormats with detected qualities or error message
        """
        def _extract_formats():
            # Don't use android client for format detection - it returns limited formats
            # We want to see ALL available formats for the user to choose from
            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
                "extract_flat": False,
                "extractor_args": _YOUTUBE_EXTRACTOR_ARGS,
            }

            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)

                    if info is None:
                        return AvailableFormats([], [], error="Could not extract media information")

                    # Handle playlists - use first entry
                    if info.get("_type") == "playlist":
                        entries = info.get("entries", [])
                        if entries and entries[0]:
                            info = entries[0]
                        else:
                            return AvailableFormats([], [], error="Playlist is empty")

                    formats = info.get("formats", [])
                    if not formats:
                        return AvailableFormats([], [], error="No formats available")

                    # Extract unique video heights and audio bitrates
                    video_heights: set[int] = set()
                    audio_bitrates: set[int] = set()

                    for fmt in formats:
                        # Video formats
                        height = fmt.get("height")
                        vcodec = fmt.get("vcodec", "none")
                        if height and vcodec != "none":
                            video_heights.add(height)

                        # Audio formats
                        abr = fmt.get("abr")
                        acodec = fmt.get("acodec", "none")
                        if abr and acodec != "none":
                            rounded_bitrate = self._round_to_standard_bitrate(abr)
                            audio_bitrates.add(rounded_bitrate)

                    # Create sorted format lists (descending)
                    video_formats = [VideoFormat(h) for h in sorted(video_heights, reverse=True)]
                    audio_formats = [AudioFormat(b) for b in sorted(audio_bitrates, reverse=True)]

                    logger.info(f"Detected formats for {url}: video={[f.label for f in video_formats]}, audio={[f.label for f in audio_formats]}")

                    return AvailableFormats(video_formats, audio_formats)

            except yt_dlp.utils.DownloadError as e:
                error_msg = str(e)
                if "Video unavailable" in error_msg:
                    error_msg = "Video is unavailable or private"
                elif "Sign in" in error_msg:
                    error_msg = "This content requires authentication"
                elif "age" in error_msg.lower():
                    error_msg = "Age-restricted content"
                return AvailableFormats([], [], error=error_msg)
            except Exception as e:
                logger.error(f"Failed to get formats for {url}: {e}")
                return AvailableFormats([], [], error=str(e))

        loop = asyncio.get_running_loop()
        try:
            return await asyncio.wait_for(
                loop.run_in_executor(None, _extract_formats),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            return AvailableFormats([], [], error="Format detection timed out")

    async def get_info(self, url: str) -> Optional[MediaInfo]:
        """Get media information without downloading."""

        def _extract_info():
            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
                "extract_flat": "in_playlist",
                "extractor_args": _YOUTUBE_EXTRACTOR_ARGS,
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
            except Exception:
                logger.exception(f"Failed to get info for {url}")
                return None

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, _extract_info)

    async def get_playlist_info(self, url: str, timeout: int = 60) -> Optional[PlaylistInfo]:
        """
        Get detailed playlist information including entries.

        Args:
            url: The playlist URL
            timeout: Timeout in seconds for extraction

        Returns:
            PlaylistInfo with entries, or None if not a playlist
        """

        def _extract_playlist():
            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
                "extract_flat": "in_playlist",  # Only get basic info, don't resolve each video
                "extractor_args": _YOUTUBE_EXTRACTOR_ARGS,
            }

            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)

                    if info is None:
                        return None

                    # Check if it's a playlist
                    if info.get("_type") != "playlist":
                        return None

                    entries_data = info.get("entries", [])
                    entries = []

                    for idx, entry in enumerate(entries_data):
                        if entry is None:
                            continue
                        # Build the full URL for the entry
                        entry_url = entry.get("url") or entry.get("webpage_url", "")
                        if not entry_url and entry.get("id"):
                            # For YouTube, construct URL from video ID
                            entry_url = f"https://www.youtube.com/watch?v={entry.get('id')}"

                        if entry_url:
                            entries.append(PlaylistEntry(
                                url=entry_url,
                                title=entry.get("title", f"Video {idx + 1}"),
                                duration=entry.get("duration", 0) or 0,
                                index=idx + 1,
                            ))

                    return PlaylistInfo(
                        title=info.get("title", "Unknown Playlist"),
                        playlist_id=info.get("id", ""),
                        entries=entries,
                        uploader=info.get("uploader", ""),
                    )

            except yt_dlp.utils.DownloadError as e:
                logger.warning(f"Failed to get playlist info for {url}: {e}")
                return None
            except Exception:
                logger.exception(f"Failed to get playlist info for {url}")
                return None

        loop = asyncio.get_running_loop()
        try:
            return await asyncio.wait_for(
                loop.run_in_executor(None, _extract_playlist),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            logger.warning(f"Playlist extraction timed out for {url}")
            return None

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
        # Capture event loop for thread-safe callbacks from executor
        loop = asyncio.get_running_loop()

        is_audio = self._is_audio_format(quality)
        platform_dir = get_platform_directory(url)

        format_string = self._get_format_string(quality)
        logger.info(f"Starting download: url={url}, quality={quality}, format_string={format_string}")

        # Prepare yt-dlp options
        # Include video ID in filename to avoid collisions (Instagram videos have same titles)
        ydl_opts = {
            "format": format_string,
            "outtmpl": str(platform_dir / "%(title)s_%(id)s.%(ext)s"),
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,  # Download single video by default
            "extractor_args": _YOUTUBE_EXTRACTOR_ARGS,
        }

        if is_audio:
            # Determine audio quality for postprocessor
            if isinstance(quality, DynamicQuality):
                audio_quality = str(quality.value)
            elif quality == DownloadQuality.AUDIO_BEST:
                audio_quality = "0"  # Best quality for ffmpeg
            else:
                audio_quality = quality.value.split("_")[1]

            ydl_opts.update({
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": audio_quality,
                }],
            })
        else:
            # Force MP4 container for video downloads (VP9/WebM → MP4)
            ydl_opts["merge_output_format"] = "mp4"

        # Progress hook
        last_progress = [0]

        def progress_hook(d):
            status = d.get("status", "unknown")
            if status == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
                downloaded = d.get("downloaded_bytes", 0)

                if total > 0:
                    percent = (downloaded / total) * 100
                    # Only update every 5%
                    if percent - last_progress[0] >= 5:
                        last_progress[0] = percent
                        if progress_callback:
                            loop.call_soon_threadsafe(
                                lambda p=percent: asyncio.create_task(progress_callback(p, "downloading"))
                            )

            elif status == "finished":
                if progress_callback:
                    loop.call_soon_threadsafe(
                        lambda: asyncio.create_task(progress_callback(95, "processing"))
                    )

        ydl_opts["progress_hooks"] = [progress_hook]

        def _download():
            try:
                ydl = yt_dlp.YoutubeDL(ydl_opts)
                try:
                    info = ydl.extract_info(url, download=True)

                    if info is None:
                        return DownloadResult(
                            success=False,
                            error_message="Could not extract media information"
                        )

                    title = info.get("title", "Unknown")
                    duration = info.get("duration", 0) or 0

                    # Determine expected extension
                    if is_audio:
                        ext = "mp3"
                    else:
                        ext = info.get("ext", "mp4")

                    # Find the downloaded file using yt-dlp's requested_downloads
                    # This is the most reliable method as it contains the actual filepath
                    filepath = None
                    requested_downloads = info.get("requested_downloads")
                    if requested_downloads and len(requested_downloads) > 0:
                        download_info = requested_downloads[0]
                        filepath_str = download_info.get("filepath")
                        if filepath_str:
                            filepath = Path(filepath_str)
                            logger.debug(f"Found file via requested_downloads: {filepath}")

                    # Fallback: Try sanitized filename
                    if not filepath or not filepath.exists():
                        safe_title = sanitize_filename(title)
                        filepath = platform_dir / f"{safe_title}.{ext}"

                    # Fallback: Try to find file with partial title match
                    if not filepath.exists():
                        safe_title = sanitize_filename(title)
                        for f in platform_dir.iterdir():
                            if f.stem.startswith(safe_title[:50]) and f.suffix == f".{ext}":
                                filepath = f
                                logger.debug(f"Found file via partial match: {filepath}")
                                break

                    # Last resort: find most recent file with correct extension
                    if not filepath.exists():
                        files = list(platform_dir.glob(f"*.{ext}"))
                        if files:
                            filepath = max(files, key=lambda x: x.stat().st_mtime)
                            logger.debug(f"Found file via most recent: {filepath}")
                        else:
                            return DownloadResult(
                                success=False,
                                error_message="Downloaded file not found"
                            )

                    filesize_mb = get_file_size_mb(filepath)
                    logger.info(f"Download completed: {title} ({filesize_mb:.1f} MB)")

                    return DownloadResult(
                        success=True,
                        filepath=filepath,
                        title=title,
                        duration=duration,
                        filesize_mb=filesize_mb,
                    )
                finally:
                    ydl.close()

            except yt_dlp.utils.DownloadError as e:
                error_msg = str(e)
                logger.warning(f"Download failed for {url}: {error_msg}")
                # Clean up common error messages
                if "Video unavailable" in error_msg:
                    error_msg = "Video is unavailable or private"
                elif "Sign in" in error_msg:
                    error_msg = "This content requires authentication"
                elif "age" in error_msg.lower():
                    error_msg = "Age-restricted content cannot be downloaded"

                return DownloadResult(success=False, error_message=error_msg)
            except Exception:
                logger.exception(f"Unexpected download error for {url}")
                return DownloadResult(success=False, error_message="Unexpected download error")

        return await loop.run_in_executor(_download_executor, _download)


# Global queue instance
download_queue = DownloadQueue()
