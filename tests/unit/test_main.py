"""Test that startup wires redaction in before anything can log the token.

Ordering is the whole point here: installing redaction after the bot starts
would be useless, and that mistake is invisible in the unit tests for the
redaction helpers themselves.
"""

import io
import logging

import main as main_module
from bot.redaction import REDACTED
from config import Config

FAKE_TOKEN = "1234567890:AA" + "x" * 33


class _FakeApplication:
    """Minimal stand-in for telegram.ext.Application's builder chain."""

    @classmethod
    def builder(cls):
        return cls()

    def token(self, _token):
        return self

    def build(self):
        return object()


def _config(download_path: str) -> Config:
    return Config(
        telegram_bot_token=FAKE_TOKEN,
        allowed_user_ids={1},
        admin_user_id=None,
        ollama_url="http://localhost:11434",
        ollama_model="llama3.2:3b",
        download_path=download_path,
        max_file_size_mb=50,
        file_server_url="http://localhost:8080",
        file_server_public_url="http://localhost:8080",
        download_timeout=1800,
        format_detection_timeout=30,
        llm_timeout=30,
    )


def test_token_is_already_redacted_by_the_time_the_bot_starts(monkeypatch, tmp_path):
    captured = io.StringIO()
    handler = logging.StreamHandler(captured)
    handler.setFormatter(logging.Formatter("%(message)s"))
    root = logging.getLogger()
    root.addHandler(handler)
    original_formatters = [(h, h.formatter) for h in root.handlers]

    def leak_the_token_the_way_ptb_does(_app):
        logging.getLogger("telegram.ext").error(
            "The token `%s` was rejected by the server.", FAKE_TOKEN
        )

    try:
        monkeypatch.setattr(main_module, "get_config", lambda: _config(str(tmp_path)))
        monkeypatch.setattr(main_module, "ensure_directories_exist", lambda: None)
        monkeypatch.setattr(
            main_module, "setup_file_logging", lambda path: tmp_path / "bot.log"
        )
        monkeypatch.setattr(main_module, "register_handlers", lambda app: None)
        monkeypatch.setattr(main_module, "Application", _FakeApplication)
        monkeypatch.setattr(main_module, "run_bot", leak_the_token_the_way_ptb_does)

        main_module.main()

        assert FAKE_TOKEN not in captured.getvalue()
        assert REDACTED in captured.getvalue()
    finally:
        root.removeHandler(handler)
        for original_handler, formatter in original_formatters:
            original_handler.setFormatter(formatter)
