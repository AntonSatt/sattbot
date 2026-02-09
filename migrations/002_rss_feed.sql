-- RSS feed storage for weekly summaries

CREATE TABLE IF NOT EXISTS rss_guild_config (
    guild_id INTEGER PRIMARY KEY,
    rss_channel_id INTEGER DEFAULT NULL,
    FOREIGN KEY (guild_id) REFERENCES guild_settings(guild_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS rss_feed_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    link TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    published_at TEXT NOT NULL DEFAULT '',
    fetched_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (guild_id) REFERENCES guild_settings(guild_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_rss_feed_items_guild_fetched
    ON rss_feed_items (guild_id, fetched_at);
