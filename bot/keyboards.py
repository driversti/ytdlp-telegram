from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bot.downloader import VideoFormat, AudioFormat


# Callback data prefixes
FORMAT_PREFIX = "format:"
QUALITY_PREFIX = "quality:"
CONFIRM_PREFIX = "confirm:"
CANCEL_PREFIX = "cancel:"
DELETE_PREFIX = "delete:"


def format_selection_keyboard() -> InlineKeyboardMarkup:
    """Create keyboard for format selection (audio/video)."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎵 Audio", callback_data=f"{FORMAT_PREFIX}audio"),
            InlineKeyboardButton("🎬 Video", callback_data=f"{FORMAT_PREFIX}video"),
        ],
        [
            InlineKeyboardButton("❌ Cancel", callback_data=f"{CANCEL_PREFIX}download"),
        ]
    ])


def audio_quality_keyboard() -> InlineKeyboardMarkup:
    """Create keyboard for audio quality selection."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("128 kbps", callback_data=f"{QUALITY_PREFIX}audio_128"),
            InlineKeyboardButton("192 kbps", callback_data=f"{QUALITY_PREFIX}audio_192"),
        ],
        [
            InlineKeyboardButton("320 kbps", callback_data=f"{QUALITY_PREFIX}audio_320"),
            InlineKeyboardButton("🌟 Best", callback_data=f"{QUALITY_PREFIX}audio_best"),
        ],
        [
            InlineKeyboardButton("⬅️ Back", callback_data=f"{FORMAT_PREFIX}back"),
            InlineKeyboardButton("❌ Cancel", callback_data=f"{CANCEL_PREFIX}download"),
        ]
    ])


def video_quality_keyboard() -> InlineKeyboardMarkup:
    """Create keyboard for video quality selection (fallback with default options)."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("480p", callback_data=f"{QUALITY_PREFIX}video_480"),
            InlineKeyboardButton("720p", callback_data=f"{QUALITY_PREFIX}video_720"),
        ],
        [
            InlineKeyboardButton("1080p", callback_data=f"{QUALITY_PREFIX}video_1080"),
            InlineKeyboardButton("🌟 Best", callback_data=f"{QUALITY_PREFIX}video_best"),
        ],
        [
            InlineKeyboardButton("⬅️ Back", callback_data=f"{FORMAT_PREFIX}back"),
            InlineKeyboardButton("❌ Cancel", callback_data=f"{CANCEL_PREFIX}download"),
        ]
    ])


def dynamic_video_quality_keyboard(formats: list["VideoFormat"]) -> InlineKeyboardMarkup:
    """Create keyboard for video quality selection with dynamic options."""
    buttons = []
    row = []

    for fmt in formats:
        # Use video_{height} format for callback data
        row.append(
            InlineKeyboardButton(fmt.label, callback_data=f"{QUALITY_PREFIX}video_{fmt.height}")
        )
        if len(row) == 2:
            buttons.append(row)
            row = []

    # Add remaining button if odd number
    if row:
        buttons.append(row)

    # Add "Best" option
    buttons.append([InlineKeyboardButton("🌟 Best", callback_data=f"{QUALITY_PREFIX}video_best")])

    # Add navigation buttons
    buttons.append([
        InlineKeyboardButton("⬅️ Back", callback_data=f"{FORMAT_PREFIX}back"),
        InlineKeyboardButton("❌ Cancel", callback_data=f"{CANCEL_PREFIX}download"),
    ])

    return InlineKeyboardMarkup(buttons)


def dynamic_audio_quality_keyboard(formats: list["AudioFormat"]) -> InlineKeyboardMarkup:
    """Create keyboard for audio quality selection with dynamic options."""
    buttons = []
    row = []

    for fmt in formats:
        # Use audio_{bitrate} format for callback data
        row.append(
            InlineKeyboardButton(fmt.label, callback_data=f"{QUALITY_PREFIX}audio_{fmt.bitrate}")
        )
        if len(row) == 2:
            buttons.append(row)
            row = []

    # Add remaining button if odd number
    if row:
        buttons.append(row)

    # Add "Best" option
    buttons.append([InlineKeyboardButton("🌟 Best", callback_data=f"{QUALITY_PREFIX}audio_best")])

    # Add navigation buttons
    buttons.append([
        InlineKeyboardButton("⬅️ Back", callback_data=f"{FORMAT_PREFIX}back"),
        InlineKeyboardButton("❌ Cancel", callback_data=f"{CANCEL_PREFIX}download"),
    ])

    return InlineKeyboardMarkup(buttons)


def playlist_confirmation_keyboard(count: int) -> InlineKeyboardMarkup:
    """Create keyboard for playlist download confirmation."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                f"✅ Download all {count} items",
                callback_data=f"{CONFIRM_PREFIX}playlist"
            ),
        ],
        [
            InlineKeyboardButton(
                "📄 First item only",
                callback_data=f"{CONFIRM_PREFIX}single"
            ),
        ],
        [
            InlineKeyboardButton("❌ Cancel", callback_data=f"{CANCEL_PREFIX}download"),
        ]
    ])


def file_delete_keyboard(token: str) -> InlineKeyboardMarkup:
    """Create keyboard with delete button for large files."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🗑️ Delete from server", callback_data=f"{DELETE_PREFIX}{token}"),
        ]
    ])


def parse_callback_data(data: str) -> tuple[str, str]:
    """
    Parse callback data into prefix and action.

    Returns:
        Tuple of (prefix, action)
    """
    if ":" in data:
        prefix, action = data.split(":", 1)
        prefix = prefix + ":"
    else:
        prefix = ""
        action = data

    return prefix, action
