import logging
from functools import wraps
from typing import Callable, Coroutine, Any

from telegram import Update
from telegram.ext import ContextTypes

from config import get_config
from bot.user_service import user_service
from bot.keyboards import request_access_keyboard, ACCESS_PREFIX, ADMIN_PREFIX

logger = logging.getLogger(__name__)


def whitelist_only(func: Callable[[Update, ContextTypes.DEFAULT_TYPE], Coroutine[Any, Any, Any]]):
    """Decorator to restrict bot access to whitelisted users only.

    Uses hybrid authorization:
    1. First checks env-based allowed_user_ids (always takes priority)
    2. Then checks DB for approved users
    3. Shows "Request Access" button for unauthorized users

    Note: ACCESS_PREFIX callbacks are always allowed (so users can request access).
    ADMIN_PREFIX callbacks require the user to be the admin.
    """

    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        config = get_config()
        user = update.effective_user

        if user is None:
            logger.warning("Received update without user information")
            return

        # Allow ACCESS_PREFIX callbacks from anyone (so they can request access)
        if update.callback_query:
            callback_data = update.callback_query.data or ""
            if callback_data.startswith(ACCESS_PREFIX):
                return await func(update, context)
            # ADMIN_PREFIX requires being the admin
            if callback_data.startswith(ADMIN_PREFIX):
                if config.admin_user_id and user.id == config.admin_user_id:
                    return await func(update, context)
                else:
                    await update.callback_query.answer("Only admin can do this", show_alert=True)
                    return

        # Check if user is allowed (env whitelist or DB approved)
        if user_service.is_user_allowed(user.id):
            return await func(update, context)

        # User is not allowed - check their status
        user_status = user_service.get_user_status(user.id)
        logger.warning(f"Unauthorized access attempt from user {user.id} (@{user.username}), status: {user_status}")

        if update.message:
            if user_status == "pending":
                await update.message.reply_text(
                    "⏳ Your access request is pending approval.\n"
                    "You'll be notified when an admin reviews your request."
                )
            elif user_status == "denied":
                await update.message.reply_text(
                    "⛔ Your access request was denied.\n"
                    "This is a private bot for personal use only."
                )
            else:
                # No existing request - show request access button
                await update.message.reply_text(
                    "⛔ You are not authorized to use this bot.\n"
                    "This is a private bot for personal use only.\n\n"
                    "You can request access from the admin:",
                    reply_markup=request_access_keyboard(),
                )
        return

    return wrapper
