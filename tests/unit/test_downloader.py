"""Tests for bot/downloader.py module."""

import pytest

from bot.downloader import (
    extract_urls,
    DynamicQuality,
    DownloadQuality,
    DownloadTask,
    DownloadResult,
    MediaInfo,
    VideoFormat,
    AudioFormat,
    AvailableFormats,
    Downloader,
    URL_PATTERN,
)


class TestExtractUrls:
    """Tests for URL extraction from text."""

    def test_single_url_extraction(self):
        """Test extraction of a single URL."""
        text = "Check out this video: https://youtube.com/watch?v=test123"
        result = extract_urls(text)
        assert len(result) == 1
        assert result[0] == "https://youtube.com/watch?v=test123"

    def test_multiple_urls_extraction(self):
        """Test extraction of multiple URLs."""
        text = "Videos: https://youtube.com/1 and https://twitter.com/2"
        result = extract_urls(text)
        assert len(result) == 2
        assert "https://youtube.com/1" in result
        assert "https://twitter.com/2" in result

    def test_url_with_query_params(self):
        """Test extraction of URLs with query parameters."""
        text = "https://youtube.com/watch?v=test&list=playlist&index=5"
        result = extract_urls(text)
        assert len(result) == 1
        assert "list=playlist" in result[0]
        assert "index=5" in result[0]

    def test_url_with_fragments(self):
        """Test extraction of URLs with fragments."""
        text = "https://example.com/page#section"
        result = extract_urls(text)
        assert len(result) == 1
        # Fragment might be included depending on regex

    def test_http_and_https(self):
        """Test extraction of both HTTP and HTTPS URLs."""
        text = "http://example.com and https://secure.com"
        result = extract_urls(text)
        assert len(result) == 2

    def test_no_urls_in_text(self):
        """Test with text containing no URLs."""
        text = "This is just plain text without any links"
        result = extract_urls(text)
        assert len(result) == 0

    def test_url_with_special_characters(self):
        """Test extraction of URLs with special characters."""
        text = "https://example.com/path/to/file?name=test%20file&id=123"
        result = extract_urls(text)
        assert len(result) == 1

    def test_url_with_subdomain(self):
        """Test extraction of URLs with subdomains."""
        text = "https://www.sub.domain.example.com/path"
        result = extract_urls(text)
        assert len(result) == 1

    def test_url_with_port(self):
        """Test extraction of URLs with port numbers - currently not supported by regex."""
        text = "https://localhost:8080/api/test"
        result = extract_urls(text)
        # Note: The current regex doesn't support port numbers in URLs
        # This is a known limitation - localhost URLs with ports won't be extracted
        assert len(result) == 0  # Expected limitation

    def test_url_in_parentheses(self):
        """Test extraction of URLs surrounded by parentheses."""
        text = "Check this out (https://example.com/video)"
        result = extract_urls(text)
        assert len(result) == 1
        # URL might include trailing parenthesis depending on regex

    def test_youtube_short_url(self):
        """Test extraction of YouTube short URLs."""
        text = "https://youtu.be/dQw4w9WgXcQ"
        result = extract_urls(text)
        assert len(result) == 1
        assert result[0] == "https://youtu.be/dQw4w9WgXcQ"

    def test_url_at_end_of_sentence(self):
        """Test extraction of URL at end of sentence with punctuation."""
        text = "Visit https://example.com."
        result = extract_urls(text)
        assert len(result) == 1
        # Trailing period might be excluded

    def test_empty_text(self):
        """Test extraction from empty text."""
        result = extract_urls("")
        assert len(result) == 0

    def test_ftp_not_extracted(self):
        """Test that FTP URLs are not extracted (only HTTP/HTTPS)."""
        text = "ftp://files.example.com/download"
        result = extract_urls(text)
        assert len(result) == 0


class TestDynamicQuality:
    """Tests for DynamicQuality format string generation."""

    def test_audio_format_string_with_bitrate(self):
        """Test audio format string generation with bitrate."""
        quality = DynamicQuality(is_audio=True, value=192)
        format_str = quality.get_format_string()
        assert "bestaudio[abr<=192]" in format_str
        assert "bestaudio" in format_str
        assert "best" in format_str

    def test_audio_format_string_best_fallback(self):
        """Test that audio format string has fallback to bestaudio and best."""
        quality = DynamicQuality(is_audio=True, value=320)
        format_str = quality.get_format_string()
        assert "/bestaudio/" in format_str
        assert format_str.endswith("/best")

    def test_video_format_string_with_height(self):
        """Test video format string generation with height."""
        quality = DynamicQuality(is_audio=False, value=1080)
        format_str = quality.get_format_string()
        assert "height=1080" in format_str
        assert "bestvideo" in format_str
        assert "bestaudio" in format_str

    def test_video_format_string_has_fallbacks(self):
        """Test that video format string has proper fallbacks."""
        quality = DynamicQuality(is_audio=False, value=720)
        format_str = quality.get_format_string()
        # Should have exact height match first
        assert "bestvideo[height=720]" in format_str
        # Then height <= match
        assert "bestvideo[height<=720]" in format_str
        # Finally best fallback
        assert "best" in format_str

    def test_various_bitrates(self):
        """Test format strings for various bitrates."""
        for bitrate in [64, 128, 192, 256, 320]:
            quality = DynamicQuality(is_audio=True, value=bitrate)
            format_str = quality.get_format_string()
            assert f"abr<={bitrate}" in format_str

    def test_various_heights(self):
        """Test format strings for various video heights."""
        for height in [360, 480, 720, 1080, 1440, 2160]:
            quality = DynamicQuality(is_audio=False, value=height)
            format_str = quality.get_format_string()
            assert f"height={height}" in format_str


class TestDownloadQuality:
    """Tests for DownloadQuality enum."""

    def test_audio_qualities_exist(self):
        """Test that all audio quality levels exist."""
        assert DownloadQuality.AUDIO_128
        assert DownloadQuality.AUDIO_192
        assert DownloadQuality.AUDIO_320
        assert DownloadQuality.AUDIO_BEST

    def test_video_qualities_exist(self):
        """Test that all video quality levels exist."""
        assert DownloadQuality.VIDEO_480
        assert DownloadQuality.VIDEO_720
        assert DownloadQuality.VIDEO_1080
        assert DownloadQuality.VIDEO_BEST

    def test_audio_quality_values_start_with_audio(self):
        """Test that audio quality values start with 'audio'."""
        audio_qualities = [
            DownloadQuality.AUDIO_128,
            DownloadQuality.AUDIO_192,
            DownloadQuality.AUDIO_320,
            DownloadQuality.AUDIO_BEST,
        ]
        for q in audio_qualities:
            assert q.value.startswith("audio")

    def test_video_quality_values_start_with_video(self):
        """Test that video quality values start with 'video'."""
        video_qualities = [
            DownloadQuality.VIDEO_480,
            DownloadQuality.VIDEO_720,
            DownloadQuality.VIDEO_1080,
            DownloadQuality.VIDEO_BEST,
        ]
        for q in video_qualities:
            assert q.value.startswith("video")


class TestDownloader:
    """Tests for Downloader class methods."""

    @pytest.fixture
    def downloader(self, mock_config):
        """Create a Downloader instance."""
        return Downloader()

    def test_get_format_string_audio_qualities(self, downloader):
        """Test format string for audio qualities."""
        assert "bestaudio[abr<=128]" in downloader._get_format_string(DownloadQuality.AUDIO_128)
        assert "bestaudio[abr<=192]" in downloader._get_format_string(DownloadQuality.AUDIO_192)
        assert "bestaudio[abr<=320]" in downloader._get_format_string(DownloadQuality.AUDIO_320)
        assert "bestaudio" in downloader._get_format_string(DownloadQuality.AUDIO_BEST)

    def test_get_format_string_video_qualities(self, downloader):
        """Test format string for video qualities."""
        assert "height<=480" in downloader._get_format_string(DownloadQuality.VIDEO_480)
        assert "height<=720" in downloader._get_format_string(DownloadQuality.VIDEO_720)
        assert "height<=1080" in downloader._get_format_string(DownloadQuality.VIDEO_1080)
        assert "bestvideo+bestaudio" in downloader._get_format_string(DownloadQuality.VIDEO_BEST)

    def test_get_format_string_dynamic_quality(self, downloader):
        """Test format string with dynamic quality."""
        dynamic_audio = DynamicQuality(is_audio=True, value=256)
        dynamic_video = DynamicQuality(is_audio=False, value=1440)

        assert "abr<=256" in downloader._get_format_string(dynamic_audio)
        assert "height=1440" in downloader._get_format_string(dynamic_video)

    def test_is_audio_format_enum(self, downloader):
        """Test audio format detection with enum."""
        assert downloader._is_audio_format(DownloadQuality.AUDIO_128) is True
        assert downloader._is_audio_format(DownloadQuality.AUDIO_BEST) is True
        assert downloader._is_audio_format(DownloadQuality.VIDEO_720) is False
        assert downloader._is_audio_format(DownloadQuality.VIDEO_BEST) is False

    def test_is_audio_format_dynamic(self, downloader):
        """Test audio format detection with dynamic quality."""
        assert downloader._is_audio_format(DynamicQuality(is_audio=True, value=192)) is True
        assert downloader._is_audio_format(DynamicQuality(is_audio=False, value=720)) is False

    def test_round_to_standard_bitrate(self, downloader):
        """Test bitrate rounding to standard values."""
        # Exact matches
        assert downloader._round_to_standard_bitrate(128) == 128
        assert downloader._round_to_standard_bitrate(192) == 192
        assert downloader._round_to_standard_bitrate(320) == 320

        # Close values should round to nearest
        assert downloader._round_to_standard_bitrate(130) == 128
        assert downloader._round_to_standard_bitrate(180) == 192
        assert downloader._round_to_standard_bitrate(300) == 320

        # Edge cases
        assert downloader._round_to_standard_bitrate(50) == 64
        assert downloader._round_to_standard_bitrate(400) == 320


class TestDataClasses:
    """Tests for data classes."""

    def test_download_task_creation(self):
        """Test DownloadTask creation."""
        task = DownloadTask(
            url="https://youtube.com/watch?v=test",
            quality=DownloadQuality.VIDEO_720,
            chat_id=123,
            message_id=456,
        )
        assert task.url == "https://youtube.com/watch?v=test"
        assert task.quality == DownloadQuality.VIDEO_720
        assert task.chat_id == 123
        assert task.message_id == 456
        assert task.original_url == task.url  # Auto-set in __post_init__

    def test_download_task_with_original_url(self):
        """Test DownloadTask with explicit original_url."""
        task = DownloadTask(
            url="short",
            quality=DownloadQuality.AUDIO_BEST,
            chat_id=1,
            message_id=2,
            original_url="https://very-long-url.com/full/path",
        )
        assert task.url == "short"
        assert task.original_url == "https://very-long-url.com/full/path"

    def test_download_result_success(self):
        """Test DownloadResult for successful download."""
        from pathlib import Path

        result = DownloadResult(
            success=True,
            filepath=Path("/downloads/video.mp4"),
            title="Test Video",
            duration=120,
            filesize_mb=25.5,
        )
        assert result.success is True
        assert result.error_message == ""

    def test_download_result_failure(self):
        """Test DownloadResult for failed download."""
        result = DownloadResult(
            success=False,
            error_message="Video unavailable",
        )
        assert result.success is False
        assert result.error_message == "Video unavailable"
        assert result.filepath is None

    def test_media_info_creation(self):
        """Test MediaInfo creation."""
        info = MediaInfo(
            title="Test Video",
            duration=300,
            is_playlist=False,
            playlist_count=1,
            thumbnail="https://img.youtube.com/vi/abc/default.jpg",
            uploader="Test Channel",
            url="https://youtube.com/watch?v=abc",
        )
        assert info.title == "Test Video"
        assert info.duration == 300
        assert info.is_playlist is False
        assert info.playlist_count == 1

    def test_media_info_playlist(self):
        """Test MediaInfo for playlist."""
        info = MediaInfo(
            title="My Playlist",
            duration=0,
            is_playlist=True,
            playlist_count=15,
        )
        assert info.is_playlist is True
        assert info.playlist_count == 15

    def test_video_format_label(self):
        """Test VideoFormat label generation."""
        fmt = VideoFormat(height=1080)
        assert fmt.label == "1080p"

        fmt2 = VideoFormat(height=720)
        assert fmt2.label == "720p"

    def test_audio_format_label(self):
        """Test AudioFormat label generation."""
        fmt = AudioFormat(bitrate=320)
        assert fmt.label == "320 kbps"

        fmt2 = AudioFormat(bitrate=128)
        assert fmt2.label == "128 kbps"

    def test_available_formats_with_error(self):
        """Test AvailableFormats with error."""
        formats = AvailableFormats(
            video_formats=[],
            audio_formats=[],
            error="Video unavailable",
        )
        assert formats.error == "Video unavailable"
        assert len(formats.video_formats) == 0
        assert len(formats.audio_formats) == 0

    def test_available_formats_success(self):
        """Test AvailableFormats with formats."""
        formats = AvailableFormats(
            video_formats=[VideoFormat(1080), VideoFormat(720), VideoFormat(480)],
            audio_formats=[AudioFormat(320), AudioFormat(192), AudioFormat(128)],
        )
        assert formats.error is None
        assert len(formats.video_formats) == 3
        assert len(formats.audio_formats) == 3


class TestURLPattern:
    """Tests for the URL pattern regex."""

    def test_pattern_matches_https(self):
        """Test that pattern matches HTTPS URLs."""
        assert URL_PATTERN.match("https://example.com")
        assert URL_PATTERN.match("https://www.example.com/path")

    def test_pattern_matches_http(self):
        """Test that pattern matches HTTP URLs."""
        assert URL_PATTERN.match("http://example.com")
        assert URL_PATTERN.match("http://www.example.com/path")

    def test_pattern_does_not_match_ftp(self):
        """Test that pattern does not match FTP."""
        assert URL_PATTERN.match("ftp://example.com") is None

    def test_pattern_does_not_match_plain_text(self):
        """Test that pattern does not match plain text."""
        assert URL_PATTERN.match("just some text") is None
        assert URL_PATTERN.match("example.com") is None  # Missing protocol

    def test_pattern_matches_complex_urls(self):
        """Test pattern matches complex URLs."""
        complex_urls = [
            "https://youtube.com/watch?v=abc123&list=xyz",
            "https://example.com/path/to/resource?query=value&another=one",
            "https://subdomain.example.co.uk/page",
        ]
        for url in complex_urls:
            assert URL_PATTERN.match(url), f"Failed to match: {url}"
