import logging
import time
from collections import defaultdict

import discord
from discord.ext import commands

log = logging.getLogger(__name__)


class Listeners(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        # Anti-spam: guild_id -> user_id -> list of timestamps
        self.message_timestamps: dict[int, dict[int, list[float]]] = defaultdict(
            lambda: defaultdict(list)
        )

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild) -> None:
        log.info("Joined guild: %s (ID: %s)", guild.name, guild.id)
        await self.bot.db.ensure_guild(guild.id)

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild) -> None:
        log.info("Removed from guild: %s (ID: %s)", guild.name, guild.id)
        await self.bot.db.remove_guild(guild.id)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return

        # Block DMs
        if message.guild is None:
            try:
                await message.channel.send(
                    "I don't respond to DMs. Use me in a server!"
                )
            except discord.Forbidden:
                pass
            return

        # Anti-spam detection
        guild_id = message.guild.id
        user_id = message.author.id
        now = time.time()

        settings = await self.bot.db.get_guild_settings(guild_id)
        if settings is None:
            return

        max_msgs = settings["spam_max_msgs"]
        mute_secs = settings["spam_mute_secs"]

        timestamps = self.message_timestamps[guild_id][user_id]
        # Keep only messages within the last 60 seconds
        timestamps[:] = [t for t in timestamps if now - t < 60]
        timestamps.append(now)

        if len(timestamps) > max_msgs:
            # Don't mute admins
            if message.author.guild_permissions.administrator:
                return

            # Try to timeout the user
            try:
                duration = discord.utils.utcnow() + __import__(
                    "datetime"
                ).timedelta(seconds=mute_secs)
                await message.author.timeout(
                    duration, reason="Anti-spam: message rate exceeded"
                )
                await message.channel.send(
                    f"{message.author.mention} has been muted for {mute_secs}s (spam detected).",
                    delete_after=10,
                )
                log.info(
                    "Muted %s in %s for spam (%d msgs/min)",
                    message.author,
                    message.guild.name,
                    len(timestamps),
                )
            except discord.Forbidden:
                log.warning(
                    "Cannot mute %s in %s – missing permissions",
                    message.author,
                    message.guild.name,
                )
            # Reset their timestamps
            self.message_timestamps[guild_id][user_id] = []


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Listeners(bot))
