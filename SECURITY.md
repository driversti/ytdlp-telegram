# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in this project, please report it
privately rather than opening a public GitHub issue.

- Use [GitHub's private vulnerability reporting](https://github.com/driversti/ytdlp-telegram/security/advisories/new)
  for the fastest, traceable path.
- Alternatively, contact the maintainer via the email listed on the GitHub
  profile.

Please include:
- A description of the issue and its potential impact.
- Steps to reproduce, or a proof-of-concept.
- The version (or commit SHA) you observed it on.

You can expect an acknowledgement within a few days. Fixes for confirmed
issues are prioritized over feature work.

## Scope

This project is a self-hosted Telegram bot. Security-relevant areas include:

- **Telegram bot token handling** — never commit `.env`; use `.env.example`
  as a template.
- **Whitelist enforcement** — `ALLOWED_USER_IDS` plus the database-backed
  user table gate every command and callback.
- **File server tokens** — UUIDs for large-file links; treat as bearer
  credentials and rotate by deletion.
- **Admin UI session cookies** — signed via `itsdangerous`; protect
  `ADMIN_PASSWORD`.
- **Path traversal** — the file server validates paths before reads/deletes.

## Out of Scope

- Vulnerabilities in upstream dependencies (`yt-dlp`, `python-telegram-bot`,
  FastAPI, Ollama, etc.) — please report those to their respective projects.
  We will respond by upgrading once a fix is published.
- Issues that require an attacker to already control the host running the
  bot.

## Operational Recommendations

- Run the bot in a dedicated host or container; do not share the file
  server's storage volume with sensitive data.
- Keep `ALLOWED_USER_IDS` minimal; rely on the admin approval workflow for
  ad-hoc users.
- Rotate the bot token via @BotFather (`/revoke`) after any suspected
  exposure.
- Place the file server behind HTTPS (reverse proxy) when exposing it to
  the public internet.
