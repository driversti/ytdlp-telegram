# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
- Concurrent download queue with configurable limit
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
