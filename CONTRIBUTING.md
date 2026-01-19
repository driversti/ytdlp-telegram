# Contributing to ytdlp-telegram

Thank you for your interest in contributing to ytdlp-telegram! This document provides guidelines and information for contributors.

## How to Contribute

### Reporting Bugs

If you find a bug, please open an issue with:

1. **Clear title** describing the problem
2. **Steps to reproduce** the issue
3. **Expected behavior** vs actual behavior
4. **Environment details** (OS, Docker version, Python version if running locally)
5. **Relevant logs** from `docker compose logs bot`

### Suggesting Features

Feature requests are welcome! Please open an issue with:

1. **Clear description** of the proposed feature
2. **Use case** explaining why this feature would be useful
3. **Possible implementation** ideas (optional)

### Pull Requests

1. **Fork the repository** and create your branch from `main`
2. **Make your changes** following the code style guidelines below
3. **Add tests** for new functionality
4. **Ensure all tests pass**: `pytest tests/ -v`
5. **Update documentation** if needed
6. **Submit a pull request** with a clear description of changes

## Development Setup

```bash
# Clone your fork
git clone https://github.com/YOUR_USERNAME/ytdlp-telegram.git
cd ytdlp-telegram

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy and configure environment
cp .env.example .env
# Edit .env with your test bot token and user ID

# Run locally
python main.py

# Run tests
pytest tests/ -v
```

## Code Style Guidelines

### Python

- Follow [PEP 8](https://pep8.org/) style guide
- Use type hints for function parameters and return values
- Use `async`/`await` for all I/O operations
- Keep functions focused and under 50 lines when possible
- Use descriptive variable and function names

### Commits

- Use clear, concise commit messages
- Start with a verb in imperative mood (e.g., "Add", "Fix", "Update")
- Reference issue numbers when applicable (e.g., "Fix #123: ...")

### Documentation

- Update README.md if adding user-facing features
- Add docstrings for public functions
- Comment complex logic that isn't self-explanatory

## Testing

- Write unit tests for new functionality
- Tests should be in `tests/` directory
- Use pytest fixtures for common setup
- Mock external services (Telegram API, yt-dlp, Ollama)

Run tests with:

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=bot --cov-report=term-missing
```

## Project Structure

```
ytdlp-telegram/
├── bot/                  # Main bot package
│   ├── handlers.py       # Telegram command/message handlers
│   ├── downloader.py     # yt-dlp wrapper and download queue
│   ├── llm_service.py    # Ollama integration
│   ├── storage.py        # File management
│   ├── keyboards.py      # Inline keyboards
│   ├── middleware.py     # Auth middleware
│   └── ...
├── file-server/          # FastAPI file server
├── tests/                # Test suite
├── config.py             # Configuration
└── main.py               # Entry point
```

## Questions?

If you have questions about contributing, feel free to open an issue for discussion.

Thank you for contributing!
