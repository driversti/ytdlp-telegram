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

### Data Flow

```
User message → Whitelist check → Intent parsing (LLM/heuristics)
→ Format keyboard → Quality keyboard → DownloadTask created
→ Queue processing → yt-dlp execution → Send file or notify
```

### Key Patterns

- **Async/await throughout** - All I/O operations are non-blocking
- **Executor pattern** - CPU-bound yt-dlp work runs in thread pool via `asyncio.get_event_loop().run_in_executor()`
- **Callback-based progress** - Progress updates via async callbacks every 5%
- **Graceful degradation** - LLM optional, falls back to keyword-based heuristics
- **Decorator auth** - `@whitelist_only` wraps handlers

### Callback Data Format

Inline keyboard callbacks use: `"prefix:action|url_short"` (URL truncated to 50 chars)
- Prefixes: `format:`, `quality:`, `confirm:`, `cancel:`

## Configuration

Required environment variables:
- `TELEGRAM_BOT_TOKEN` - From @BotFather
- `ALLOWED_USER_IDS` - Comma-separated user IDs

Optional:
- `OLLAMA_URL` (default: http://localhost:11434)
- `OLLAMA_MODEL` (default: llama3.2:3b)
- `DOWNLOAD_PATH` (default: /downloads)
- `MAX_FILE_SIZE_MB` (default: 50)

## Docker Setup

- Uses `python:3.11-slim` with FFmpeg
- Network mode `host` for local Ollama access
- Companion service: `bgutil-ytdlp-pot-provider` for YouTube PO Token support (port 4416)
- Multi-arch builds: `linux/amd64`, `linux/arm64`
- Registry: `registry.yurii.live`

## Current Limitations

- Playlist downloads not yet implemented (keyboard exists, logic is TODO)
- No concurrent downloads (sequential queue only)
- No test suite
- Files >50MB saved to disk but can't be sent via Telegram API
