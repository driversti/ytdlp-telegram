import logging
from functools import wraps
from typing import Callable, Coroutine, Any

from telegram import Update
from telegram.ext import ContextTypes

from config import get_config

logger = logging.getLogger(__name__)


def whitelist_only(func: Callable[[Update, ContextTypes.DEFAULT_TYPE], Coroutine[Any, Any, Any]]):
    """Decorator to restrict bot access to whitelisted users only."""

    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        config = get_config()
        user = update.effective_user

        if user is None:
            logger.warning("Received update without user information")
            return

        if user.id not in config.allowed_user_ids:
            logger.warning(f"Unauthorized access attempt from user {user.id} (@{user.username})")
            if update.message:
                await update.message.reply_text(
                    "⛔ You are not authorized to use this bot.\n"
                    "This is a private bot for personal use only."
                )
            return

        return await func(update, context)

    return wrapper
