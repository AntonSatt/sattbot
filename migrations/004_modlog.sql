-- Moderation log channel: where /nuke and /rolepurge report what they kicked

CREATE TABLE IF NOT EXISTS modlog_guild_config (
    guild_id INTEGER PRIMARY KEY,
    modlog_channel_id INTEGER DEFAULT NULL,
    FOREIGN KEY (guild_id) REFERENCES guild_settings(guild_id) ON DELETE CASCADE
);
