"""Tests for secret redaction in log output.

Motivation: python-telegram-bot puts the full bot token inside the message of
`InvalidToken`, and logs that exception itself from its network retry loop. So
on an auth failure the token reaches every log sink without the application
ever touching it. Redaction has to happen at the formatter, not at the call
site, to cover logging we do not control.
"""

import io
import logging
import sys

from bot.redaction import REDACTED, RedactingFormatter, install_secret_redaction, redact

FAKE_TOKEN = "1234567890:AA" + "x" * 33


def _record_with_exception(exc: Exception) -> logging.LogRecord:
    """Build a log record carrying a real traceback, the way PTB logs one."""
    try:
        raise exc
    except type(exc):
        exc_info = sys.exc_info()

    return logging.LogRecord(
        name="telegram.ext",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg="Network Retry Loop (Bootstrap Initialize Application): Invalid token.",
        args=(),
        exc_info=exc_info,
    )


class TestRedact:
    def test_replaces_secret_in_plain_text(self):
        assert redact(f"token is {FAKE_TOKEN} ok", [FAKE_TOKEN]) == f"token is {REDACTED} ok"

    def test_leaves_text_without_secrets_untouched(self):
        assert redact("nothing to hide", [FAKE_TOKEN]) == "nothing to hide"

    def test_ignores_empty_secrets_so_output_is_not_corrupted(self):
        # An empty needle matches between every character; guarding against it
        # matters because an unset env var arrives here as "".
        assert redact("hello", ["", None]) == "hello"

    def test_redacts_every_occurrence(self):
        assert FAKE_TOKEN not in redact(f"{FAKE_TOKEN} and again {FAKE_TOKEN}", [FAKE_TOKEN])


class TestRedactingFormatter:
    def test_redacts_secret_from_the_log_message(self):
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="using %s now",
            args=(FAKE_TOKEN,),
            exc_info=None,
        )

        output = RedactingFormatter("%(message)s", secrets=[FAKE_TOKEN]).format(record)

        assert FAKE_TOKEN not in output
        assert REDACTED in output

    def test_redacts_secret_that_appears_only_inside_a_traceback(self):
        # The actual leak path from the 2026-05-23 incident.
        record = _record_with_exception(
            ValueError(f"The token `{FAKE_TOKEN}` was rejected by the server.")
        )

        output = RedactingFormatter("%(message)s", secrets=[FAKE_TOKEN]).format(record)

        assert FAKE_TOKEN not in output
        assert REDACTED in output
        assert "Traceback" in output, "the traceback itself must still be readable"


class TestInstallSecretRedaction:
    def test_wraps_handlers_that_were_configured_before_the_secret_was_known(self):
        # Logging is set up at import time; the token only arrives once config
        # loads. Installation therefore has to retrofit existing handlers.
        logger = logging.getLogger("test_install_redaction")
        logger.handlers.clear()
        logger.propagate = False
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)

        install_secret_redaction([FAKE_TOKEN], logger=logger)
        logger.error("leaking %s here", FAKE_TOKEN)

        assert FAKE_TOKEN not in stream.getvalue()
        assert REDACTED in stream.getvalue()

    def test_preserves_the_original_log_format(self):
        logger = logging.getLogger("test_install_redaction_format")
        logger.handlers.clear()
        logger.propagate = False
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(logging.Formatter("PREFIX %(levelname)s %(message)s"))
        logger.addHandler(handler)

        install_secret_redaction([FAKE_TOKEN], logger=logger)
        logger.error("boom")

        assert stream.getvalue().strip() == "PREFIX ERROR boom"
