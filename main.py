#!/usr/bin/env python3
"""
ytdlp-telegram bot - Personal media downloader bot using yt-dlp.

This bot downloads media from YouTube, Instagram, Twitter, Facebook,
and 1000+ other sites supported by yt-dlp.
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from telegram.ext import Application

from config import get_config
from bot.handlers import register_handlers
from bot.storage import ensure_directories_exist

# Configure logging
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# Setup root logger
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)

# Console handler (for docker logs)
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter(LOG_FORMAT))
root_logger.addHandler(console_handler)


def setup_file_logging(download_path: str):
    """Setup file logging with rotation."""
    log_file = Path(download_path) / "bot.log"
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024,  # 5MB per file
        backupCount=3,  # Keep 3 backup files (~20MB total max)
        encoding="utf-8",
    )
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
    root_logger.addHandler(file_handler)
    return log_file


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

    # Setup file logging after directories exist
    log_file = setup_file_logging(config.download_path)
    logger.info(f"Log file: {log_file}")

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
