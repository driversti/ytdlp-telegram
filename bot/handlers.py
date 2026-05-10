import logging
from pathlib import Path

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
    dynamic_video_quality_keyboard,
    dynamic_audio_quality_keyboard,
    playlist_confirmation_keyboard,
    file_delete_keyboard,
    admin_access_decision_keyboard,
    parse_callback_data,
    FORMAT_PREFIX,
    QUALITY_PREFIX,
    CONFIRM_PREFIX,
    CANCEL_PREFIX,
    DELETE_PREFIX,
    ACCESS_PREFIX,
    ADMIN_PREFIX,
)
from bot.downloader import (
    Downloader,
    DownloadQuality,
    DynamicQuality,
    DownloadTask,
    download_queue,
)
from bot.storage import is_file_within_limit, detect_platform
from bot.file_server_client import file_server_client
from bot.llm_service import llm_service
from bot.stats_service import stats_service
from bot.user_service import user_service
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
        "/status - Check queue status\n"
        "/stats - View download statistics"
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
    active, queued = await download_queue.get_queue_status()

    await update.message.reply_text(
        f"📊 *Queue Status*\n\n"
        f"Active downloads: {active}\n"
        f"Items in queue: {queued}",
        parse_mode="Markdown"
    )


@whitelist_only
async def health_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /health command - show system health status."""
    import shutil
    from pathlib import Path

    config = get_config()
    text = "🏥 *System Health*\n\n"

    # Queue status
    active, queued = await download_queue.get_queue_status()
    text += "*Download Queue:*\n"
    text += f"• Active: {active}\n"
    text += f"• Queued: {queued}\n\n"

    # Disk space
    download_path = Path(config.download_path)
    if download_path.exists():
        total, used, free = shutil.disk_usage(download_path)
        free_gb = free / (1024**3)
        used_gb = used / (1024**3)
        total_gb = total / (1024**3)
        usage_percent = (used / total) * 100

        text += "*Disk Space:*\n"
        text += f"• Free: {free_gb:.1f} GB\n"
        text += f"• Used: {used_gb:.1f} GB ({usage_percent:.0f}%)\n"
        text += f"• Total: {total_gb:.1f} GB\n\n"
    else:
        text += "*Disk Space:* ⚠️ Download path not found\n\n"

    # Ollama status
    text += "*Ollama LLM:*\n"
    try:
        ollama_available = await llm_service.is_available()
        if ollama_available:
            text += "• Status: ✅ Connected\n"
            text += f"• Model: {config.ollama_model}\n\n"
        else:
            text += "• Status: ❌ Disconnected\n\n"
    except Exception:
        text += "• Status: ❌ Error checking\n\n"

    # File server status
    text += "*File Server:*\n"
    try:
        import httpx
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{config.file_server_url}/health")
            if response.status_code == 200:
                text += "• Status: ✅ Connected\n"
            else:
                text += f"• Status: ⚠️ Error ({response.status_code})\n"
    except Exception:
        text += "• Status: ❌ Disconnected\n"

    await update.message.reply_text(text, parse_mode="Markdown")


@whitelist_only
async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /stats command - show download statistics."""
    user_id = update.effective_user.id
    overall = stats_service.get_overall_stats()
    user_stats = stats_service.get_user_stats(user_id)

    text = "📈 *Download Statistics*\n\n"

    # Overall stats
    text += "*Overall:*\n"
    text += f"• Total downloads: {overall.total_downloads}\n"
    text += f"• Total size: {overall.total_size_mb:.1f} MB\n"
    text += f"• This month: {overall.downloads_this_month} downloads ({overall.size_this_month_mb:.1f} MB)\n\n"

    # Platform breakdown
    if overall.platforms:
        text += "*By platform:*\n"
        for platform, count in list(overall.platforms.items())[:5]:
            text += f"• {platform.capitalize()}: {count}\n"
        text += "\n"

    # User stats
    if user_stats:
        text += "*Your stats:*\n"
        text += f"• Downloads: {user_stats.total_downloads}\n"
        text += f"• Total size: {user_stats.total_size_mb:.1f} MB\n"
        text += f"• Audio: {user_stats.audio_downloads} | Video: {user_stats.video_downloads}\n"
        text += f"• Favorite platform: {user_stats.favorite_platform.capitalize()}\n"
    else:
        text += "_You haven't downloaded anything yet!_"

    await update.message.reply_text(text, parse_mode="Markdown")


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

    # Check if it's a playlist
    status_msg = await message.reply_text("⏳ Checking URL...")
    downloader = Downloader()
    media_info = await downloader.get_info(url)

    if media_info and media_info.is_playlist and media_info.playlist_count > 1:
        # It's a playlist - ask for confirmation
        context.user_data['pending_playlist_count'] = media_info.playlist_count
        await status_msg.edit_text(
            f"📋 *Playlist detected!*\n\n"
            f"*Title:* {media_info.title}\n"
            f"*Videos:* {media_info.playlist_count}\n\n"
            f"What would you like to do?",
            reply_markup=playlist_confirmation_keyboard(media_info.playlist_count),
            parse_mode="Markdown"
        )
        return

    # If user explicitly requested audio or video, skip format selection
    if intent.wants_audio and not intent.wants_video:
        await show_audio_quality(status_msg)
    elif intent.wants_video and not intent.wants_audio:
        await show_video_quality(status_msg)
    else:
        # Show format selection
        await status_msg.edit_text(
            "🎯 *Choose format:*",
            reply_markup=format_selection_keyboard(),
            parse_mode="Markdown"
        )


async def show_audio_quality(status_msg):
    """Show audio quality selection."""
    await status_msg.edit_text(
        "🎵 *Choose audio quality:*",
        reply_markup=audio_quality_keyboard(),
        parse_mode="Markdown"
    )


async def show_video_quality(status_msg):
    """Show video quality selection."""
    await status_msg.edit_text(
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
        context.user_data.pop('pending_formats', None)
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

    if prefix == ACCESS_PREFIX:
        await handle_access_callback(query, context, action)
        return

    if prefix == ADMIN_PREFIX:
        await handle_admin_callback(query, context, action)
        return

    # Now check for pending_url (only needed for format/quality/confirm)
    url = context.user_data.get('pending_url')
    if not url:
        await query.edit_message_text("❌ Session expired. Please send the URL again.")
        return

    if prefix == FORMAT_PREFIX:
        if action == "audio":
            await _handle_format_selection(query, context, url, is_audio=True)
        elif action == "video":
            await _handle_format_selection(query, context, url, is_audio=False)
        elif action == "back":
            context.user_data.pop('pending_formats', None)
            await query.edit_message_text(
                "🎯 *Choose format:*",
                reply_markup=format_selection_keyboard(),
                parse_mode="Markdown"
            )

    elif prefix == QUALITY_PREFIX:
        quality = _parse_quality_action(action)
        if quality:
            is_playlist = context.user_data.get('is_playlist_download', False)
            # Clear pending data after starting download
            context.user_data.pop('pending_url', None)
            context.user_data.pop('pending_formats', None)
            context.user_data.pop('is_playlist_download', None)
            context.user_data.pop('pending_playlist_count', None)

            if is_playlist:
                await start_playlist_download(query, url, quality, context)
            else:
                await start_download(query, url, quality, context)

    elif prefix == CONFIRM_PREFIX:
        if action == "playlist":
            # Store that this is a playlist download, then show format selection
            context.user_data['is_playlist_download'] = True
            await query.edit_message_text(
                "🎯 *Choose format for all videos:*",
                reply_markup=format_selection_keyboard(),
                parse_mode="Markdown"
            )
        elif action == "single":
            # User wants only the first item
            context.user_data['is_playlist_download'] = False
            await query.edit_message_text(
                "🎯 *Choose format:*",
                reply_markup=format_selection_keyboard(),
                parse_mode="Markdown"
            )


async def handle_access_callback(query, context: ContextTypes.DEFAULT_TYPE, action: str):
    """Handle access request callbacks."""
    config = get_config()
    user = query.from_user

    if action == "request":
        # Check if user already has a pending request
        existing_status = user_service.get_user_status(user.id)
        if existing_status == "pending":
            await query.edit_message_text(
                "⏳ You already have a pending access request.\n"
                "You'll be notified when an admin reviews your request."
            )
            return

        # Create access request
        created = user_service.create_access_request(
            telegram_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
        )

        if created:
            await query.edit_message_text(
                "✅ Access request submitted!\n\n"
                "You'll be notified when an admin reviews your request."
            )

            # Notify admin
            if config.admin_user_id:
                user_info = f"*User:* {user.first_name or ''} {user.last_name or ''}".strip()
                if user.username:
                    user_info += f" (@{user.username})"
                user_info += f"\n*ID:* `{user.id}`"

                try:
                    await context.bot.send_message(
                        chat_id=config.admin_user_id,
                        text=(
                            "🔔 *New Access Request*\n\n"
                            f"{user_info}\n\n"
                            "Review this request:"
                        ),
                        reply_markup=admin_access_decision_keyboard(user.id),
                        parse_mode="Markdown",
                    )
                except Exception:
                    logger.exception(f"Failed to notify admin about access request from {user.id}")
        else:
            await query.edit_message_text(
                "⚠️ You already have an access request on file.\n"
                "Please wait for admin review."
            )


async def handle_admin_callback(query, context: ContextTypes.DEFAULT_TYPE, action: str):
    """Handle admin decision callbacks (approve/deny)."""
    config = get_config()
    admin_user = query.from_user

    # Verify that the user clicking is the admin
    if admin_user.id != config.admin_user_id:
        await query.answer("You are not authorized to perform this action.", show_alert=True)
        return

    # Parse action: approve:{telegram_id} or deny:{telegram_id}
    parts = action.split(":", 1)
    if len(parts) != 2:
        await query.answer("Invalid action", show_alert=True)
        return

    decision, telegram_id_str = parts
    try:
        telegram_id = int(telegram_id_str)
    except ValueError:
        await query.answer("Invalid user ID", show_alert=True)
        return

    if decision == "approve":
        success = user_service.approve_user(telegram_id, admin_user.id)
        if success:
            await query.edit_message_text(
                query.message.text + "\n\n✅ *Approved* by you"
            , parse_mode="Markdown")

            # Notify the user
            try:
                await context.bot.send_message(
                    chat_id=telegram_id,
                    text=(
                        "🎉 *Access Granted!*\n\n"
                        "Your request has been approved. You can now use the bot.\n\n"
                        "Send me a URL to download media, or use /help for more info."
                    ),
                    parse_mode="Markdown",
                )
            except Exception:
                logger.exception(f"Failed to notify user {telegram_id} about approval")
        else:
            await query.answer("Failed to approve user", show_alert=True)

    elif decision == "deny":
        success = user_service.deny_user(telegram_id, admin_user.id)
        if success:
            await query.edit_message_text(
                query.message.text + "\n\n❌ *Denied* by you"
            , parse_mode="Markdown")

            # Notify the user
            try:
                await context.bot.send_message(
                    chat_id=telegram_id,
                    text=(
                        "⛔ *Access Denied*\n\n"
                        "Your access request was not approved.\n"
                        "This is a private bot for personal use only."
                    ),
                    parse_mode="Markdown",
                )
            except Exception:
                logger.exception(f"Failed to notify user {telegram_id} about denial")
        else:
            await query.answer("Failed to deny user", show_alert=True)


async def _handle_format_selection(query, context, url: str, is_audio: bool):
    """Handle audio/video format selection with dynamic quality detection."""
    format_type = "audio" if is_audio else "video"
    emoji = "🎵" if is_audio else "🎬"

    # Show waiting message
    await query.edit_message_text("⏳ Please wait, analyzing available qualities...")

    # Get available formats
    downloader = Downloader()
    formats_result = await downloader.get_available_formats(url)

    # Cache result for potential reuse
    context.user_data['pending_formats'] = formats_result

    # Check for errors or empty results
    if formats_result.error:
        logger.warning(f"Format detection failed for {url}: {formats_result.error}")
        await _show_fallback_keyboard(query, is_audio, emoji, formats_result.error)
        return

    if is_audio:
        if not formats_result.audio_formats:
            await _show_fallback_keyboard(query, is_audio, emoji, "No audio formats detected")
            return
        keyboard = dynamic_audio_quality_keyboard(formats_result.audio_formats)
    else:
        if not formats_result.video_formats:
            await _show_fallback_keyboard(query, is_audio, emoji, "No video formats detected")
            return
        keyboard = dynamic_video_quality_keyboard(formats_result.video_formats)

    await query.edit_message_text(
        f"{emoji} *Choose {format_type} quality:*",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )


async def _show_fallback_keyboard(query, is_audio: bool, emoji: str, error_reason: str):
    """Show fallback keyboard with default options when dynamic detection fails."""
    format_type = "audio" if is_audio else "video"
    keyboard = audio_quality_keyboard() if is_audio else video_quality_keyboard()

    await query.edit_message_text(
        f"{emoji} *Choose {format_type} quality:*\n"
        f"_Using default options ({error_reason})_",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )


def _parse_quality_action(action: str):
    """Parse quality action string into DownloadQuality or DynamicQuality."""
    # First check if it's a standard quality
    standard_qualities = {
        "audio_128": DownloadQuality.AUDIO_128,
        "audio_192": DownloadQuality.AUDIO_192,
        "audio_320": DownloadQuality.AUDIO_320,
        "audio_best": DownloadQuality.AUDIO_BEST,
        "video_480": DownloadQuality.VIDEO_480,
        "video_720": DownloadQuality.VIDEO_720,
        "video_1080": DownloadQuality.VIDEO_1080,
        "video_best": DownloadQuality.VIDEO_BEST,
    }

    if action in standard_qualities:
        return standard_qualities[action]

    # Try to parse as dynamic quality (e.g., video_1440, audio_256)
    if action.startswith("video_"):
        try:
            height = int(action.split("_")[1])
            return DynamicQuality(is_audio=False, value=height)
        except (ValueError, IndexError):
            pass
    elif action.startswith("audio_"):
        try:
            bitrate = int(action.split("_")[1])
            return DynamicQuality(is_audio=True, value=bitrate)
        except (ValueError, IndexError):
            pass

    return None


async def start_download(query, url: str, quality, context: ContextTypes.DEFAULT_TYPE):
    """Start a download task."""
    chat_id = query.message.chat_id
    message_id = query.message.message_id
    user_id = query.from_user.id

    # Determine format type and quality string
    is_audio = isinstance(quality, DynamicQuality) and quality.is_audio
    if not isinstance(quality, DynamicQuality):
        is_audio = quality.value.startswith("audio")
    format_type = "audio" if is_audio else "video"
    quality_str = str(quality.value) if hasattr(quality, "value") else str(quality)

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

                # Record download in stats
                platform = detect_platform(url)
                stats_service.record_download(
                    url=url,
                    platform=platform,
                    format_type=format_type,
                    quality=quality_str,
                    filesize_mb=filesize_mb,
                    title=title,
                    user_id=user_id,
                )

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
        except Exception:
            logger.exception("Error in progress callback")

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


async def start_playlist_download(query, url: str, quality, context: ContextTypes.DEFAULT_TYPE):
    """Start downloading all items in a playlist."""
    chat_id = query.message.chat_id
    message_id = query.message.message_id
    user_id = query.from_user.id

    # Determine format type and quality string
    is_audio = isinstance(quality, DynamicQuality) and quality.is_audio
    if not isinstance(quality, DynamicQuality):
        is_audio = quality.value.startswith("audio")
    format_type = "audio" if is_audio else "video"
    quality_str = str(quality.value) if hasattr(quality, "value") else str(quality)

    # Show extraction message
    await query.edit_message_text("⏳ Extracting playlist entries...")

    # Get playlist info
    downloader = Downloader()
    playlist_info = await downloader.get_playlist_info(url)

    if not playlist_info or not playlist_info.entries:
        await query.edit_message_text("❌ Could not extract playlist entries.")
        return

    total = playlist_info.count
    await query.edit_message_text(
        f"📋 *Downloading playlist: {playlist_info.title}*\n\n"
        f"Items: 0/{total} completed\n"
        f"Status: Starting...",
        parse_mode="Markdown"
    )

    # Download each entry sequentially
    completed = 0
    failed = 0
    results = []

    for entry in playlist_info.entries:
        # Update progress
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=(
                f"📋 *Downloading playlist: {playlist_info.title}*\n\n"
                f"Items: {completed}/{total} completed ({failed} failed)\n"
                f"Current: {entry.title[:50]}..."
            ),
            parse_mode="Markdown"
        )

        # Download this entry
        result = await downloader.download(url=entry.url, quality=quality)

        if result.success:
            completed += 1
            results.append((entry.title, result.filepath, result.filesize_mb))

            # Record download in stats
            platform = detect_platform(entry.url)
            stats_service.record_download(
                url=entry.url,
                platform=platform,
                format_type=format_type,
                quality=quality_str,
                filesize_mb=result.filesize_mb,
                title=entry.title,
                user_id=user_id,
            )
        else:
            failed += 1
            logger.warning(f"Failed to download playlist item {entry.index}: {result.error_message}")

    # Final summary
    summary_text = (
        f"📋 *Playlist complete: {playlist_info.title}*\n\n"
        f"✅ Downloaded: {completed}/{total}\n"
    )
    if failed > 0:
        summary_text += f"❌ Failed: {failed}\n"

    # List first few successful downloads
    if results:
        summary_text += "\n*Downloaded files:*\n"
        for i, (title, filepath, size_mb) in enumerate(results[:5]):
            summary_text += f"• {title[:40]}... ({size_mb:.1f} MB)\n"
        if len(results) > 5:
            summary_text += f"_... and {len(results) - 5} more_\n"

    await context.bot.edit_message_text(
        chat_id=chat_id,
        message_id=message_id,
        text=summary_text,
        parse_mode="Markdown"
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

        except (OSError, IOError):
            logger.exception(f"Failed to send file: {filepath}")
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
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("health", health_command))

    # Callback queries (inline keyboards)
    app.add_handler(CallbackQueryHandler(handle_callback))

    # Text messages
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Handlers registered")
