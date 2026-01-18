# ytdlp-telegram

A personal Telegram bot that downloads media from YouTube, Instagram, Facebook, Twitter, and 1000+ other platforms using yt-dlp.

## Features

- Download audio (MP3) or video from supported platforms
- Quality selection (128kbps-320kbps for audio, 480p-1080p for video)
- Sequential download queue with position tracking
- Natural language support via Ollama LLM integration
- Platform-based file organization
- User whitelist for access control

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
git clone <repository-url>
cd ytdlp-telegram
```

2. Create your `.env` file:
```bash
cp .env.example .env
```

3. Edit `.env` with your configuration:
```env
TELEGRAM_BOT_TOKEN=your_bot_token_here
ALLOWED_USER_IDS=299701567
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2:3b
DOWNLOAD_PATH=/downloads
MAX_FILE_SIZE_MB=50
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
| `OLLAMA_URL` | Ollama API endpoint | `http://localhost:11434` |
| `OLLAMA_MODEL` | Ollama model for NLP | `llama3.2:3b` |
| `DOWNLOAD_PATH` | Directory for downloaded files | `/downloads` |
| `MAX_FILE_SIZE_MB` | Max file size for Telegram upload | `50` |

## Usage

### Commands

- `/start` - Show welcome message
- `/help` - Show help information
- `/status` - Check download queue status

### Downloading

1. **Direct URL**: Just paste a URL and the bot will prompt you to choose format and quality.

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

## File Organization

Downloads are organized by platform:
```
/downloads/
├── youtube/
├── instagram/
├── twitter/
├── facebook/
├── tiktok/
├── vimeo/
├── reddit/
├── twitch/
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

### Project Structure

```
ytdlp-telegram/
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── .env.example
├── config.py
├── main.py
└── bot/
    ├── __init__.py
    ├── handlers.py      # Telegram handlers
    ├── keyboards.py     # Inline keyboards
    ├── llm_service.py   # Ollama integration
    ├── downloader.py    # yt-dlp wrapper + queue
    ├── storage.py       # File management
    └── middleware.py    # Auth middleware
```

## Troubleshooting

### Bot doesn't respond
- Check if your user ID is in `ALLOWED_USER_IDS`
- Verify bot token is correct
- Check Docker logs: `docker compose logs -f`

### Download fails
- Some content may be age-restricted or private
- Check if the URL is supported by yt-dlp
- Some platforms require cookies for authentication

### Large files
Files larger than 50MB (or your configured limit) are saved to disk but cannot be sent via Telegram due to API limitations.

## License

MIT
