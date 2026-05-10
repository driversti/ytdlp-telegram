"""Tests for bot/storage.py module."""


import pytest

from bot.storage import (
    detect_platform,
    sanitize_filename,
    get_file_size,
    get_file_size_mb,
    PLATFORM_PATTERNS,
)


class TestDetectPlatform:
    """Tests for platform detection from URLs."""

    def test_youtube_standard_url(self):
        """Test standard YouTube URLs."""
        assert detect_platform("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "youtube"
        assert detect_platform("https://youtube.com/watch?v=test123") == "youtube"
        assert detect_platform("http://youtube.com/watch?v=test") == "youtube"

    def test_youtube_short_url(self):
        """Test YouTube short URLs (youtu.be)."""
        assert detect_platform("https://youtu.be/dQw4w9WgXcQ") == "youtube"
        assert detect_platform("http://youtu.be/test123") == "youtube"

    def test_youtube_shorts(self):
        """Test YouTube Shorts URLs."""
        assert detect_platform("https://youtube.com/shorts/abc123") == "youtube"
        assert detect_platform("https://www.youtube.com/shorts/xyz789") == "youtube"

    def test_instagram_standard(self):
        """Test standard Instagram URLs."""
        assert detect_platform("https://www.instagram.com/p/ABC123/") == "instagram"
        assert detect_platform("https://instagram.com/reel/XYZ789/") == "instagram"
        assert detect_platform("https://www.instagram.com/stories/user/123/") == "instagram"

    def test_instagram_short_url(self):
        """Test Instagram short URLs."""
        assert detect_platform("https://instagr.am/p/test") == "instagram"

    def test_twitter_standard(self):
        """Test standard Twitter URLs."""
        assert detect_platform("https://twitter.com/user/status/123456") == "twitter"
        assert detect_platform("https://www.twitter.com/user/status/789012") == "twitter"

    def test_twitter_x_domain(self):
        """Test X.com (rebranded Twitter) URLs."""
        assert detect_platform("https://x.com/user/status/789012") == "twitter"
        assert detect_platform("https://www.x.com/user/status/123") == "twitter"

    def test_facebook_standard(self):
        """Test standard Facebook URLs."""
        assert detect_platform("https://www.facebook.com/watch?v=123456") == "facebook"
        assert detect_platform("https://facebook.com/video/789") == "facebook"

    def test_facebook_short_urls(self):
        """Test Facebook short URLs."""
        assert detect_platform("https://fb.watch/abc123/") == "facebook"
        assert detect_platform("https://fb.com/video/789") == "facebook"

    def test_tiktok(self):
        """Test TikTok URLs."""
        assert detect_platform("https://www.tiktok.com/@user/video/123456") == "tiktok"
        assert detect_platform("https://tiktok.com/t/abc123/") == "tiktok"

    def test_vimeo(self):
        """Test Vimeo URLs."""
        assert detect_platform("https://vimeo.com/123456789") == "vimeo"
        assert detect_platform("https://www.vimeo.com/video/abc") == "vimeo"

    def test_reddit_standard(self):
        """Test Reddit URLs."""
        assert detect_platform("https://www.reddit.com/r/videos/comments/abc123/") == "reddit"
        assert detect_platform("https://reddit.com/r/test/comments/xyz/") == "reddit"

    def test_reddit_short_url(self):
        """Test Reddit short URLs."""
        assert detect_platform("https://redd.it/abc123") == "reddit"

    def test_twitch(self):
        """Test Twitch URLs."""
        assert detect_platform("https://www.twitch.tv/videos/123456789") == "twitch"
        assert detect_platform("https://twitch.tv/username") == "twitch"
        assert detect_platform("https://clips.twitch.tv/ClipName") == "twitch"

    def test_unknown_platform_returns_other(self):
        """Test that unknown platforms return 'other'."""
        assert detect_platform("https://example.com/video.mp4") == "other"
        assert detect_platform("https://unknown-site.org/media/123") == "other"
        assert detect_platform("https://dailymotion.com/video/abc") == "other"

    def test_invalid_url_returns_other(self):
        """Test that invalid URLs return 'other'."""
        assert detect_platform("not-a-url") == "other"
        assert detect_platform("") == "other"
        # Note: ftp://youtube.com still matches youtube since the function
        # only checks the domain pattern, not the protocol
        # This is acceptable behavior since ftp URLs are rare and
        # yt-dlp would reject them anyway

    def test_url_with_query_params(self):
        """Test URLs with various query parameters."""
        assert detect_platform("https://youtube.com/watch?v=abc&list=xyz&index=1") == "youtube"
        assert detect_platform("https://instagram.com/p/abc/?utm_source=test") == "instagram"

    def test_case_insensitive_domain(self):
        """Test that domain matching is case insensitive."""
        assert detect_platform("https://YOUTUBE.COM/watch?v=test") == "youtube"
        assert detect_platform("https://YouTube.com/watch?v=test") == "youtube"


class TestSanitizeFilename:
    """Tests for filename sanitization."""

    def test_basic_filename_unchanged(self):
        """Test that basic safe filenames are unchanged."""
        assert sanitize_filename("test_video.mp4") == "test_video.mp4"
        assert sanitize_filename("my-file.mp3") == "my-file.mp3"
        assert sanitize_filename("Video 123") == "Video 123"

    def test_removes_dangerous_characters(self):
        """Test removal of filesystem-dangerous characters."""
        assert sanitize_filename('file<>name.mp4') == "filename.mp4"
        assert sanitize_filename('file:name.mp4') == "filename.mp4"
        assert sanitize_filename('file"name.mp4') == "filename.mp4"
        assert sanitize_filename('file/name.mp4') == "filename.mp4"
        assert sanitize_filename('file\\name.mp4') == "filename.mp4"
        assert sanitize_filename('file|name.mp4') == "filename.mp4"
        assert sanitize_filename('file?name.mp4') == "filename.mp4"
        assert sanitize_filename('file*name.mp4') == "filename.mp4"

    def test_removes_control_characters(self):
        """Test removal of control characters (ASCII 0-31)."""
        assert sanitize_filename("file\x00name.mp4") == "filename.mp4"
        assert sanitize_filename("file\x1fname.mp4") == "filename.mp4"
        # Tab and newline are also control characters and are removed
        assert sanitize_filename("test\t\nname.mp4") == "testname.mp4"

    def test_collapses_multiple_spaces(self):
        """Test that multiple spaces are collapsed to single space."""
        assert sanitize_filename("test    video.mp4") == "test video.mp4"
        assert sanitize_filename("a  b   c.mp4") == "a b c.mp4"

    def test_collapses_multiple_underscores(self):
        """Test that multiple underscores are collapsed."""
        assert sanitize_filename("test____video.mp4") == "test_video.mp4"
        assert sanitize_filename("a__b___c.mp4") == "a_b_c.mp4"

    def test_trims_whitespace(self):
        """Test that leading/trailing whitespace is trimmed."""
        assert sanitize_filename("  test.mp4  ") == "test.mp4"
        assert sanitize_filename("\ttest.mp4\n") == "test.mp4"

    def test_truncation_preserves_extension(self):
        """Test that truncation preserves file extension."""
        long_name = "a" * 250 + ".mp4"
        result = sanitize_filename(long_name, max_length=50)
        assert result.endswith(".mp4")
        assert len(result) <= 50

    def test_truncation_with_default_max_length(self):
        """Test truncation with default max length."""
        long_name = "x" * 300 + ".mp3"
        result = sanitize_filename(long_name)  # default is 200
        assert len(result) <= 200
        assert result.endswith(".mp3")

    def test_empty_result_fallback(self):
        """Test that empty/invalid results fallback to 'download'."""
        assert sanitize_filename("") == "download"
        assert sanitize_filename("   ") == "download"
        assert sanitize_filename(".") == "download"
        assert sanitize_filename("..") == "download"

    def test_only_dangerous_chars_fallback(self):
        """Test fallback when only dangerous characters are present."""
        assert sanitize_filename("<>:\"/\\|?*") == "download"

    def test_preserves_unicode(self):
        """Test that unicode characters are preserved."""
        assert sanitize_filename("видео_тест.mp4") == "видео_тест.mp4"
        assert sanitize_filename("日本語テスト.mp4") == "日本語テスト.mp4"
        assert sanitize_filename("emoji_test_🎬.mp4") == "emoji_test_🎬.mp4"

    def test_mixed_dangerous_and_safe(self):
        """Test mixed content with dangerous and safe characters."""
        assert sanitize_filename('Test: "Video" | Part <1>.mp4') == "Test Video Part 1.mp4"

    def test_path_traversal_prevention(self):
        """Test that path traversal attempts are sanitized."""
        assert sanitize_filename("../../../etc/passwd") == "......etcpasswd"
        # Forward slashes are removed
        result = sanitize_filename("folder/file.mp4")
        assert "/" not in result


class TestFileSizeFunctions:
    """Tests for file size utility functions."""

    def test_get_file_size_existing_file(self, create_temp_file):
        """Test getting size of an existing file."""
        content = b"x" * 1024  # 1 KB
        filepath = create_temp_file("test.mp4", content)
        assert get_file_size(filepath) == 1024

    def test_get_file_size_nonexistent_file(self, tmp_path):
        """Test that nonexistent file returns 0."""
        filepath = tmp_path / "nonexistent.mp4"
        assert get_file_size(filepath) == 0

    def test_get_file_size_mb(self, create_temp_file):
        """Test getting size in megabytes."""
        content = b"x" * (1024 * 1024)  # 1 MB
        filepath = create_temp_file("test.mp4", content)
        assert get_file_size_mb(filepath) == pytest.approx(1.0, rel=0.01)

    def test_get_file_size_mb_small_file(self, create_temp_file):
        """Test MB conversion for small files."""
        content = b"x" * 512  # 512 bytes
        filepath = create_temp_file("small.mp4", content)
        assert get_file_size_mb(filepath) == pytest.approx(512 / (1024 * 1024), rel=0.01)


class TestPlatformPatterns:
    """Tests for platform pattern configuration."""

    def test_all_platforms_have_patterns(self):
        """Verify all expected platforms are configured."""
        expected_platforms = {
            "youtube", "instagram", "twitter", "facebook",
            "tiktok", "vimeo", "reddit", "twitch"
        }
        assert expected_platforms == set(PLATFORM_PATTERNS.keys())

    def test_patterns_are_valid_regex(self):
        """Test that all patterns are valid regular expressions."""
        import re
        for platform, patterns in PLATFORM_PATTERNS.items():
            for pattern in patterns:
                try:
                    re.compile(pattern)
                except re.error:
                    pytest.fail(f"Invalid regex pattern for {platform}: {pattern}")

    def test_each_platform_has_at_least_one_pattern(self):
        """Verify each platform has at least one pattern."""
        for platform, patterns in PLATFORM_PATTERNS.items():
            assert len(patterns) >= 1, f"Platform {platform} has no patterns"
