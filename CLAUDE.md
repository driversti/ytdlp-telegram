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

## Architecture

### Core Components

- **`main.py`** - Entry point, initializes Telegram application and registers handlers
- **`config.py`** - Frozen dataclass loading from environment variables
- **`bot/handlers.py`** - Telegram message/command/callback handlers, orchestrates the download flow
- **`bot/downloader.py`** - yt-dlp wrapper with async download queue (sequential FIFO processing)
- **`bot/llm_service.py`** - Ollama integration for intent parsing with heuristics fallback
- **`bot/storage.py`** - Platform detection (regex-based) and file management
- **`bot/keyboards.py`** - Inline keyboard builders for format/quality selection
- **`bot/middleware.py`** - `@whitelist_only` decorator for user authentication
- **`bot/file_server_client.py`** - HTTP client for file server API (large file links)

### File Server (`file-server/`)

FastAPI service for serving large downloads (>50MB):
- **`main.py`** - FastAPI app with Jinja2 templates
- **`config.py`** - Environment config
- **`services/token_service.py`** - UUID token generation, JSON storage
- **`services/file_service.py`** - File listing, deletion, metadata

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
- Prefixes: `format:`, `quality:`, `confirm:`, `cancel:`, `delete:`
- URLs are stored in `context.user_data['pending_url']` to avoid Telegram's 64-byte callback limit
- Delete callbacks store the file token as action: `delete:{token}`
- **Important:** Callbacks that don't need `pending_url` (like `DELETE_PREFIX`, `CANCEL_PREFIX`) must be handled BEFORE the URL check in `handle_callback()`

## Configuration

Required environment variables:
- `TELEGRAM_BOT_TOKEN` - From @BotFather
- `ALLOWED_USER_IDS` - Comma-separated user IDs

Optional:
- `OLLAMA_URL` (default: http://localhost:11434)
- `OLLAMA_MODEL` (default: llama3.2:3b)
- `DOWNLOAD_PATH` (default: /downloads)
- `MAX_FILE_SIZE_MB` (default: 50)
- `FILE_SERVER_URL` (default: http://localhost:8080) - Internal URL for bot→server
- `FILE_SERVER_PUBLIC_URL` (default: http://localhost:8080) - Public URL for download links
- `FILE_SERVER_PORT` (default: 8080) - Port for file server

## Docker Setup

- Uses `python:3.11-slim` with FFmpeg
- Network mode `host` for local Ollama access
- Companion services:
  - `bgutil-ytdlp-pot-provider` for YouTube PO Token support (port 4416)
  - `file-server` for large file downloads (port 8080)
- Multi-arch builds: `linux/amd64`, `linux/arm64`
- Registry: `registry.yurii.live`
- File server image: `registry.yurii.live/ytdlp-file-server:v0.1.0` (built separately in `file-server/`)

## Deployment

- **Host:** Nvidia Jetson Orin Nano (`192.168.10.10`)
- **SSH:** `ssh jetson@192.168.10.10`
- **Root folder:** `/home/jetson/docker/ytdlp-telegram`
- **Ollama:** Runs locally on the Jetson at `http://192.168.10.10:11434`

## Current Limitations

- Playlist downloads not yet implemented (keyboard exists, logic is TODO)
- No concurrent downloads (sequential queue only)
- No test suite

## Troubleshooting

- Check bot logs: `docker compose logs -f bot`
- Check file server logs: `docker compose logs -f file-server`
- "Session expired" on callbacks → check handler ordering in `handle_callback()`
- Use `logger.exception()` instead of `logger.error()` to capture full tracebacks
