# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.12] - 2026-05-10

### Added
- `/about` command showing bot version, license, source URL, host name, OS, architecture, Python and yt-dlp versions, and process uptime.
- `/about` listed in `/help` together with the other utility commands.

## [0.1.11] - 2026-05-10

### Fixed
- Unlisted YouTube videos failing with "This video is not available". Added `_YOUTUBE_EXTRACTOR_ARGS` in `bot/downloader.py` that overrides yt-dlp's default `android_vr` player client with `mweb,web,android,ios`, applied to all four `ydl_opts` blocks (format detection, get_info, playlist extraction, download).

### Changed
- Bumped `yt-dlp` minimum to `>=2026.3.17` for upstream YouTube fixes.

## [0.1.10] - 2026-04-20

### Fixed
- YouTube `HTTP Error 403: Forbidden` caused by degraded POT tokens. The custom `pot-server` Dockerfile now installs `libexpat1`, which the native `canvas` module (used by `jsdom` for proof-of-origin attestation) requires.

### Changed
- Pinned `bgutil-ytdlp-pot-provider` to `>=1.3.1` to match the pot-server image and avoid version drift.

## [0.1.9] - 2024-01-19

### Added
- User management system with admin UI
- Access request workflow for new users
- Web-based admin panel for user management
- Live logs page in admin UI
- Modern theme support for admin interface

### Changed
- Status messages now edit in-place instead of delete/recreate for better UX

### Fixed
- Download queue issues

## [0.1.8] - 2024-01-XX

### Added
- File server for handling large downloads (>50MB)
- Download link generation with token-based access
- Delete button for removing downloaded files

## [0.1.7] - 2024-01-XX

### Added
- Download statistics tracking
- `/stats` command for viewing download history
- SQLite-based stats storage

## [0.1.6] - 2024-01-XX

### Added
- `/health` command for system health checks
- Disk space monitoring
- Ollama connectivity check
- File server health check

## [0.1.5] - 2024-01-XX

### Added
- Download queue with progress tracking
- Progress bar updates during downloads
- Download position tracking in queue

## [0.1.4] - 2024-01-XX

### Added
- Natural language processing via Ollama
- Intent parsing for download requests
- Heuristics fallback when LLM unavailable

## [0.1.3] - 2024-01-XX

### Added
- Quality selection for downloads
- Audio: 128kbps, 192kbps, 320kbps, best
- Video: 480p, 720p, 1080p, best

## [0.1.2] - 2024-01-XX

### Added
- Platform-based file organization
- Support for multiple platforms via yt-dlp

## [0.1.1] - 2024-01-XX

### Added
- Basic Telegram bot functionality
- URL detection and download
- Format selection (audio/video)

## [0.1.0] - 2024-01-XX

### Added
- Initial release
- yt-dlp integration
- Docker support
- User whitelist authentication
