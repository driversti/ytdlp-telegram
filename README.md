# ytdlp-telegram

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

A Telegram bot that downloads media from YouTube, Instagram, Facebook, Twitter/X, TikTok, and 1000+ other platforms using yt-dlp. Features natural language processing via Ollama for intelligent intent parsing.

## Features

- Download audio (MP3) or video from supported platforms
- Quality selection (128kbps-320kbps for audio, 480p-1080p for video)
- Download queue with progress tracking
- Natural language support via Ollama LLM integration
- Platform-based file organization
- User access control with admin approval workflow
- Web-based admin panel for user management
- File server for handling large downloads (>50MB)

## Supported Platforms

- YouTube
- Instagram
- Twitter/X
- Facebook
- TikTok
- Vimeo
- Reddit
- Twitch
- And 1000+ more via yt-dlp

## Requirements

- Docker and Docker Compose
- Telegram Bot Token (from [@BotFather](https://t.me/BotFather))
- (Optional) Ollama running on the host for natural language processing

## Quick Start

1. Clone the repository:
```bash
git clone https://github.com/driversti/ytdlp-telegram.git
cd ytdlp-telegram
```

2. Create your `.env` file:
```bash
cp .env.example .env
```

3. Edit `.env` with your configuration:
```env
TELEGRAM_BOT_TOKEN=your_bot_token_here
ALLOWED_USER_IDS=123456789
ADMIN_USER_ID=123456789
ADMIN_PASSWORD=your-secure-password
```

4. Start the bot:
```bash
docker compose up -d
```

## Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `TELEGRAM_BOT_TOKEN` | Your Telegram bot token | (required) |
| `ALLOWED_USER_IDS` | Comma-separated list of allowed user IDs | (required) |
| `ADMIN_USER_ID` | Telegram ID for access request notifications | (optional) |
| `ADMIN_PASSWORD` | Password for web admin UI | (optional) |
| `OLLAMA_URL` | Ollama API endpoint | `http://localhost:11434` |
| `OLLAMA_MODEL` | Ollama model for NLP | `llama3.2:3b` |
| `DOWNLOAD_PATH` | Directory for downloaded files | `/downloads` |
| `MAX_FILE_SIZE_MB` | Max file size for Telegram upload | `50` |
| `FILE_SERVER_URL` | Internal file server URL | `http://localhost:8080` |
| `FILE_SERVER_PUBLIC_URL` | Public file server URL | `http://localhost:8080` |

## Architecture

```
User message → Whitelist check → Intent parsing (LLM/heuristics)
→ Format keyboard → Quality keyboard → Download queued
→ yt-dlp execution → Progress updates
  → File ≤50MB: Send via Telegram
  → File >50MB: Generate link via file server
```

### Components

- **Bot** - Main Telegram bot handling commands and downloads
- **File Server** - FastAPI service for large files and admin UI
- **PO Token Server** - YouTube authentication support

## Usage

### Commands

- `/start` - Show welcome message
- `/help` - Show help information
- `/status` - Check download queue status
- `/stats` - View download statistics
- `/health` - System health check
- `/about` - Bot version and host information

### Downloading

1. **Direct URL**: Paste a URL and the bot will prompt you to choose format and quality.

2. **Natural Language** (requires Ollama):
   - "download the audio from https://youtube.com/..."
   - "grab this video https://twitter.com/..."
   - "get me this song https://..."

### Quality Options

**Audio:**
- 128 kbps
- 192 kbps
- 320 kbps
- Best available

**Video:**
- 480p
- 720p
- 1080p
- Best available

## User Management

The bot uses a hybrid authorization system:

1. **Environment whitelist** (`ALLOWED_USER_IDS`) - Always allowed
2. **Database users** - Can be managed via admin UI

### Access Request Flow

1. Unauthorized user sends message → Bot shows "Request Access" button
2. User clicks button → Admin receives notification with Approve/Deny buttons
3. Admin approves → User can use the bot

### Web Admin Panel

Access at `{FILE_SERVER_PUBLIC_URL}/admin` (requires `ADMIN_PASSWORD`):
- View and manage users
- Approve/deny access requests
- Add users by Telegram ID

## File Organization

Downloads are organized by platform:
```
/downloads/
├── youtube/
├── instagram/
├── twitter/
├── facebook/
├── tiktok/
└── other/
```

## Development

### Local Setup

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python main.py
```

### Running Tests

```bash
pytest tests/ -v
pytest tests/ --cov=bot --cov-report=term-missing
```

### Project Structure

```
ytdlp-telegram/
├── bot/
│   ├── handlers.py       # Telegram handlers
│   ├── downloader.py     # yt-dlp wrapper + queue
│   ├── llm_service.py    # Ollama integration
│   ├── storage.py        # File management
│   ├── keyboards.py      # Inline keyboards
│   ├── middleware.py     # Auth middleware
│   ├── user_service.py   # User management
│   └── stats_service.py  # Download statistics
├── file-server/          # FastAPI file server
├── tests/                # Test suite
├── config.py             # Configuration
├── main.py               # Entry point
└── docker-compose.yml
```

## Troubleshooting

### Bot doesn't respond
- Check if your user ID is in `ALLOWED_USER_IDS` or approved in the database
- Verify bot token is correct
- Check Docker logs: `docker compose logs -f bot`

### Download fails
- Some content may be age-restricted or private
- Check if the URL is supported by yt-dlp
- Some platforms require cookies for authentication

### Large files
Files larger than 50MB are served via the file server with a download link.

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## Acknowledgments

- [yt-dlp](https://github.com/yt-dlp/yt-dlp) - The core download engine
- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) - Telegram Bot API wrapper
- [Ollama](https://ollama.ai/) - Local LLM inference
- [FastAPI](https://fastapi.tiangolo.com/) - File server framework

## License

MIT - see [LICENSE](LICENSE) for details.
