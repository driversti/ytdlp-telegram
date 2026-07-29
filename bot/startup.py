"""Startup helpers for the bot process."""

import logging
import sys

from telegram.error import InvalidToken

logger = logging.getLogger(__name__)

# sysexits.h EX_CONFIG — the configuration is wrong, so retrying cannot help.
EXIT_INVALID_TOKEN = 78

ALLOWED_UPDATES = ["message", "callback_query"]


def run_bot(app) -> None:
    """Run polling, turning a rejected token into one readable fatal error.

    An invalid token is the one startup failure that no amount of restarting
    will fix, so it is reported as a single actionable line rather than being
    allowed to crash the process with a traceback.
    """
    try:
        app.run_polling(allowed_updates=ALLOWED_UPDATES)
    except InvalidToken:
        # The exception is deliberately neither re-raised nor passed to
        # logger.exception: its message quotes the token verbatim, and a
        # traceback adds nothing to a cause that is already known.
        logger.error(
            "Telegram rejected TELEGRAM_BOT_TOKEN (HTTP 401 Unauthorized). "
            "The token was most likely revoked in @BotFather. Issue a new one "
            "(/mybots -> pick the bot -> API Token), update TELEGRAM_BOT_TOKEN "
            "and start again. Restarting with the same token will not help."
        )
        sys.exit(EXIT_INVALID_TOKEN)
