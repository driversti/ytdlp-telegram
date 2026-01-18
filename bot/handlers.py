import asyncio
import logging
from pathlib import Path
from typing import Optional

from telegram import Update, InputFile
from telegram.ext import (
    ContextTypes,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    Application,
)

from bot.middleware import whitelist_only
from bot.keyboards import (
    format_selection_keyboard,
    audio_quality_keyboard,
    video_quality_keyboard,
    playlist_confirmation_keyboard,
    file_delete_keyboard,
    parse_callback_data,
    FORMAT_PREFIX,
    QUALITY_PREFIX,
    CONFIRM_PREFIX,
    CANCEL_PREFIX,
    DELETE_PREFIX,
)
from bot.downloader import (
    Downloader,
    DownloadQuality,
    DownloadTask,
    download_queue,
    extract_urls,
)
from bot.storage import is_file_within_limit, get_file_size_mb, cleanup_file
from bot.file_server_client import file_server_client
from bot.llm_service import llm_service
from config import get_config

logger = logging.getLogger(__name__)

# Store active downloads by message_id
active_downloads: dict[int, dict] = {}


@whitelist_only
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    await update.message.reply_text(
        "👋 Welcome to the Media Downloader Bot!\n\n"
        "Send me a URL from:\n"
        "• YouTube\n"
        "• Instagram\n"
        "• Twitter/X\n"
        "• Facebook\n"
        "• TikTok\n"
        "• And 1000+ other sites!\n\n"
        "You can also use natural language:\n"
        "• \"download audio from <url>\"\n"
        "• \"grab this video <url>\"\n\n"
        "Commands:\n"
        "/help - Show this help message\n"
        "/status - Check queue status"
    )


@whitelist_only
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    await update.message.reply_text(
        "📖 *How to use this bot:*\n\n"
        "*1. Send a URL*\n"
        "Just paste any supported URL and I'll ask you to choose format and quality.\n\n"
        "*2. Natural Language*\n"
        "You can say things like:\n"
        "• \"download the audio from youtube.com/...\"\n"
        "• \"get this video in best quality\"\n\n"
        "*3. Quality Options*\n"
        "🎵 Audio: 128kbps, 192kbps, 320kbps, Best\n"
        "🎬 Video: 480p, 720p, 1080p, Best\n\n"
        "*4. File Limits*\n"
        "Files up to 50MB can be sent directly in Telegram.\n"
        "Larger files are saved to the server.\n\n"
        "*Supported Platforms:*\n"
        "YouTube, Instagram, Twitter/X, Facebook, TikTok, Vimeo, Reddit, Twitch, and 1000+ more!",
        parse_mode="Markdown"
    )


@whitelist_only
async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /status command."""
    queue_size = len(download_queue._queue)
    current = "Yes" if download_queue._current_task else "No"

    await update.message.reply_text(
        f"📊 *Queue Status*\n\n"
        f"Currently downloading: {current}\n"
        f"Items in queue: {queue_size}",
        parse_mode="Markdown"
    )


@whitelist_only
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming text messages."""
    message = update.message
    text = message.text

    if not text:
        return

    # Try to parse intent using LLM or heuristics
    intent = await llm_service.parse_intent(text)

    if not intent.urls:
        # No URLs found
        if intent.is_download_request:
            await message.reply_text(
                "🔗 I didn't find any URL in your message.\n"
                "Please include a valid link to download."
            )
        else:
            await message.reply_text(
                "👋 Send me a URL to download media, or use /help for more info."
            )
        return

    # Use the first URL and store it in user_data
    url = intent.urls[0]
    context.user_data['pending_url'] = url

    # If user explicitly requested audio or video, skip format selection
    if intent.wants_audio and not intent.wants_video:
        await show_audio_quality(message)
    elif intent.wants_video and not intent.wants_audio:
        await show_video_quality(message)
    else:
        # Show format selection
        await message.reply_text(
            "🎯 *Choose format:*",
            reply_markup=format_selection_keyboard(),
            parse_mode="Markdown"
        )


async def show_audio_quality(message):
    """Show audio quality selection."""
    await message.reply_text(
        "🎵 *Choose audio quality:*",
        reply_markup=audio_quality_keyboard(),
        parse_mode="Markdown"
    )


async def show_video_quality(message):
    """Show video quality selection."""
    await message.reply_text(
        "🎬 *Choose video quality:*",
        reply_markup=video_quality_keyboard(),
        parse_mode="Markdown"
    )


@whitelist_only
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline keyboard callbacks."""
    query = update.callback_query
    await query.answer()

    prefix, action = parse_callback_data(query.data)

    # Handle callbacks that don't need pending_url first
    if prefix == CANCEL_PREFIX:
        context.user_data.pop('pending_url', None)
        await query.edit_message_text("❌ Download cancelled.")
        return

    if prefix == DELETE_PREFIX:
        token = action
        success = await file_server_client.delete_file(token)
        if success:
            await query.edit_message_text(
                query.message.text + "\n\n🗑️ File deleted from server."
            )
        else:
            await query.answer("Failed to delete file", show_alert=True)
        return

    # Now check for pending_url (only needed for format/quality/confirm)
    url = context.user_data.get('pending_url')
    if not url:
        await query.edit_message_text("❌ Session expired. Please send the URL again.")
        return

    if prefix == FORMAT_PREFIX:
        if action == "audio":
            await query.edit_message_text(
                "🎵 *Choose audio quality:*",
                reply_markup=audio_quality_keyboard(),
                parse_mode="Markdown"
            )
        elif action == "video":
            await query.edit_message_text(
                "🎬 *Choose video quality:*",
                reply_markup=video_quality_keyboard(),
                parse_mode="Markdown"
            )
        elif action == "back":
            await query.edit_message_text(
                "🎯 *Choose format:*",
                reply_markup=format_selection_keyboard(),
                parse_mode="Markdown"
            )

    elif prefix == QUALITY_PREFIX:
        quality_map = {
            "audio_128": DownloadQuality.AUDIO_128,
            "audio_192": DownloadQuality.AUDIO_192,
            "audio_320": DownloadQuality.AUDIO_320,
            "audio_best": DownloadQuality.AUDIO_BEST,
            "video_480": DownloadQuality.VIDEO_480,
            "video_720": DownloadQuality.VIDEO_720,
            "video_1080": DownloadQuality.VIDEO_1080,
            "video_best": DownloadQuality.VIDEO_BEST,
        }

        quality = quality_map.get(action)
        if quality:
            # Clear pending URL after starting download
            context.user_data.pop('pending_url', None)
            await start_download(query, url, quality, context)

    elif prefix == CONFIRM_PREFIX:
        if action == "playlist":
            # TODO: Implement playlist download
            await query.edit_message_text("📋 Playlist download not yet implemented.")
        elif action == "single":
            await query.edit_message_text(
                "🎯 *Choose format:*",
                reply_markup=format_selection_keyboard(),
                parse_mode="Markdown"
            )


async def start_download(query, url: str, quality: DownloadQuality, context: ContextTypes.DEFAULT_TYPE):
    """Start a download task."""
    chat_id = query.message.chat_id
    message_id = query.message.message_id

    # Update message to show queuing
    await query.edit_message_text("⏳ Adding to queue...")

    # Create progress callback
    async def progress_callback(percent: float, status: str):
        try:
            if status == "downloading":
                progress_bar = create_progress_bar(percent)
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=f"⬇️ Downloading...\n{progress_bar} {percent:.0f}%"
                )
            elif status == "processing":
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text="🔄 Processing..."
                )
            elif status.startswith("complete|"):
                # Split from right first to get filesize (last field, no pipes)
                # Then split remaining from left to handle titles containing |
                main_part, filesize_str = status.rsplit("|", maxsplit=1)
                parts = main_part.split("|", maxsplit=2)
                filepath = Path(parts[1])
                title = parts[2]
                filesize_mb = float(filesize_str)

                await handle_download_complete(
                    context.bot, chat_id, message_id, filepath, title, filesize_mb
                )
            elif status.startswith("error|"):
                error_msg = status.split("|", 1)[1]
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=f"❌ Download failed:\n{error_msg}"
                )
        except Exception as e:
            logger.exception(f"Error in progress callback: {e}")

    # Create and queue task
    task = DownloadTask(
        url=url[:50],
        quality=quality,
        chat_id=chat_id,
        message_id=message_id,
        progress_callback=progress_callback,
        original_url=url,
    )

    position = await download_queue.add(task)

    if position > 0:
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=f"📋 Added to queue (position #{position})"
        )


async def handle_download_complete(bot, chat_id: int, message_id: int, filepath: Path, title: str, filesize_mb: float):
    """Handle completed download - send file or notify about large file."""
    config = get_config()

    if is_file_within_limit(filepath):
        # Send file to user
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text="📤 Uploading..."
        )

        try:
            with open(filepath, "rb") as f:
                if filepath.suffix.lower() == ".mp3":
                    await bot.send_audio(
                        chat_id=chat_id,
                        audio=InputFile(f, filename=filepath.name),
                        title=title,
                        caption=f"🎵 {title}"
                    )
                else:
                    await bot.send_video(
                        chat_id=chat_id,
                        video=InputFile(f, filename=filepath.name),
                        caption=f"🎬 {title}",
                        supports_streaming=True
                    )

            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=f"✅ Downloaded: {title}\n📁 Size: {filesize_mb:.1f} MB"
            )

        except Exception as e:
            logger.error(f"Failed to send file: {e}")
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=f"✅ Downloaded but couldn't send:\n{title}\n📁 Size: {filesize_mb:.1f} MB\n📍 Saved to: {filepath}"
            )
    else:
        # File too large for Telegram - generate download link
        download_link = await file_server_client.generate_download_link(str(filepath))

        if download_link:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=(
                    f"✅ Downloaded: {title}\n"
                    f"📁 Size: {filesize_mb:.1f} MB\n\n"
                    f"⚠️ File exceeds {config.max_file_size_mb}MB Telegram limit.\n\n"
                    f"📥 Download: {download_link.url}"
                ),
                reply_markup=file_delete_keyboard(download_link.token),
            )
        else:
            # Fallback if file server is unavailable
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=(
                    f"✅ Downloaded: {title}\n"
                    f"📁 Size: {filesize_mb:.1f} MB\n\n"
                    f"⚠️ File exceeds {config.max_file_size_mb}MB limit.\n"
                    f"📍 Saved to: {filepath}"
                )
            )


def create_progress_bar(percent: float, length: int = 10) -> str:
    """Create a text progress bar."""
    filled = int(length * percent / 100)
    empty = length - filled
    return "▓" * filled + "░" * empty


def register_handlers(app: Application):
    """Register all handlers with the application."""
    # Commands
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("status", status_command))

    # Callback queries (inline keyboards)
    app.add_handler(CallbackQueryHandler(handle_callback))

    # Text messages
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Handlers registered")
