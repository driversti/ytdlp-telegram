"""Shared fixtures for tests."""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock

import pytest

# Set up environment variables BEFORE importing any bot modules
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-token-123")
os.environ.setdefault("ALLOWED_USER_IDS", "123,456,789")
os.environ.setdefault("DOWNLOAD_PATH", tempfile.mkdtemp())
os.environ.setdefault("OLLAMA_URL", "http://localhost:11434")
os.environ.setdefault("OLLAMA_MODEL", "llama3.2:3b")
os.environ.setdefault("MAX_FILE_SIZE_MB", "50")
os.environ.setdefault("FILE_SERVER_URL", "http://localhost:8080")
os.environ.setdefault("FILE_SERVER_PUBLIC_URL", "http://localhost:8080")

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


@pytest.fixture
def temp_download_dir(tmp_path):
    """Create a temporary download directory."""
    download_dir = tmp_path / "downloads"
    download_dir.mkdir()
    return download_dir


@pytest.fixture
def mock_config(temp_download_dir, monkeypatch):
    """Mock the config module with test values."""
    from config import Config

    test_config = Config(
        telegram_bot_token="test-token-123",
        allowed_user_ids={123, 456, 789},
        admin_user_id=None,
        ollama_url="http://localhost:11434",
        ollama_model="llama3.2:3b",
        download_path=str(temp_download_dir),
        max_file_size_mb=50,
        file_server_url="http://localhost:8080",
        file_server_public_url="http://localhost:8080",
        download_timeout=1800,
        format_detection_timeout=30,
        llm_timeout=30,
    )

    # Patch get_config to return our test config
    monkeypatch.setattr("config.config", test_config)
    monkeypatch.setattr("config.get_config", lambda: test_config)

    return test_config


@pytest.fixture
def sample_urls():
    """Sample URLs for testing."""
    return {
        "youtube": [
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://youtu.be/dQw4w9WgXcQ",
            "https://youtube.com/shorts/abc123",
        ],
        "instagram": [
            "https://www.instagram.com/p/ABC123/",
            "https://instagram.com/reel/XYZ789/",
            "https://instagr.am/p/test",
        ],
        "twitter": [
            "https://twitter.com/user/status/123456",
            "https://x.com/user/status/789012",
        ],
        "facebook": [
            "https://www.facebook.com/watch?v=123456",
            "https://fb.watch/abc123/",
            "https://fb.com/video/789",
        ],
        "tiktok": [
            "https://www.tiktok.com/@user/video/123456",
            "https://tiktok.com/t/abc123/",
        ],
        "vimeo": [
            "https://vimeo.com/123456789",
        ],
        "reddit": [
            "https://www.reddit.com/r/videos/comments/abc123/",
            "https://redd.it/abc123",
        ],
        "twitch": [
            "https://www.twitch.tv/videos/123456789",
            "https://clips.twitch.tv/ClipName",
        ],
        "other": [
            "https://example.com/video.mp4",
            "https://unknown-site.org/media/123",
        ],
    }


@pytest.fixture
def mock_telegram_update():
    """Create a mock Telegram Update object."""
    update = MagicMock()
    update.message = MagicMock()
    update.message.chat_id = 123
    update.message.message_id = 456
    update.message.text = ""
    update.message.reply_text = AsyncMock()
    update.callback_query = MagicMock()
    update.callback_query.answer = AsyncMock()
    update.callback_query.edit_message_text = AsyncMock()
    update.callback_query.message.chat_id = 123
    update.callback_query.message.message_id = 456
    update.effective_user = MagicMock()
    update.effective_user.id = 123
    return update


@pytest.fixture
def mock_telegram_context():
    """Create a mock Telegram Context object."""
    context = MagicMock()
    context.user_data = {}
    context.bot = MagicMock()
    context.bot.edit_message_text = AsyncMock()
    context.bot.send_audio = AsyncMock()
    context.bot.send_video = AsyncMock()
    return context


@pytest.fixture
def create_temp_file(tmp_path):
    """Factory fixture to create temporary files."""
    def _create_file(name: str, content: bytes = b"test content", subdir: str = None):
        if subdir:
            target_dir = tmp_path / subdir
            target_dir.mkdir(parents=True, exist_ok=True)
        else:
            target_dir = tmp_path

        filepath = target_dir / name
        filepath.write_bytes(content)
        return filepath

    return _create_file
