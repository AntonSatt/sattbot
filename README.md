# SattBot

A modular Discord bot with per-server configurable permissions, slash commands, moderation tools, and an interactive setup wizard.

## Features

- **Slash commands** — `/ping`, `/help`, `/meme`, `/roastme`, `/topchatter`, `/inactive`, `/nuke`
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
| `OPENROUTER_API_KEY` | No | Enables `/roastme` AI features |
| `HUMOR_API_KEY` | No | Enables `/meme` command |
| `DATABASE_PATH` | No | SQLite path (default: `sattbot.db`) |
| `LOG_LEVEL` | No | Logging level (default: `INFO`) |

### In-Server Configuration

- `/setup` — Interactive wizard for first-time configuration
- `/config` — View or change individual settings
- `/permissions` — Grant/revoke role access to commands
- `/permissions-view` — See current permission settings

## Permission System

Three layers of access control:

1. **Discord's built-in** — Admin commands (`/setup`, `/permissions`, `/config`) are hidden from non-admins
2. **Command defaults** — Each command is `public`, `admin_only`, or `restricted` per server
3. **Role grants** — When a command is `restricted`, only listed roles can use it; admins always bypass

### Default Access

| Command | Default |
|---------|---------|
| `/help`, `/ping`, `/meme`, `/roastme`, `/topchatter` | public |
| `/inactive`, `/nuke` | admin_only |

### Example

```
/permissions command:inactive action:Grant role:@Mods
→ Now only @Mods and admins can use /inactive
```

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
