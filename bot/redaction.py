"""Keep secrets out of log output.

python-telegram-bot embeds the bot token in the message of `InvalidToken` and
logs that exception itself from its network retry loop. Redacting at our own
call sites therefore cannot work — the secret has to be stripped where records
are rendered, so that logging we do not control is covered too.
"""

import logging
from collections.abc import Iterable

REDACTED = "***REDACTED***"


def redact(text: str, secrets: Iterable[str | None]) -> str:
    """Replace every occurrence of each secret in ``text``."""
    for secret in secrets:
        # An empty needle matches between every character, and an unset env
        # var arrives here as "" — skipping falsy values keeps output intact.
        if secret:
            text = text.replace(secret, REDACTED)
    return text


class RedactingFormatter(logging.Formatter):
    """Formatter that strips secrets from the fully rendered record.

    Rendering first and redacting after is what catches secrets that only
    appear inside a traceback; a ``logging.Filter`` inspecting ``record.msg``
    would miss those entirely.

    Pass ``inner`` to reuse an already-configured formatter instead of
    rebuilding one, which preserves its format string and any subclass
    behaviour.
    """

    def __init__(
        self,
        fmt: str | None = None,
        datefmt: str | None = None,
        secrets: Iterable[str | None] = (),
        inner: logging.Formatter | None = None,
        **kwargs,
    ):
        super().__init__(fmt, datefmt, **kwargs)
        self._inner = inner
        self._secrets = [s for s in secrets if s]

    def format(self, record: logging.LogRecord) -> str:
        rendered = self._inner.format(record) if self._inner else super().format(record)
        return redact(rendered, self._secrets)


def install_secret_redaction(
    secrets: Iterable[str | None],
    logger: logging.Logger | None = None,
) -> None:
    """Retrofit every handler on ``logger`` (root by default) with redaction.

    Logging is configured at import time, but the token only becomes known once
    config loads, so handlers have to be wrapped after the fact.
    """
    real_secrets = [s for s in secrets if s]
    if not real_secrets:
        return

    target = logger if logger is not None else logging.getLogger()
    for handler in target.handlers:
        handler.setFormatter(
            RedactingFormatter(inner=handler.formatter, secrets=real_secrets)
        )
