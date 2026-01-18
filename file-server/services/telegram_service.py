"""Telegram notification service for file server."""

import logging
from typing import Optional

import httpx

from config import config

logger = logging.getLogger(__name__)


class TelegramService:
    """Service for sending Telegram notifications."""

    def __init__(self):
        self.token = config.telegram_bot_token
        self.base_url = f"https://api.telegram.org/bot{self.token}" if self.token else None

    async def send_message(
        self,
        chat_id: int,
        text: str,
        parse_mode: str = "Markdown",
    ) -> bool:
        """Send a message to a Telegram user."""
        if not self.base_url:
            logger.warning("Telegram bot token not configured, skipping notification")
            return False

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.base_url}/sendMessage",
                    json={
                        "chat_id": chat_id,
                        "text": text,
                        "parse_mode": parse_mode,
                    },
                )
                if response.status_code == 200:
                    logger.info(f"Sent Telegram notification to user {chat_id}")
                    return True
                else:
                    logger.error(
                        f"Failed to send Telegram notification to {chat_id}: "
                        f"{response.status_code} - {response.text}"
                    )
                    return False
        except Exception:
            logger.exception(f"Error sending Telegram notification to {chat_id}")
            return False

    async def notify_user_approved(self, telegram_id: int) -> bool:
        """Notify a user that their access request was approved."""
        text = (
            "*Access Granted!*\n\n"
            "Your request has been approved. You can now use the bot.\n\n"
            "Send me a URL to download media, or use /help for more info."
        )
        return await self.send_message(telegram_id, text)

    async def notify_user_denied(self, telegram_id: int) -> bool:
        """Notify a user that their access request was denied."""
        text = (
            "*Access Denied*\n\n"
            "Your access request was not approved.\n"
            "This is a private bot for personal use only."
        )
        return await self.send_message(telegram_id, text)


# Global service instance
telegram_service = TelegramService()
