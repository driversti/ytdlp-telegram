import os
import re
import logging
from pathlib import Path
from urllib.parse import urlparse

from config import get_config

logger = logging.getLogger(__name__)

# Platform detection patterns
PLATFORM_PATTERNS = {
    "youtube": [
        r"(?:youtube\.com|youtu\.be)",
    ],
    "instagram": [
        r"instagram\.com",
        r"instagr\.am",
    ],
    "twitter": [
        r"twitter\.com",
        r"x\.com",
    ],
    "facebook": [
        r"facebook\.com",
        r"fb\.watch",
        r"fb\.com",
    ],
    "tiktok": [
        r"tiktok\.com",
    ],
    "vimeo": [
        r"vimeo\.com",
    ],
    "reddit": [
        r"reddit\.com",
        r"redd\.it",
    ],
    "twitch": [
        r"twitch\.tv",
    ],
}


def detect_platform(url: str) -> str:
    """Detect the platform from URL."""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()

        for platform, patterns in PLATFORM_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, domain):
                    return platform

        return "other"
    except Exception:
        return "other"


def sanitize_filename(filename: str, max_length: int = 200) -> str:
    """
    Sanitize a filename to be safe for the filesystem.

    Args:
        filename: The original filename
        max_length: Maximum length for the filename (without extension)

    Returns:
        Sanitized filename
    """
    # Remove or replace problematic characters
    # Keep alphanumeric, spaces, dashes, underscores, dots, and some unicode
    sanitized = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", filename)

    # Replace multiple spaces/underscores with single ones
    sanitized = re.sub(r"\s+", " ", sanitized)
    sanitized = re.sub(r"_+", "_", sanitized)

    # Trim whitespace
    sanitized = sanitized.strip()

    # Truncate if too long (preserve extension if present)
    if len(sanitized) > max_length:
        name, ext = os.path.splitext(sanitized)
        max_name_length = max_length - len(ext)
        sanitized = name[:max_name_length].rstrip() + ext

    # Fallback if empty
    if not sanitized or sanitized in (".", ".."):
        sanitized = "download"

    return sanitized


def get_platform_directory(url: str) -> Path:
    """Get the directory path for a platform."""
    config = get_config()
    platform = detect_platform(url)
    platform_dir = Path(config.download_path) / platform
    platform_dir.mkdir(parents=True, exist_ok=True)
    return platform_dir


def get_download_path(url: str, title: str, extension: str) -> Path:
    """
    Get the full download path for a file.

    Args:
        url: The source URL
        title: The media title
        extension: File extension (without dot)

    Returns:
        Full path for the download
    """
    platform_dir = get_platform_directory(url)
    safe_title = sanitize_filename(title)

    # Ensure extension doesn't have a leading dot
    extension = extension.lstrip(".")

    filename = f"{safe_title}.{extension}"
    filepath = platform_dir / filename

    # Handle duplicates by adding a number
    counter = 1
    while filepath.exists():
        filename = f"{safe_title} ({counter}).{extension}"
        filepath = platform_dir / filename
        counter += 1

    return filepath


def get_file_size(filepath: Path) -> int:
    """Get file size in bytes."""
    return filepath.stat().st_size if filepath.exists() else 0


def get_file_size_mb(filepath: Path) -> float:
    """Get file size in megabytes."""
    return get_file_size(filepath) / (1024 * 1024)


def is_file_within_limit(filepath: Path) -> bool:
    """Check if file is within the Telegram upload limit."""
    config = get_config()
    return get_file_size(filepath) <= config.max_file_size_bytes


def cleanup_file(filepath: Path) -> bool:
    """Remove a file from disk."""
    try:
        if filepath.exists():
            filepath.unlink()
            logger.info(f"Cleaned up file: {filepath}")
            return True
    except Exception as e:
        logger.error(f"Failed to cleanup file {filepath}: {e}")
    return False


def ensure_directories_exist():
    """Ensure all platform directories exist."""
    config = get_config()
    base_path = Path(config.download_path)

    for platform in list(PLATFORM_PATTERNS.keys()) + ["other"]:
        platform_dir = base_path / platform
        platform_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"Download directories initialized at {base_path}")
