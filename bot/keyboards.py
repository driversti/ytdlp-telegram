from telegram import InlineKeyboardButton, InlineKeyboardMarkup


# Callback data prefixes
FORMAT_PREFIX = "format:"
QUALITY_PREFIX = "quality:"
CONFIRM_PREFIX = "confirm:"
CANCEL_PREFIX = "cancel:"


def format_selection_keyboard(url: str) -> InlineKeyboardMarkup:
    """Create keyboard for format selection (audio/video)."""
    # Encode URL in callback data (truncated if too long)
    url_short = url[:50] if len(url) > 50 else url

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎵 Audio", callback_data=f"{FORMAT_PREFIX}audio|{url_short}"),
            InlineKeyboardButton("🎬 Video", callback_data=f"{FORMAT_PREFIX}video|{url_short}"),
        ],
        [
            InlineKeyboardButton("❌ Cancel", callback_data=f"{CANCEL_PREFIX}download"),
        ]
    ])


def audio_quality_keyboard(url: str) -> InlineKeyboardMarkup:
    """Create keyboard for audio quality selection."""
    url_short = url[:50] if len(url) > 50 else url

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("128 kbps", callback_data=f"{QUALITY_PREFIX}audio_128|{url_short}"),
            InlineKeyboardButton("192 kbps", callback_data=f"{QUALITY_PREFIX}audio_192|{url_short}"),
        ],
        [
            InlineKeyboardButton("320 kbps", callback_data=f"{QUALITY_PREFIX}audio_320|{url_short}"),
            InlineKeyboardButton("🌟 Best", callback_data=f"{QUALITY_PREFIX}audio_best|{url_short}"),
        ],
        [
            InlineKeyboardButton("⬅️ Back", callback_data=f"{FORMAT_PREFIX}back|{url_short}"),
            InlineKeyboardButton("❌ Cancel", callback_data=f"{CANCEL_PREFIX}download"),
        ]
    ])


def video_quality_keyboard(url: str) -> InlineKeyboardMarkup:
    """Create keyboard for video quality selection."""
    url_short = url[:50] if len(url) > 50 else url

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("480p", callback_data=f"{QUALITY_PREFIX}video_480|{url_short}"),
            InlineKeyboardButton("720p", callback_data=f"{QUALITY_PREFIX}video_720|{url_short}"),
        ],
        [
            InlineKeyboardButton("1080p", callback_data=f"{QUALITY_PREFIX}video_1080|{url_short}"),
            InlineKeyboardButton("🌟 Best", callback_data=f"{QUALITY_PREFIX}video_best|{url_short}"),
        ],
        [
            InlineKeyboardButton("⬅️ Back", callback_data=f"{FORMAT_PREFIX}back|{url_short}"),
            InlineKeyboardButton("❌ Cancel", callback_data=f"{CANCEL_PREFIX}download"),
        ]
    ])


def playlist_confirmation_keyboard(url: str, count: int) -> InlineKeyboardMarkup:
    """Create keyboard for playlist download confirmation."""
    url_short = url[:50] if len(url) > 50 else url

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                f"✅ Download all {count} items",
                callback_data=f"{CONFIRM_PREFIX}playlist|{url_short}"
            ),
        ],
        [
            InlineKeyboardButton(
                "📄 First item only",
                callback_data=f"{CONFIRM_PREFIX}single|{url_short}"
            ),
        ],
        [
            InlineKeyboardButton("❌ Cancel", callback_data=f"{CANCEL_PREFIX}download"),
        ]
    ])


def parse_callback_data(data: str) -> tuple[str, str, str]:
    """
    Parse callback data into prefix, action, and URL.

    Returns:
        Tuple of (prefix, action, url)
    """
    if "|" in data:
        prefix_action, url = data.split("|", 1)
    else:
        prefix_action = data
        url = ""

    if ":" in prefix_action:
        prefix, action = prefix_action.split(":", 1)
        prefix = prefix + ":"
    else:
        prefix = ""
        action = prefix_action

    return prefix, action, url
