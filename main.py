#!/usr/bin/env python3
"""
ytdlp-telegram bot - Personal media downloader bot using yt-dlp.

This bot downloads media from YouTube, Instagram, Twitter, Facebook,
and 1000+ other sites supported by yt-dlp.
"""

import logging
import sys

from telegram.ext import Application

from config import get_config
from bot.handlers import register_handlers
from bot.storage import ensure_directories_exist

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

# Reduce noise from httpx
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


def main():
    """Main entry point."""
    try:
        config = get_config()
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)

    # Ensure download directories exist
    ensure_directories_exist()

    logger.info("Starting ytdlp-telegram bot...")
    logger.info(f"Allowed users: {config.allowed_user_ids}")
    logger.info(f"Download path: {config.download_path}")
    logger.info(f"Ollama URL: {config.ollama_url}")
    logger.info(f"Ollama model: {config.ollama_model}")

    # Create application
    app = Application.builder().token(config.telegram_bot_token).build()

    # Register handlers
    register_handlers(app)

    # Start the bot
    logger.info("Bot is running. Press Ctrl+C to stop.")
    app.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()
