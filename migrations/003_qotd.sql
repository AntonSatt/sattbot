-- Question of the Day channel config (separate from RSS news channel)

CREATE TABLE IF NOT EXISTS qotd_guild_config (
    guild_id INTEGER PRIMARY KEY,
    qotd_channel_id INTEGER DEFAULT NULL,
    FOREIGN KEY (guild_id) REFERENCES guild_settings(guild_id) ON DELETE CASCADE
);

-- Track active QOTD polls so we can post the answer reveal later
CREATE TABLE IF NOT EXISTS qotd_active_polls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    channel_id INTEGER NOT NULL,
    message_id INTEGER NOT NULL,
    question TEXT NOT NULL,
    answer_data TEXT NOT NULL,         -- JSON blob of the full feed item for building the answer embed
    reveal_at TEXT NOT NULL,           -- ISO timestamp when the answer should be revealed
    revealed INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (guild_id) REFERENCES guild_settings(guild_id) ON DELETE CASCADE
);
