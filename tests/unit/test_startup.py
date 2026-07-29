"""Tests for how the bot reacts to a token Telegram refuses.

On 2026-05-23 the deployed token was revoked. `run_polling` raised
`InvalidToken`, nothing caught it, and the container exited 1 and was restarted
10823 times — each cycle writing a full traceback (including the token) to the
log. These tests pin the two properties that were missing: a readable fatal
error, and no token in it.
"""

import logging

import pytest
from telegram.error import InvalidToken

from bot.startup import EXIT_INVALID_TOKEN, run_bot

FAKE_TOKEN = "1234567890:AA" + "x" * 33


def _app_rejecting_token():
    """A stand-in Application whose polling fails the way PTB's does."""
    from unittest.mock import MagicMock

    app = MagicMock()
    app.run_polling.side_effect = InvalidToken(
        f"The token `{FAKE_TOKEN}` was rejected by the server."
    )
    return app


class TestRunBotWithRejectedToken:
    def test_exits_with_a_dedicated_configuration_error_code(self):
        with pytest.raises(SystemExit) as excinfo:
            run_bot(_app_rejecting_token())

        assert excinfo.value.code == EXIT_INVALID_TOKEN

    def test_does_not_echo_the_rejected_token_into_the_log(self, caplog):
        with caplog.at_level(logging.ERROR), pytest.raises(SystemExit):
            run_bot(_app_rejecting_token())

        assert FAKE_TOKEN not in caplog.text

    def test_explains_how_to_recover(self, caplog):
        with caplog.at_level(logging.ERROR), pytest.raises(SystemExit):
            run_bot(_app_rejecting_token())

        assert "BotFather" in caplog.text
        assert "TELEGRAM_BOT_TOKEN" in caplog.text

    def test_reports_the_failure_without_dumping_a_traceback(self, caplog):
        # A traceback here is pure noise: the cause is known and external.
        with caplog.at_level(logging.ERROR), pytest.raises(SystemExit):
            run_bot(_app_rejecting_token())

        assert "Traceback" not in caplog.text


class TestRunBotNormally:
    def test_starts_polling_for_messages_and_callbacks(self):
        from unittest.mock import MagicMock

        app = MagicMock()

        run_bot(app)

        app.run_polling.assert_called_once_with(
            allowed_updates=["message", "callback_query"]
        )

    def test_lets_unrelated_failures_propagate(self):
        from unittest.mock import MagicMock

        app = MagicMock()
        app.run_polling.side_effect = RuntimeError("network down")

        # Only an invalid token is fatal-and-known; everything else must keep
        # its traceback so it can be diagnosed.
        with pytest.raises(RuntimeError):
            run_bot(app)
