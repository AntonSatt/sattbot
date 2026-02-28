import os
from dotenv import load_dotenv

load_dotenv()

# Secrets
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
HUMOR_API_KEY = os.getenv("HUMOR_API_KEY", "")

# Paths
DATABASE_PATH = os.getenv("DATABASE_PATH", "sattbot.db")

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# API URLs
HUMOR_API_URL = "https://api.humorapi.com/memes/random"
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Default AI model
DEFAULT_AI_MODEL = "google/gemini-2.5-flash"

# Default moderation settings
DEFAULT_SPAM_MAX_MSGS = 10
DEFAULT_SPAM_MUTE_SECS = 60
DEFAULT_SCAN_LIMIT = 1000
DEFAULT_NUKE_DAYS = 60

# RSS feeds
METACURATE_RSS_URL = "https://metacurate.io/briefs/daily/latest/rss"
METACURATE_QOTD_URL = "https://metacurate.io/qotd/rss"

# Command default access levels
DEFAULT_COMMAND_ACCESS = {
    "help": "public",
    "ping": "public",
    "meme": "public",
    "roastme": "public",
    "topchatter": "public",
    "inactive": "admin_only",
    "nuke": "admin_only",
    "dailynews": "public",
    "qotd": "public",
    "qotd-channel": "admin_only",
    "rss-channel": "admin_only",
    "rss-fetch": "admin_only",
}
