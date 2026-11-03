-- Move servers off the old default AI models, once.
-- Llama 3.3 70B was the old column default and Mixtral 8x7B is gone from
-- OpenRouter. Every migration runs on each start, so a marker row keeps this
-- from undoing a model an admin picks later with /config.

CREATE TABLE IF NOT EXISTS data_fixes (
    name TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT (datetime('now'))
);

UPDATE guild_settings
SET ai_model = 'openai/gpt-6-luna'
WHERE ai_model IN ('meta-llama/llama-3.3-70b-instruct', 'mistralai/mixtral-8x7b-instruct')
  AND NOT EXISTS (SELECT 1 FROM data_fixes WHERE name = '005_ai_model');

INSERT OR IGNORE INTO data_fixes (name) VALUES ('005_ai_model');
