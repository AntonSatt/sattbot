import logging
import pathlib

import aiosqlite

from config import DEFAULT_COMMAND_ACCESS

log = logging.getLogger(__name__)

MIGRATIONS_DIR = pathlib.Path(__file__).parent / "migrations"


class Database:
    def __init__(self, path: str) -> None:
        self.path = path
        self.db: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        self.db = await aiosqlite.connect(self.path)
        await self.db.execute("PRAGMA journal_mode=WAL")
        await self.db.execute("PRAGMA foreign_keys=ON")
        await self._run_migrations()
        log.info("Database connected: %s", self.path)

    async def close(self) -> None:
        if self.db:
            await self.db.close()

    async def _run_migrations(self) -> None:
        for sql_file in sorted(MIGRATIONS_DIR.glob("*.sql")):
            sql = sql_file.read_text()
            await self.db.executescript(sql)
            log.info("Applied migration: %s", sql_file.name)

    # ── Guild settings ──────────────────────────────────────────────

    async def ensure_guild(self, guild_id: int) -> None:
        """Insert default guild settings and command defaults if missing."""
        await self.db.execute(
            "INSERT OR IGNORE INTO guild_settings (guild_id) VALUES (?)",
            (guild_id,),
        )
        for cmd, access in DEFAULT_COMMAND_ACCESS.items():
            await self.db.execute(
                "INSERT OR IGNORE INTO command_defaults (guild_id, command, default_access) "
                "VALUES (?, ?, ?)",
                (guild_id, cmd, access),
            )
        await self.db.commit()

    async def get_guild_settings(self, guild_id: int) -> dict | None:
        async with self.db.execute(
            "SELECT * FROM guild_settings WHERE guild_id = ?", (guild_id,)
        ) as cur:
            row = await cur.fetchone()
            if row is None:
                return None
            cols = [d[0] for d in cur.description]
            return dict(zip(cols, row))

    async def update_guild_setting(
        self, guild_id: int, key: str, value
    ) -> None:
        allowed = {
            "spam_max_msgs",
            "spam_mute_secs",
            "scan_limit",
            "nuke_days",
            "ai_model",
            "setup_complete",
        }
        if key not in allowed:
            raise ValueError(f"Invalid setting: {key}")
        await self.db.execute(
            f"UPDATE guild_settings SET {key} = ?, updated_at = datetime('now') "
            "WHERE guild_id = ?",
            (value, guild_id),
        )
        await self.db.commit()

    # ── Command permissions ─────────────────────────────────────────

    async def get_command_access(self, guild_id: int, command: str) -> str:
        async with self.db.execute(
            "SELECT default_access FROM command_defaults "
            "WHERE guild_id = ? AND command = ?",
            (guild_id, command),
        ) as cur:
            row = await cur.fetchone()
            if row is None:
                return DEFAULT_COMMAND_ACCESS.get(command, "public")
            return row[0]

    async def set_command_access(
        self, guild_id: int, command: str, access: str
    ) -> None:
        await self.db.execute(
            "INSERT INTO command_defaults (guild_id, command, default_access) "
            "VALUES (?, ?, ?) "
            "ON CONFLICT(guild_id, command) DO UPDATE SET default_access = excluded.default_access",
            (guild_id, command, access),
        )
        await self.db.commit()

    async def get_command_roles(self, guild_id: int, command: str) -> list[int]:
        async with self.db.execute(
            "SELECT role_id FROM command_permissions "
            "WHERE guild_id = ? AND command = ?",
            (guild_id, command),
        ) as cur:
            rows = await cur.fetchall()
            return [r[0] for r in rows]

    async def add_command_role(
        self, guild_id: int, command: str, role_id: int
    ) -> None:
        await self.db.execute(
            "INSERT OR IGNORE INTO command_permissions (guild_id, command, role_id) "
            "VALUES (?, ?, ?)",
            (guild_id, command, role_id),
        )
        await self.db.commit()

    async def remove_command_role(
        self, guild_id: int, command: str, role_id: int
    ) -> None:
        await self.db.execute(
            "DELETE FROM command_permissions "
            "WHERE guild_id = ? AND command = ? AND role_id = ?",
            (guild_id, command, role_id),
        )
        await self.db.commit()

    async def get_all_command_defaults(self, guild_id: int) -> dict[str, str]:
        async with self.db.execute(
            "SELECT command, default_access FROM command_defaults WHERE guild_id = ?",
            (guild_id,),
        ) as cur:
            rows = await cur.fetchall()
            return {r[0]: r[1] for r in rows}

    async def get_all_command_permissions(
        self, guild_id: int
    ) -> dict[str, list[int]]:
        async with self.db.execute(
            "SELECT command, role_id FROM command_permissions WHERE guild_id = ?",
            (guild_id,),
        ) as cur:
            rows = await cur.fetchall()
            result: dict[str, list[int]] = {}
            for cmd, role_id in rows:
                result.setdefault(cmd, []).append(role_id)
            return result

    async def remove_guild(self, guild_id: int) -> None:
        await self.db.execute(
            "DELETE FROM guild_settings WHERE guild_id = ?", (guild_id,)
        )
        await self.db.commit()

    # ── RSS feed ─────────────────────────────────────────────────────

    async def get_rss_channel(self, guild_id: int) -> int | None:
        async with self.db.execute(
            "SELECT rss_channel_id FROM rss_guild_config WHERE guild_id = ?",
            (guild_id,),
        ) as cur:
            row = await cur.fetchone()
            if row is None:
                return None
            return row[0]

    async def set_rss_channel(self, guild_id: int, channel_id: int | None) -> None:
        await self.db.execute(
            "INSERT INTO rss_guild_config (guild_id, rss_channel_id) "
            "VALUES (?, ?) "
            "ON CONFLICT(guild_id) DO UPDATE SET rss_channel_id = excluded.rss_channel_id",
            (guild_id, channel_id),
        )
        await self.db.commit()

    async def get_rss_guilds(self) -> list[tuple[int, int]]:
        """Return all (guild_id, rss_channel_id) pairs with a configured channel."""
        async with self.db.execute(
            "SELECT guild_id, rss_channel_id FROM rss_guild_config "
            "WHERE rss_channel_id IS NOT NULL",
        ) as cur:
            return await cur.fetchall()

    async def store_rss_items(
        self, guild_id: int, items: list[dict]
    ) -> int:
        """Store RSS feed items. Returns the number of new items inserted."""
        count = 0
        for item in items:
            # Skip duplicates based on link within the same guild
            async with self.db.execute(
                "SELECT 1 FROM rss_feed_items WHERE guild_id = ? AND link = ?",
                (guild_id, item["link"]),
            ) as cur:
                if await cur.fetchone():
                    continue
            await self.db.execute(
                "INSERT INTO rss_feed_items (guild_id, title, link, description, published_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    guild_id,
                    item.get("title", ""),
                    item["link"],
                    item.get("description", ""),
                    item.get("published_at", ""),
                ),
            )
            count += 1
        await self.db.commit()
        return count

    async def get_weekly_rss_items(self, guild_id: int) -> list[dict]:
        """Return RSS items fetched in the last 7 days for a guild."""
        async with self.db.execute(
            "SELECT title, link, description, published_at, fetched_at "
            "FROM rss_feed_items "
            "WHERE guild_id = ? AND fetched_at >= datetime('now', '-7 days') "
            "ORDER BY fetched_at DESC",
            (guild_id,),
        ) as cur:
            rows = await cur.fetchall()
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in rows]

    async def delete_old_rss_items(self, days: int = 30) -> int:
        """Delete RSS items older than the given number of days. Returns count."""
        cur = await self.db.execute(
            "DELETE FROM rss_feed_items WHERE fetched_at < datetime('now', ?)",
            (f"-{days} days",),
        )
        await self.db.commit()
        return cur.rowcount
