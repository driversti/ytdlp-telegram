# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A personal Telegram bot that downloads media from YouTube, Instagram, Twitter/X, Facebook, TikTok, and 1000+ other platforms using yt-dlp. Features natural language processing via Ollama for intelligent intent parsing.

## Development Commands

```bash
# Local development setup
python -m venv venv
source venv/bin/activate
pip install -r requirements-dev.txt  # includes runtime + test + lint deps
python main.py

# Run tests
uv run python -m pytest tests/ -v
uv run python -m pytest tests/unit/test_downloader.py -v          # single file
uv run python -m pytest tests/unit/test_downloader.py::test_name  # single test

# Coverage
uv run python -m pytest tests/ --cov=bot --cov-report=term-missing

# Lint
ruff check .
ruff format .

# Docker
docker compose up -d
docker compose logs -f bot

# Build and push multi-arch bot image (reads version from config.py)
./release.sh  # NOTE: only builds the bot image, not the file-server
```

## Versioning

- **Bot version**: `__version__` in `config.py` (single source of truth). `release.sh` reads it automatically.
- **File server version**: Independent, set in `FastAPI()` constructor in `file-server/main.py`
- Test deployments on production (Jetson): use `-testN` postfixes (e.g., `v1.2.0-test1`)

## Architecture

### Core Components

- **`main.py`** — Entry point; dual logging (console + rotating file at `{download_path}/bot.log`, 5MB/3 backups); silences httpx at WARNING
- **`config.py`** — Frozen dataclass loaded from env vars; global singleton via `get_config()`
- **`bot/handlers.py`** — Telegram message/command/callback handlers; orchestrates download flow
- **`bot/downloader.py`** — yt-dlp wrapper with sequential `DownloadQueue`; dedicated `ThreadPoolExecutor(max_workers=4)` for downloads
- **`bot/llm_service.py`** — Ollama integration for intent parsing with heuristics fallback (5-min TTL cache)
- **`bot/storage.py`** — Platform detection (regex-based), file management, URL validation
- **`bot/keyboards.py`** — Inline keyboard builders for format/quality selection; `parse_callback_data()` splits on first `:` only
- **`bot/middleware.py`** — `@whitelist_only` decorator for hybrid user authentication
- **`bot/file_server_client.py`** — HTTP client for file server API (large file links)
- **`bot/stats_service.py`** — SQLite-based download history and statistics (`.stats.db`)
- **`bot/user_service.py`** — SQLite-based user management (`.users.db`)

### File Server (`file-server/`)

FastAPI service for serving large downloads (>50MB), admin UI, and live log viewer:
- **`main.py`** — FastAPI app with Jinja2 templates, session auth (itsdangerous), admin routes
- **`services/token_service.py`** — UUID token generation, JSON file storage (`.tokens.json`)
- **`services/file_service.py`** — File listing, deletion, metadata; path traversal protection
- **`services/user_service.py`** — User database access for admin UI (shares `.users.db` with bot)
- **`services/log_service.py`** — Reads and parses the bot's `bot.log` file; powers `/logs` and `/api/logs` endpoints
- **`services/telegram_service.py`** — Sends Telegram notifications directly (approval/denial from web admin, bypassing the bot process)

### Data Flow

```
User message → Whitelist check → Intent parsing (LLM/heuristics)
→ Format keyboard → Quality keyboard → DownloadTask created
→ Queue processing → yt-dlp execution (in dedicated thread pool)
  → File ≤50MB: Send via Telegram
  → File >50MB: Generate token → Send download link + delete button
                         ↓
                  File Server (FastAPI)
```

### Progress Status Protocol

The downloader communicates progress to handlers via string-encoded pipe-delimited status messages through `progress_callback(percent, status_string)`:

| Status | Format | Example |
|--------|--------|---------|
| Downloading | `"downloading"` | — |
| Post-processing | `"processing"` | — |
| Complete | `"complete\|{filepath}\|{title}\|{filesize_mb}"` | `complete\|/downloads/video.mp4\|My Video\|42.5` |
| Error | `"error\|{message}"` | `error\|Video unavailable` |

**Parsing in handlers.py**: Uses `rsplit("|", 1)` first to extract filesize (rightmost), then `split("|", 2)` for filepath and title — because titles may contain `|`.

### Callback Data Format

Inline keyboard callbacks use `"prefix:action"` (e.g., `quality:video_best`):
- Prefixes: `format:`, `quality:`, `confirm:`, `cancel:`, `delete:`, `access:`, `admin:`
- URLs stored in `context.user_data['pending_url']` to avoid Telegram's 64-byte callback limit
- `parse_callback_data()` uses `split(":", 1)` — important for nested colons like `admin:approve:{telegram_id}`
- **Important:** Callbacks that don't need `pending_url` (like `DELETE_PREFIX`, `CANCEL_PREFIX`, `ACCESS_PREFIX`, `ADMIN_PREFIX`) must be handled BEFORE the URL check in `handle_callback()`

### Logging Architecture

- **Bot** writes to `{download_path}/bot.log` via `RotatingFileHandler` (5MB, 3 backups) + console
- **File server** reads that same `bot.log` to serve it via `/logs` (web UI) and `/api/logs` (JSON)
- `httpx` logger silenced to WARNING in `main.py`

## Code Conventions

- **Global singletons** at module bottom: `llm_service = LLMService()`, `download_queue = DownloadQueue()`, etc.
- **Type hints**: Python 3.10+ union syntax (`int | None`, not `Optional[int]`)
- **Dataclasses**: `@dataclass(frozen=True)` for config; plain `@dataclass` for domain objects
- **DB deserialization**: `@classmethod from_row(cls, row: tuple)` pattern
- **Error handling**: `logger.exception()` (not `logger.error()`) to capture full tracebacks
- **Async patterns**: `loop.run_in_executor(_download_executor, fn)` for downloads; `loop.call_soon_threadsafe(lambda: asyncio.create_task(...))` for thread→async bridging

## Configuration

Required environment variables:
- `TELEGRAM_BOT_TOKEN` — From @BotFather
- `ALLOWED_USER_IDS` — Comma-separated user IDs (env-based whitelist, always allowed)

Optional (with defaults in `config.py`):
- `ADMIN_USER_ID` — Telegram ID to receive access request notifications
- `ADMIN_PASSWORD` — Password for web admin UI at `/admin`
- `OLLAMA_URL` (default: `http://localhost:11434`)
- `OLLAMA_MODEL` (default: `llama3.2:3b`)
- `DOWNLOAD_PATH` (default: `/downloads`)
- `MAX_FILE_SIZE_MB` (default: `50`)
- `FILE_SERVER_URL` (default: `http://localhost:8080`) — Internal URL for bot→server
- `FILE_SERVER_PUBLIC_URL` (default: `http://localhost:8080`) — Public URL for download links
- `FILE_SERVER_PORT` (default: `8080`)
- `DOWNLOAD_TIMEOUT` (default: `1800`) — 30 minutes
- `FORMAT_DETECTION_TIMEOUT` (default: `30`)
- `LLM_TIMEOUT` (default: `30`)

## Docker Setup

- Bot: `python:3.11-slim` with FFmpeg, `network_mode: host` for local Ollama access
- File server: `python:3.11-slim`, port `8080`
- Companion: `bgutil-ytdlp-pot-provider` for YouTube PO Token support (port `4416`)
- Multi-arch builds: `linux/amd64`, `linux/arm64`
- Shared volume: `./downloads:/downloads` (bot and file-server both access it)

## Testing

- **Framework**: pytest with `pytest-asyncio` (auto mode), `pytest-mock`, `respx` (httpx mocking)
- **Config**: `pytest.ini` sets `asyncio_mode = auto`, `addopts = -v --tb=short`
- **Fixtures**: `tests/conftest.py` — `mock_config` patches global config; env vars set before imports
- **Structure**: `tests/unit/` has tests for downloader, keyboards, llm_service, storage

## User Management

Hybrid authorization:
1. **Environment whitelist** (`ALLOWED_USER_IDS`) — Always allowed, cannot be removed via UI
2. **Database users** (`.users.db`) — Managed via admin UI or Telegram approval flow

Access request flow: Unauthorized user → "Request Access" button → Admin gets Telegram notification → Approve/Deny → User notified

## Current Limitations

- Large playlist downloads (100+ items) may be slow due to sequential processing
- No scheduled downloads feature

## Troubleshooting

- Bot logs: `docker compose logs -f bot`
- File server logs: `docker compose logs -f file-server`
- Live logs in browser: `{FILE_SERVER_PUBLIC_URL}/logs`
- "Session expired" on callbacks → check handler ordering in `handle_callback()`
- YouTube `HTTP Error 403: Forbidden` → usually a broken POT token. `pot-server` is built from `pot-server/Dockerfile` because the upstream `brainicism/bgutil-ytdlp-pot-provider` image ships without `libexpat1`, which `canvas` needs for the integrity attestation. Without it, `generateTokenMinter` falls back to a degraded POT and YouTube rejects media URLs with 403.
