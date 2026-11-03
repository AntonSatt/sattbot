# SattBot

A modular Discord bot with per-server configurable permissions, slash commands, moderation tools, and an interactive setup wizard.

## Features

- **Slash commands** — `/ping`, `/help`, `/meme`, `/roastme`, `/topchatter`, `/inactive`, `/nuke`, `/rolepurge`
- **Daily AI & tech news** — posts the latest brief from [Metacurate.io](https://metacurate.io/briefs/daily/latest/rss) as pretty embeds every day at 08:00 CET
- **Question of the Day** — posts a daily QOTD as a native Discord poll at 08:00 CET with context, then reveals the answer 8 hours later
- **Per-server permissions** — 3-tier system (public / admin-only / restricted by role)
- **Interactive setup wizard** — `/setup` walks admins through configuration
- **Anti-spam** — automatic muting when message rate exceeds threshold
- **AI roasts** — powered by OpenRouter (default `openai/gpt-6-luna`, change per server with `/config ai_model`)
- **Random memes** — via HumorAPI
- **Moderation** — scan for inactive members, bulk kick with confirmation, or kick everyone without the roles you pick ([Role Purge](#role-purge))

## Inviting the Bot

Generate an invite link with these permissions: **Send Messages**, **Embed Links**, **Read Message History**, **Kick Members**, **Moderate Members** (for timeouts). Permission integer: `1101927424064`.

## Invite Link

[Invite SattBot to your server](https://discord.com/api/oauth2/authorize?client_id=1421000801098141817&permissions=1101927424064&scope=bot%20applications.commands)

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
| `OPENROUTER_API_KEY` | No | Enables `/roastme` and AI captions in kick reports |
| `HUMOR_API_KEY` | No | Enables `/meme` command and GIFs in kick reports |
| `DATABASE_PATH` | No | SQLite path (default: `sattbot.db`; the Docker image uses `/app/data/sattbot.db`, which must be a persistent volume) |
| `LOG_LEVEL` | No | Logging level (default: `INFO`) |

### In-Server Configuration

- `/setup` — Interactive wizard for first-time configuration
- `/config` — View or change individual settings
- `/permissions` — Grant/revoke role access to commands
- `/permissions-view` — See current permission settings
- `/rss-channel #channel` — Set which channel receives the daily news
- `/qotd-channel #channel` — Set which channel receives the Question of the Day poll
- `/modlog-channel #channel`: Set which channel receives [kick reports](#kick-reports) from `/nuke` and `/rolepurge`

## Permission System

Three layers of access control:

1. **Discord's built-in** — Admin commands (`/setup`, `/permissions`, `/config`) are hidden from non-admins
2. **Command defaults** — Each command is `public`, `admin_only`, or `restricted` per server
3. **Role grants** — When a command is `restricted`, only listed roles can use it; admins always bypass

### Default Access

| Command | Default |
|---------|---------|
| `/help`, `/ping`, `/meme`, `/roastme`, `/topchatter`, `/dailynews`, `/qotd` | public |
| `/inactive`, `/nuke`, `/rolepurge`, `/modlog-channel`, `/rss-channel`, `/rss-fetch`, `/qotd-channel` | admin_only |

### Example

```
/permissions command:inactive action:Grant role:@Mods
→ Now only @Mods and admins can use /inactive
```

## Role Purge

`/rolepurge` kicks every member who has none of the roles you pick, for example everyone who hasn't chosen a class role yet.

1. Run `/rolepurge` and pick the roles that let a member stay (up to 25).
2. The bot lists everyone who would be kicked and attaches the full list as `rolepurge.txt`. Bots, admins, the server owner, you, and members who joined within `grace_days` are never on it.
3. Nothing happens until you press **Confirm Role Purge**. Each member then gets a DM just before the kick; closed DMs don't stop the kick.

| Option | Description |
|--------|-------------|
| `grace_days` | Skip members who joined within this many days (0-365, default 7) |
| `message` | Text of the DM (default: a short notice in English) |
| `invite` | Invite link added at the end of the DM |

The bot can only kick members whose highest role is below its own, so keep the bot's role above the roles those members hold. The preview counts anyone it can't kick.

## Kick Reports

When a `/nuke` or `/rolepurge` kicks anyone, the bot posts a report in the channel set with `/modlog-channel`, typically a channel only admins can see:

- a meme caption written by AI (OpenRouter, the same model as `/roastme`), which never names the people removed
- a fitting GIF from HumorAPI
- how many were kicked, how many failed, how many got the DM, and who ran the command
- the full list of kicked members as an attachment

Without API keys, or if an API doesn't answer, the report uses a built-in caption and skips the GIF. Without a configured channel nothing is posted.

## Daily AI & Tech News

SattBot posts a daily tech brief from [Metacurate.io](https://metacurate.io/) as a formatted embed with headlines and summaries.

### How it works

1. **Scheduled post** — Every day at **08:00 CET** (Stockholm time), the bot fetches the latest brief from the [Metacurate RSS feed](https://metacurate.io/briefs/daily/latest/rss) and posts it as an embed in the configured channel.
2. **Cleanup** — Articles older than 30 days are automatically deleted from the database.

No AI processing or API keys are required — the feed content is formatted directly into Discord embeds.

### News Commands

| Command | Access | Description |
|---------|--------|-------------|
| `/rss-channel [#channel]` | Admin | Set or view the channel that receives daily news |
| `/rss-fetch` | Admin | Manually fetch and post today's news (useful for testing) |
| `/dailynews` | Public | Get today's news on demand |

### Setup

```
/rss-channel #news
```

The bot will start posting the daily brief at 08:00 CET. Use `/dailynews` or `/rss-fetch` to test immediately.

## Question of the Day

SattBot posts a daily Question of the Day from [Metacurate.io](https://metacurate.io/qotd/rss) as a native Discord poll with topic context. Users vote, and the detailed answer is revealed automatically 8 hours later.

### How it works

1. **Poll posted at 08:00 CET** — The bot fetches the latest QOTD and posts it as a Discord poll with three choices: **Yes**, **No**, and **It's Complicated**. A context paragraph and source link are included above the poll so users understand the topic.
2. **Users vote** — Members vote using Discord's native poll UI for 8 hours.
3. **Answer revealed at 16:00 CET** — The bot replies to the original poll with the full answer embed, including a TL;DR, detailed explanation, and source links.
4. **Cleanup** — Revealed polls older than 7 days are cleaned up automatically.

### QOTD Commands

| Command | Access | Description |
|---------|--------|-------------|
| `/qotd-channel [#channel]` | Admin | Set or view the channel that receives daily QOTD polls |
| `/qotd` | Public | Post today's QOTD poll on demand |

### Setup

```
/qotd-channel #trivia
```

The bot will start posting daily polls at 08:00 CET. Use `/qotd` to test immediately.

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
