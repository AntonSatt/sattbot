# SattBot

A modular Discord bot with per-server configurable permissions, slash commands, moderation tools, and an interactive setup wizard.

## Features

- **Slash commands** — `/ping`, `/help`, `/meme`, `/roastme`, `/topchatter`, `/inactive`, `/nuke`
- **Weekly RSS summaries** — daily fetch from [Metacurate.io](https://metacurate.io/briefs/daily/latest/rss), AI-powered weekly digest via OpenRouter
- **Per-server permissions** — 3-tier system (public / admin-only / restricted by role)
- **Interactive setup wizard** — `/setup` walks admins through configuration
- **Anti-spam** — automatic muting when message rate exceeds threshold
- **AI roasts** — powered by OpenRouter (configurable model)
- **Random memes** — via HumorAPI
- **Moderation** — scan for inactive members, bulk kick with confirmation

## Quick Start

### Docker (recommended)

```bash
cp .env.example .env
# Edit .env with your tokens
docker compose up -d --build
```

### Manual

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your tokens
python bot.py
```

## Configuration

### Environment Variables (`.env`)

| Variable | Required | Description |
|----------|----------|-------------|
| `DISCORD_TOKEN` | Yes | Your Discord bot token |
| `OPENROUTER_API_KEY` | No | Enables `/roastme` and weekly RSS summaries |
| `HUMOR_API_KEY` | No | Enables `/meme` command |
| `DATABASE_PATH` | No | SQLite path (default: `sattbot.db`) |
| `LOG_LEVEL` | No | Logging level (default: `INFO`) |

### In-Server Configuration

- `/setup` — Interactive wizard for first-time configuration
- `/config` — View or change individual settings
- `/permissions` — Grant/revoke role access to commands
- `/permissions-view` — See current permission settings
- `/rss-channel #channel` — Set which channel receives the weekly RSS summary

## Permission System

Three layers of access control:

1. **Discord's built-in** — Admin commands (`/setup`, `/permissions`, `/config`) are hidden from non-admins
2. **Command defaults** — Each command is `public`, `admin_only`, or `restricted` per server
3. **Role grants** — When a command is `restricted`, only listed roles can use it; admins always bypass

### Default Access

| Command | Default |
|---------|---------|
| `/help`, `/ping`, `/meme`, `/roastme`, `/topchatter`, `/weeklysummary` | public |
| `/inactive`, `/nuke`, `/rss-channel`, `/rss-fetch` | admin_only |

### Example

```
/permissions command:inactive action:Grant role:@Mods
→ Now only @Mods and admins can use /inactive
```

## Weekly RSS Summary

SattBot can pull the daily tech brief from [Metacurate.io](https://metacurate.io/) and generate a weekly AI-powered summary posted to a channel of your choice.

### How it works

1. **Daily fetch** — A background task runs every 24 hours and downloads articles from the [Metacurate RSS feed](https://metacurate.io/briefs/daily/latest/rss). Articles are stored in the database per guild.
2. **Weekly summary** — Every 7 days the bot sends the stored articles to OpenRouter, which generates a concise digest and posts it as an embed in the configured channel.
3. **Cleanup** — Articles older than 30 days are automatically deleted.

### RSS Commands

| Command | Access | Description |
|---------|--------|-------------|
| `/rss-channel [#channel]` | Admin | Set or view the channel that receives weekly summaries |
| `/rss-fetch` | Admin | Manually trigger an RSS fetch (useful for testing) |
| `/weeklysummary` | Public | Get this week's summary on demand |

### Setup

```
/rss-channel #news
```

That's it. The bot will start collecting articles and post its first summary after 7 days (or use `/weeklysummary` any time to get one immediately).

> **Note:** The `OPENROUTER_API_KEY` environment variable is required for AI summaries. Without it the bot falls back to posting a plain list of article links.

## Project Structure

```
sattbot/
├── bot.py              # Entry point
├── config.py           # Loads .env, defines defaults
├── database.py         # aiosqlite wrapper, migrations, CRUD
├── checks.py           # Permission check decorator
├── cogs/               # Command groups
├── views/              # UI components (wizard, confirm dialogs)
├── utils/              # HTTP helpers, formatting
└── migrations/         # SQL schema files
```

## Requirements

- Python 3.11+
- discord.py 2.3+
- aiosqlite
- aiohttp
- python-dotenv
