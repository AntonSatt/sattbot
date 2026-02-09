-- Initial schema for SattBot

CREATE TABLE IF NOT EXISTS guild_settings (
    guild_id INTEGER PRIMARY KEY,
    spam_max_msgs INTEGER NOT NULL DEFAULT 10,
    spam_mute_secs INTEGER NOT NULL DEFAULT 60,
    scan_limit INTEGER NOT NULL DEFAULT 1000,
    nuke_days INTEGER NOT NULL DEFAULT 60,
    ai_model TEXT NOT NULL DEFAULT 'meta-llama/llama-3.3-70b-instruct',
    setup_complete INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS command_defaults (
    guild_id INTEGER NOT NULL,
    command TEXT NOT NULL,
    default_access TEXT NOT NULL DEFAULT 'public',
    PRIMARY KEY (guild_id, command),
    FOREIGN KEY (guild_id) REFERENCES guild_settings(guild_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS command_permissions (
    guild_id INTEGER NOT NULL,
    command TEXT NOT NULL,
    role_id INTEGER NOT NULL,
    UNIQUE (guild_id, command, role_id),
    FOREIGN KEY (guild_id) REFERENCES guild_settings(guild_id) ON DELETE CASCADE
);
