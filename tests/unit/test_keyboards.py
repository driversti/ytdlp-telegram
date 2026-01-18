"""Tests for bot/keyboards.py module."""

import pytest

from bot.keyboards import (
    format_selection_keyboard,
    audio_quality_keyboard,
    video_quality_keyboard,
    dynamic_video_quality_keyboard,
    dynamic_audio_quality_keyboard,
    playlist_confirmation_keyboard,
    file_delete_keyboard,
    parse_callback_data,
    FORMAT_PREFIX,
    QUALITY_PREFIX,
    CONFIRM_PREFIX,
    CANCEL_PREFIX,
    DELETE_PREFIX,
)
from bot.downloader import VideoFormat, AudioFormat


class TestCallbackDataPrefixes:
    """Tests for callback data prefix constants."""

    def test_prefix_values(self):
        """Test that prefixes have expected values."""
        assert FORMAT_PREFIX == "format:"
        assert QUALITY_PREFIX == "quality:"
        assert CONFIRM_PREFIX == "confirm:"
        assert CANCEL_PREFIX == "cancel:"
        assert DELETE_PREFIX == "delete:"

    def test_prefixes_end_with_colon(self):
        """Test that all prefixes end with colon."""
        prefixes = [FORMAT_PREFIX, QUALITY_PREFIX, CONFIRM_PREFIX, CANCEL_PREFIX, DELETE_PREFIX]
        for prefix in prefixes:
            assert prefix.endswith(":")


class TestParseCallbackData:
    """Tests for callback data parsing."""

    def test_parse_format_callback(self):
        """Test parsing format callback data."""
        prefix, action = parse_callback_data("format:audio")
        assert prefix == "format:"
        assert action == "audio"

    def test_parse_quality_callback(self):
        """Test parsing quality callback data."""
        prefix, action = parse_callback_data("quality:video_720")
        assert prefix == "quality:"
        assert action == "video_720"

    def test_parse_delete_callback_with_token(self):
        """Test parsing delete callback with UUID token."""
        token = "550e8400-e29b-41d4-a716-446655440000"
        prefix, action = parse_callback_data(f"delete:{token}")
        assert prefix == "delete:"
        assert action == token

    def test_parse_cancel_callback(self):
        """Test parsing cancel callback."""
        prefix, action = parse_callback_data("cancel:download")
        assert prefix == "cancel:"
        assert action == "download"

    def test_parse_no_prefix(self):
        """Test parsing data without prefix."""
        prefix, action = parse_callback_data("simple_action")
        assert prefix == ""
        assert action == "simple_action"

    def test_parse_multiple_colons(self):
        """Test parsing data with multiple colons."""
        prefix, action = parse_callback_data("prefix:action:extra")
        assert prefix == "prefix:"
        assert action == "action:extra"  # Rest after first colon


class TestFormatSelectionKeyboard:
    """Tests for format selection keyboard."""

    def test_keyboard_has_audio_button(self):
        """Test that keyboard has audio button."""
        kb = format_selection_keyboard()
        all_buttons = [btn for row in kb.inline_keyboard for btn in row]
        audio_buttons = [btn for btn in all_buttons if "Audio" in btn.text]
        assert len(audio_buttons) == 1
        assert audio_buttons[0].callback_data == f"{FORMAT_PREFIX}audio"

    def test_keyboard_has_video_button(self):
        """Test that keyboard has video button."""
        kb = format_selection_keyboard()
        all_buttons = [btn for row in kb.inline_keyboard for btn in row]
        video_buttons = [btn for btn in all_buttons if "Video" in btn.text]
        assert len(video_buttons) == 1
        assert video_buttons[0].callback_data == f"{FORMAT_PREFIX}video"

    def test_keyboard_has_cancel_button(self):
        """Test that keyboard has cancel button."""
        kb = format_selection_keyboard()
        all_buttons = [btn for row in kb.inline_keyboard for btn in row]
        cancel_buttons = [btn for btn in all_buttons if "Cancel" in btn.text]
        assert len(cancel_buttons) == 1
        assert cancel_buttons[0].callback_data.startswith(CANCEL_PREFIX)


class TestAudioQualityKeyboard:
    """Tests for audio quality selection keyboard."""

    def test_keyboard_has_quality_options(self):
        """Test that keyboard has quality options."""
        kb = audio_quality_keyboard()
        all_buttons = [btn for row in kb.inline_keyboard for btn in row]

        # Check for expected quality options
        quality_texts = ["128 kbps", "192 kbps", "320 kbps"]
        for text in quality_texts:
            matching = [btn for btn in all_buttons if text in btn.text]
            assert len(matching) == 1, f"Missing quality option: {text}"

    def test_keyboard_has_best_option(self):
        """Test that keyboard has 'Best' option."""
        kb = audio_quality_keyboard()
        all_buttons = [btn for row in kb.inline_keyboard for btn in row]
        best_buttons = [btn for btn in all_buttons if "Best" in btn.text]
        assert len(best_buttons) == 1
        assert best_buttons[0].callback_data == f"{QUALITY_PREFIX}audio_best"

    def test_keyboard_has_back_button(self):
        """Test that keyboard has back button."""
        kb = audio_quality_keyboard()
        all_buttons = [btn for row in kb.inline_keyboard for btn in row]
        back_buttons = [btn for btn in all_buttons if "Back" in btn.text]
        assert len(back_buttons) == 1
        assert back_buttons[0].callback_data == f"{FORMAT_PREFIX}back"

    def test_quality_callback_data_format(self):
        """Test that quality callback data is properly formatted."""
        kb = audio_quality_keyboard()
        all_buttons = [btn for row in kb.inline_keyboard for btn in row]

        for btn in all_buttons:
            if btn.callback_data.startswith(QUALITY_PREFIX):
                action = btn.callback_data.replace(QUALITY_PREFIX, "")
                assert action.startswith("audio_")


class TestVideoQualityKeyboard:
    """Tests for video quality selection keyboard."""

    def test_keyboard_has_quality_options(self):
        """Test that keyboard has quality options."""
        kb = video_quality_keyboard()
        all_buttons = [btn for row in kb.inline_keyboard for btn in row]

        # Check for expected quality options
        quality_texts = ["480p", "720p", "1080p"]
        for text in quality_texts:
            matching = [btn for btn in all_buttons if text in btn.text]
            assert len(matching) == 1, f"Missing quality option: {text}"

    def test_keyboard_has_best_option(self):
        """Test that keyboard has 'Best' option."""
        kb = video_quality_keyboard()
        all_buttons = [btn for row in kb.inline_keyboard for btn in row]
        best_buttons = [btn for btn in all_buttons if "Best" in btn.text]
        assert len(best_buttons) == 1
        assert best_buttons[0].callback_data == f"{QUALITY_PREFIX}video_best"

    def test_quality_callback_data_format(self):
        """Test that quality callback data is properly formatted."""
        kb = video_quality_keyboard()
        all_buttons = [btn for row in kb.inline_keyboard for btn in row]

        for btn in all_buttons:
            if btn.callback_data.startswith(QUALITY_PREFIX):
                action = btn.callback_data.replace(QUALITY_PREFIX, "")
                assert action.startswith("video_")


class TestDynamicVideoQualityKeyboard:
    """Tests for dynamic video quality keyboard."""

    def test_keyboard_with_formats(self):
        """Test keyboard generation with video formats."""
        formats = [VideoFormat(1080), VideoFormat(720), VideoFormat(480)]
        kb = dynamic_video_quality_keyboard(formats)

        all_buttons = [btn for row in kb.inline_keyboard for btn in row]

        # Check format buttons
        for fmt in formats:
            matching = [btn for btn in all_buttons if fmt.label in btn.text]
            assert len(matching) == 1
            assert matching[0].callback_data == f"{QUALITY_PREFIX}video_{fmt.height}"

    def test_keyboard_has_best_option(self):
        """Test that dynamic keyboard has 'Best' option."""
        formats = [VideoFormat(720)]
        kb = dynamic_video_quality_keyboard(formats)

        all_buttons = [btn for row in kb.inline_keyboard for btn in row]
        best_buttons = [btn for btn in all_buttons if "Best" in btn.text]
        assert len(best_buttons) == 1

    def test_keyboard_has_navigation(self):
        """Test that dynamic keyboard has navigation buttons."""
        formats = [VideoFormat(720)]
        kb = dynamic_video_quality_keyboard(formats)

        all_buttons = [btn for row in kb.inline_keyboard for btn in row]
        back_buttons = [btn for btn in all_buttons if "Back" in btn.text]
        cancel_buttons = [btn for btn in all_buttons if "Cancel" in btn.text]

        assert len(back_buttons) == 1
        assert len(cancel_buttons) == 1

    def test_keyboard_empty_formats(self):
        """Test keyboard with empty formats list."""
        kb = dynamic_video_quality_keyboard([])
        all_buttons = [btn for row in kb.inline_keyboard for btn in row]

        # Should still have Best, Back, and Cancel
        assert len(all_buttons) >= 3


class TestDynamicAudioQualityKeyboard:
    """Tests for dynamic audio quality keyboard."""

    def test_keyboard_with_formats(self):
        """Test keyboard generation with audio formats."""
        formats = [AudioFormat(320), AudioFormat(192), AudioFormat(128)]
        kb = dynamic_audio_quality_keyboard(formats)

        all_buttons = [btn for row in kb.inline_keyboard for btn in row]

        # Check format buttons
        for fmt in formats:
            matching = [btn for btn in all_buttons if fmt.label in btn.text]
            assert len(matching) == 1
            assert matching[0].callback_data == f"{QUALITY_PREFIX}audio_{fmt.bitrate}"

    def test_keyboard_has_best_option(self):
        """Test that dynamic keyboard has 'Best' option."""
        formats = [AudioFormat(192)]
        kb = dynamic_audio_quality_keyboard(formats)

        all_buttons = [btn for row in kb.inline_keyboard for btn in row]
        best_buttons = [btn for btn in all_buttons if "Best" in btn.text]
        assert len(best_buttons) == 1


class TestPlaylistConfirmationKeyboard:
    """Tests for playlist confirmation keyboard."""

    def test_keyboard_shows_count(self):
        """Test that keyboard shows item count."""
        kb = playlist_confirmation_keyboard(15)
        all_buttons = [btn for row in kb.inline_keyboard for btn in row]

        download_all = [btn for btn in all_buttons if "Download all" in btn.text]
        assert len(download_all) == 1
        assert "15" in download_all[0].text

    def test_keyboard_has_single_option(self):
        """Test that keyboard has 'First item only' option."""
        kb = playlist_confirmation_keyboard(10)
        all_buttons = [btn for row in kb.inline_keyboard for btn in row]

        single_buttons = [btn for btn in all_buttons if "First item" in btn.text]
        assert len(single_buttons) == 1
        assert single_buttons[0].callback_data == f"{CONFIRM_PREFIX}single"

    def test_keyboard_has_cancel(self):
        """Test that keyboard has cancel button."""
        kb = playlist_confirmation_keyboard(5)
        all_buttons = [btn for row in kb.inline_keyboard for btn in row]

        cancel_buttons = [btn for btn in all_buttons if "Cancel" in btn.text]
        assert len(cancel_buttons) == 1


class TestFileDeleteKeyboard:
    """Tests for file delete keyboard."""

    def test_keyboard_with_token(self):
        """Test keyboard includes token in callback data."""
        token = "test-uuid-token-123"
        kb = file_delete_keyboard(token)

        all_buttons = [btn for row in kb.inline_keyboard for btn in row]
        assert len(all_buttons) == 1

        delete_btn = all_buttons[0]
        assert "Delete" in delete_btn.text
        assert delete_btn.callback_data == f"{DELETE_PREFIX}{token}"

    def test_keyboard_single_button(self):
        """Test that keyboard has exactly one button."""
        kb = file_delete_keyboard("token")
        total_buttons = sum(len(row) for row in kb.inline_keyboard)
        assert total_buttons == 1
