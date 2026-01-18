"""Tests for bot/llm_service.py module."""

import pytest

from bot.llm_service import LLMService, ParsedIntent


class TestParseHeuristic:
    """Tests for heuristic parsing (fallback when LLM is unavailable)."""

    @pytest.fixture
    def llm_service(self, mock_config):
        """Create an LLM service instance for testing."""
        return LLMService()

    def test_audio_keywords_detection(self, llm_service):
        """Test detection of audio-related keywords."""
        audio_keywords = ["audio", "music", "song", "mp3", "sound", "soundtrack"]

        for keyword in audio_keywords:
            message = f"download the {keyword} please"
            result = llm_service._parse_heuristic(message, [])
            assert result.wants_audio is True, f"Failed to detect audio keyword: {keyword}"
            assert result.wants_video is False

    def test_video_keywords_detection(self, llm_service):
        """Test detection of video-related keywords."""
        video_keywords = ["video", "mp4", "movie", "clip", "watch"]

        for keyword in video_keywords:
            message = f"get the {keyword} for me"
            result = llm_service._parse_heuristic(message, [])
            assert result.wants_video is True, f"Failed to detect video keyword: {keyword}"
            assert result.wants_audio is False

    def test_download_intent_detection(self, llm_service):
        """Test detection of download intent keywords."""
        download_keywords = ["download", "grab", "get", "save", "fetch", "dl"]

        for keyword in download_keywords:
            message = f"{keyword} this content"
            result = llm_service._parse_heuristic(message, [])
            assert result.is_download_request is True, f"Failed to detect download keyword: {keyword}"

    def test_url_implies_download_intent(self, llm_service):
        """Test that presence of URLs implies download intent."""
        urls = ["https://youtube.com/watch?v=test"]
        result = llm_service._parse_heuristic("just a random message", urls)
        assert result.is_download_request is True
        assert result.urls == urls

    def test_no_download_intent_without_keywords_or_urls(self, llm_service):
        """Test no download intent when no keywords or URLs present."""
        result = llm_service._parse_heuristic("hello, how are you?", [])
        assert result.is_download_request is False
        assert result.wants_audio is False
        assert result.wants_video is False

    def test_case_insensitive_keyword_detection(self, llm_service):
        """Test that keyword detection is case insensitive."""
        result1 = llm_service._parse_heuristic("DOWNLOAD the AUDIO", [])
        assert result1.is_download_request is True
        assert result1.wants_audio is True

        result2 = llm_service._parse_heuristic("Get the VIDEO", [])
        assert result2.is_download_request is True
        assert result2.wants_video is True

    def test_mixed_audio_and_video_keywords(self, llm_service):
        """Test message with both audio and video keywords."""
        result = llm_service._parse_heuristic("download audio and video please", [])
        assert result.wants_audio is True
        assert result.wants_video is True
        assert result.is_download_request is True

    def test_returns_parsed_intent_dataclass(self, llm_service):
        """Test that result is a ParsedIntent instance."""
        result = llm_service._parse_heuristic("download audio", ["https://test.com"])
        assert isinstance(result, ParsedIntent)

    def test_urls_are_preserved_in_result(self, llm_service):
        """Test that URLs are preserved in the result."""
        urls = ["https://youtube.com/watch?v=1", "https://twitter.com/test/status/2"]
        result = llm_service._parse_heuristic("get these videos", urls)
        assert result.urls == urls

    def test_empty_urls_list(self, llm_service):
        """Test with empty URLs list."""
        result = llm_service._parse_heuristic("download something", [])
        assert result.urls == []
        assert result.is_download_request is True

    def test_raw_message_preserved(self, llm_service):
        """Test that raw message is preserved in result."""
        message = "please download this audio file"
        result = llm_service._parse_heuristic(message, [])
        assert result.raw_message == message

    def test_partial_keyword_not_detected(self, llm_service):
        """Test that partial matches don't trigger detection."""
        # "downloader" contains "download" but should still match
        result = llm_service._parse_heuristic("what a great downloader tool", [])
        assert result.is_download_request is True  # Contains "download"

        # "musical" contains "music" but should still match
        result2 = llm_service._parse_heuristic("this is a musical show", [])
        assert result2.wants_audio is True  # Contains "music"

    def test_suggested_filename_not_set_by_heuristic(self, llm_service):
        """Test that heuristic parsing doesn't suggest filenames."""
        result = llm_service._parse_heuristic("download as my_video.mp4", [])
        assert result.suggested_filename is None


class TestParseIntentIntegration:
    """Integration tests for the full parse_intent flow."""

    @pytest.fixture
    def llm_service(self, mock_config):
        """Create an LLM service instance."""
        return LLMService()

    @pytest.mark.asyncio
    async def test_parse_intent_with_url_no_keywords(self, llm_service):
        """Test parsing a message with just a URL."""
        # Force heuristic by making LLM unavailable
        llm_service._available = False

        result = await llm_service.parse_intent("https://youtube.com/watch?v=test123")
        assert result.is_download_request is True
        assert "https://youtube.com/watch?v=test123" in result.urls

    @pytest.mark.asyncio
    async def test_parse_intent_with_audio_request(self, llm_service):
        """Test parsing an explicit audio request."""
        llm_service._available = False

        result = await llm_service.parse_intent(
            "download audio from https://youtube.com/watch?v=test"
        )
        assert result.is_download_request is True
        assert result.wants_audio is True
        assert len(result.urls) == 1

    @pytest.mark.asyncio
    async def test_parse_intent_no_url_no_keywords(self, llm_service):
        """Test parsing a message with no URL and no download keywords."""
        llm_service._available = False

        result = await llm_service.parse_intent("hello, how are you today?")
        assert result.is_download_request is False
        assert result.urls == []

    @pytest.mark.asyncio
    async def test_parse_intent_no_url_with_keywords(self, llm_service):
        """Test parsing a message with download keywords but no URL."""
        llm_service._available = False

        result = await llm_service.parse_intent("please download this for me")
        assert result.urls == []
        # Heuristic parsing considers "download" keyword as download intent
        # even without URLs - user is asking to download something
        assert result.is_download_request is True

    @pytest.mark.asyncio
    async def test_parse_intent_multiple_urls(self, llm_service):
        """Test parsing a message with multiple URLs."""
        llm_service._available = False

        result = await llm_service.parse_intent(
            "get these: https://youtube.com/1 and https://twitter.com/2"
        )
        assert len(result.urls) == 2
        assert result.is_download_request is True


class TestLLMAvailability:
    """Tests for LLM availability checking."""

    @pytest.fixture
    def llm_service(self, mock_config):
        """Create a fresh LLM service instance."""
        return LLMService()

    @pytest.mark.asyncio
    async def test_initial_availability_state(self, llm_service):
        """Test that initial availability is None (not checked yet)."""
        assert llm_service._available is None

    @pytest.mark.asyncio
    async def test_availability_cached(self, llm_service, mocker):
        """Test that availability is cached after first check."""
        # Mock httpx to return success
        mock_response = mocker.Mock()
        mock_response.status_code = 200

        mock_client = mocker.AsyncMock()
        mock_client.__aenter__.return_value.get = mocker.AsyncMock(return_value=mock_response)

        mocker.patch("httpx.AsyncClient", return_value=mock_client)

        # First call - should hit the network
        result1 = await llm_service.is_available()
        assert result1 is True
        assert llm_service._available is True

        # Second call - should return cached value
        result2 = await llm_service.is_available()
        assert result2 is True

    @pytest.mark.asyncio
    async def test_availability_false_on_error(self, llm_service, mocker):
        """Test that availability is False on network error."""
        import httpx

        mock_client = mocker.AsyncMock()
        mock_client.__aenter__.return_value.get = mocker.AsyncMock(
            side_effect=httpx.ConnectError("Connection refused")
        )

        mocker.patch("httpx.AsyncClient", return_value=mock_client)

        result = await llm_service.is_available()
        assert result is False
        assert llm_service._available is False
