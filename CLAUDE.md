# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A personal Telegram bot that downloads media from YouTube, Instagram, Twitter/X, Facebook, TikTok, and 1000+ other platforms using yt-dlp. Features natural language processing via Ollama for intelligent intent parsing.

## Development Commands

```bash
# Local development setup
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python main.py

# Docker deployment
docker compose up -d
docker compose logs -f bot

# Build and push multi-arch image
./release.sh

# Version is single source of truth in config.py
# release.sh reads it automatically
```

## Versioning

- Version is defined in `config.py` (single source of truth)
- `release.sh` reads the version automatically

### Test Deployments on Production

When testing on the production server (Jetson), use `-testN` postfixes to distinguish test builds from stable releases:

- `v1.2.0` → stable production release
- `v1.2.0-test1` → first test deployment
- `v1.2.0-test2` → second test iteration (after fixes)
- etc.

This allows deploying test builds without incrementing the actual version number, making it easy to identify and roll back if needed.

## Architecture

### Core Components

- **`main.py`** - Entry point, initializes Telegram application and registers handlers
- **`config.py`** - Frozen dataclass loading from environment variables
- **`bot/handlers.py`** - Telegram message/command/callback handlers, orchestrates the download flow
- **`bot/downloader.py`** - yt-dlp wrapper with async concurrent download queue (semaphore-based)
- **`bot/llm_service.py`** - Ollama integration for intent parsing with heuristics fallback (5-min TTL cache)
- **`bot/storage.py`** - Platform detection (regex-based), file management, and URL validation
- **`bot/keyboards.py`** - Inline keyboard builders for format/quality selection
- **`bot/middleware.py`** - `@whitelist_only` decorator for hybrid user authentication
- **`bot/file_server_client.py`** - HTTP client for file server API (large file links)
- **`bot/stats_service.py`** - SQLite-based download history and statistics tracking
- **`bot/user_service.py`** - SQLite-based user management (access requests, approvals)

### File Server (`file-server/`)

FastAPI service for serving large downloads (>50MB) and admin UI:
- **`main.py`** - FastAPI app with Jinja2 templates, session auth, admin routes
- **`config.py`** - Environment config
- **`services/token_service.py`** - UUID token generation, JSON storage
- **`services/file_service.py`** - File listing, deletion, metadata
- **`services/user_service.py`** - User database access for admin UI

### Data Flow

```
User message → Whitelist check → Intent parsing (LLM/heuristics)
→ Format keyboard → Quality keyboard → DownloadTask created
→ Queue processing → yt-dlp execution
  → File ≤50MB: Send via Telegram
  → File >50MB: Generate token → Send download link + delete button
                         ↓
                  File Server (FastAPI)
```

### Key Patterns

- **Async/await throughout** - All I/O operations are non-blocking
- **Executor pattern** - CPU-bound yt-dlp work runs in thread pool via `asyncio.get_event_loop().run_in_executor()`
- **Callback-based progress** - Progress updates via async callbacks every 5%
- **Graceful degradation** - LLM optional, falls back to keyword-based heuristics
- **Decorator auth** - `@whitelist_only` wraps handlers

### Callback Data Format

Inline keyboard callbacks use: `"prefix:action"` (e.g., `quality:video_best`)
- Prefixes: `format:`, `quality:`, `confirm:`, `cancel:`, `delete:`, `access:`, `admin:`
- URLs are stored in `context.user_data['pending_url']` to avoid Telegram's 64-byte callback limit
- Delete callbacks store the file token as action: `delete:{token}`
- Admin callbacks include target user: `admin:approve:{telegram_id}` or `admin:deny:{telegram_id}`
- **Important:** Callbacks that don't need `pending_url` (like `DELETE_PREFIX`, `CANCEL_PREFIX`, `ACCESS_PREFIX`, `ADMIN_PREFIX`) must be handled BEFORE the URL check in `handle_callback()`

## Configuration

Required environment variables:
- `TELEGRAM_BOT_TOKEN` - From @BotFather
- `ALLOWED_USER_IDS` - Comma-separated user IDs (env-based whitelist, always allowed)

Optional:
- `ADMIN_USER_ID` - Telegram ID to receive access request notifications
- `ADMIN_PASSWORD` - Password for web admin UI at `/admin`
- `OLLAMA_URL` (default: http://localhost:11434)
- `OLLAMA_MODEL` (default: llama3.2:3b)
- `DOWNLOAD_PATH` (default: /downloads)
- `MAX_FILE_SIZE_MB` (default: 50)
- `FILE_SERVER_URL` (default: http://localhost:8080) - Internal URL for bot→server
- `FILE_SERVER_PUBLIC_URL` (default: http://localhost:8080) - Public URL for download links
- `FILE_SERVER_PORT` (default: 8080) - Port for file server
- `MAX_CONCURRENT_DOWNLOADS` (default: 2) - Number of simultaneous downloads
- `DOWNLOAD_TIMEOUT` (default: 1800) - Download timeout in seconds (30 min)
- `FORMAT_DETECTION_TIMEOUT` (default: 30) - Format detection timeout in seconds
- `LLM_TIMEOUT` (default: 30) - LLM request timeout in seconds

## Docker Setup

- Uses `python:3.11-slim` with FFmpeg
- Network mode `host` for local Ollama access
- Companion services:
  - `bgutil-ytdlp-pot-provider` for YouTube PO Token support (port 4416)
  - `file-server` for large file downloads (port 8080)
- Multi-arch builds: `linux/amd64`, `linux/arm64`
- Registry: `registry.yurii.live`
- File server image: `registry.yurii.live/ytdlp-file-server:v0.1.1` (built separately in `file-server/`)

## Deployment

- **Host:** Nvidia Jetson Orin Nano (`192.168.10.10`)
- **SSH:** `ssh jetson@192.168.10.10`
- **Root folder:** `/home/jetson/docker/ytdlp-telegram`
- **Ollama:** Runs locally on the Jetson at `http://192.168.10.10:11434`

### Claude Code Skills

- `/deploy-test` - Build and deploy test containers to Jetson with auto-incrementing `-testN` version suffix. Builds multi-arch images, pushes to registry, updates docker-compose.yml on Jetson, and verifies deployment. Always asks for confirmation before deploying.

## Testing

```bash
# Run tests
uv run python -m pytest tests/ -v

# Run with coverage
uv run python -m pytest tests/ --cov=bot --cov-report=term-missing
```

Test structure:
- `tests/unit/` - Unit tests for core modules (storage, llm_service, downloader, keyboards)
- `tests/integration/` - Integration tests (to be added)
- `tests/file_server/` - File server tests (to be added)

## Bot Commands

- `/start` - Welcome message and quick help
- `/help` - Detailed usage instructions
- `/status` - View active downloads and queue status
- `/stats` - View download statistics and history
- `/health` - System health check (disk, Ollama, file server)

## User Management

The bot uses hybrid authorization:
1. **Environment whitelist** (`ALLOWED_USER_IDS`) - Always allowed, cannot be removed via UI
2. **Database users** (`.users.db`) - Can be added/removed via admin UI or Telegram

### Access Request Flow
```
Unauthorized user sends message → Bot shows "Request Access" button
User clicks button → Request saved to DB (status: pending)
                  → Admin receives Telegram notification with Approve/Deny buttons
Admin approves → User marked approved in DB → User receives welcome message
```

### Web Admin UI
- URL: `{FILE_SERVER_PUBLIC_URL}/admin`
- Password protected (set `ADMIN_PASSWORD`)
- Features:
  - View env users (cannot modify)
  - View/remove database users
  - View/approve/deny pending requests
  - Add user by Telegram ID

### Database
- Location: `{DOWNLOAD_PATH}/.users.db`
- Table: `users` with fields: telegram_id, username, first_name, last_name, status, source, timestamps

## Current Limitations

- Large playlist downloads (100+ items) may be slow due to sequential processing
- No scheduled downloads feature

## Troubleshooting

- Check bot logs: `docker compose logs -f bot`
- Check file server logs: `docker compose logs -f file-server`
- "Session expired" on callbacks → check handler ordering in `handle_callback()`
- Use `logger.exception()` instead of `logger.error()` to capture full tracebacks
