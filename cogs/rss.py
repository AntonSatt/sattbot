import logging

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands, tasks

from checks import has_command_permission
from utils.api import ai_weekly_summary, fetch_rss_feed

log = logging.getLogger(__name__)


class RSS(commands.Cog):
    """Fetches the Metacurate daily RSS feed and posts a weekly AI summary."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.session: aiohttp.ClientSession | None = None

    async def cog_load(self) -> None:
        self.session = aiohttp.ClientSession()
        self.daily_fetch.start()
        self.weekly_summary.start()
        self.cleanup_old_items.start()

    async def cog_unload(self) -> None:
        self.daily_fetch.cancel()
        self.weekly_summary.cancel()
        self.cleanup_old_items.cancel()
        if self.session:
            await self.session.close()

    # ── Background tasks ─────────────────────────────────────────────

    @tasks.loop(hours=24)
    async def daily_fetch(self) -> None:
        """Fetch today's RSS feed and store items for all configured guilds."""
        await self.bot.wait_until_ready()

        items = await fetch_rss_feed(self.session)
        if not items:
            log.info("RSS daily fetch: no items returned")
            return

        guilds = await self.bot.db.get_rss_guilds()
        for guild_id, _ in guilds:
            count = await self.bot.db.store_rss_items(guild_id, items)
            log.info("RSS: stored %d new items for guild %d", count, guild_id)

    @daily_fetch.before_loop
    async def before_daily_fetch(self) -> None:
        await self.bot.wait_until_ready()

    @tasks.loop(hours=168)  # 7 days
    async def weekly_summary(self) -> None:
        """Generate and post a weekly summary to each configured guild."""
        await self.bot.wait_until_ready()

        guilds = await self.bot.db.get_rss_guilds()
        for guild_id, channel_id in guilds:
            await self._post_summary(guild_id, channel_id)

    @weekly_summary.before_loop
    async def before_weekly_summary(self) -> None:
        await self.bot.wait_until_ready()

    @tasks.loop(hours=168)  # weekly cleanup
    async def cleanup_old_items(self) -> None:
        """Delete RSS items older than 30 days."""
        await self.bot.wait_until_ready()
        deleted = await self.bot.db.delete_old_rss_items(30)
        if deleted:
            log.info("RSS cleanup: deleted %d old items", deleted)

    @cleanup_old_items.before_loop
    async def before_cleanup(self) -> None:
        await self.bot.wait_until_ready()

    # ── Helper ───────────────────────────────────────────────────────

    async def _post_summary(self, guild_id: int, channel_id: int) -> None:
        """Build and send the weekly summary embed to the configured channel."""
        guild = self.bot.get_guild(guild_id)
        if guild is None:
            log.warning("RSS: guild %d not found, skipping summary", guild_id)
            return

        channel = guild.get_channel(channel_id)
        if channel is None:
            log.warning(
                "RSS: channel %d not found in guild %d, skipping",
                channel_id,
                guild_id,
            )
            return

        items = await self.bot.db.get_weekly_rss_items(guild_id)
        if not items:
            log.info("RSS: no items this week for guild %d", guild_id)
            return

        settings = await self.bot.db.get_guild_settings(guild_id)
        model = settings["ai_model"] if settings else None

        summary = await ai_weekly_summary(self.session, items, model)
        if summary is None:
            # Fallback: post a plain list if AI is unavailable
            lines = [f"- [{it['title']}]({it['link']})" for it in items[:15]]
            summary = "\n".join(lines)

        credit = "\n\n*Source: [Metacurate.io](https://metacurate.io/) — [Read more here](https://metacurate.io/)*"
        embed = discord.Embed(
            title="Weekly News Summary",
            description=summary + credit,
            color=discord.Color.blue(),
        )
        embed.set_footer(text=f"Based on {len(items)} articles from this week · Powered by Metacurate.io")

        try:
            await channel.send(embed=embed)
            log.info("RSS: posted weekly summary to guild %d", guild_id)
        except discord.Forbidden:
            log.warning(
                "RSS: missing permissions to post in channel %d (guild %d)",
                channel_id,
                guild_id,
            )

    # ── Slash commands ───────────────────────────────────────────────

    @app_commands.command(
        name="rss-channel",
        description="Set or view the channel for weekly RSS summaries",
    )
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(channel="The channel to post weekly summaries in (omit to view current)")
    @has_command_permission("rss-channel")
    async def rss_channel(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel | None = None,
    ) -> None:
        guild_id = interaction.guild_id
        await self.bot.db.ensure_guild(guild_id)

        if channel is None:
            current = await self.bot.db.get_rss_channel(guild_id)
            if current is None:
                await interaction.response.send_message(
                    "No RSS summary channel configured. "
                    "Use `/rss-channel #channel` to set one.",
                    ephemeral=True,
                )
            else:
                await interaction.response.send_message(
                    f"Weekly RSS summaries are posted to <#{current}>.",
                    ephemeral=True,
                )
            return

        await self.bot.db.set_rss_channel(guild_id, channel.id)
        await interaction.response.send_message(
            f"Weekly RSS summaries will now be posted to {channel.mention}.",
            ephemeral=True,
        )

    @app_commands.command(
        name="rss-fetch",
        description="Manually fetch the RSS feed now (for testing)",
    )
    @app_commands.default_permissions(administrator=True)
    @has_command_permission("rss-fetch")
    async def rss_fetch(self, interaction: discord.Interaction) -> None:
        guild_id = interaction.guild_id
        await self.bot.db.ensure_guild(guild_id)

        rss_channel = await self.bot.db.get_rss_channel(guild_id)
        if rss_channel is None:
            await interaction.response.send_message(
                "No RSS channel configured yet. Use `/rss-channel #channel` first.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        items = await fetch_rss_feed(self.session)
        if not items:
            await interaction.followup.send(
                "RSS fetch returned no items. The feed may be temporarily unavailable.",
                ephemeral=True,
            )
            return

        count = await self.bot.db.store_rss_items(guild_id, items)

        await interaction.followup.send(
            f"Fetched **{len(items)}** article(s) from Metacurate.io — "
            f"**{count}** new item(s) stored ({len(items) - count} duplicates skipped).",
            ephemeral=True,
        )

    @app_commands.command(
        name="weeklysummary",
        description="Get this week's RSS news summary on demand",
    )
    @app_commands.checks.cooldown(1, 30.0)
    @has_command_permission("weeklysummary")
    async def weekly_summary_cmd(self, interaction: discord.Interaction) -> None:
        guild_id = interaction.guild_id
        await self.bot.db.ensure_guild(guild_id)

        items = await self.bot.db.get_weekly_rss_items(guild_id)
        if not items:
            await interaction.response.send_message(
                "No RSS articles collected this week yet. "
                "Make sure an admin has configured `/rss-channel` and wait for the daily fetch.",
                ephemeral=True,
            )
            return

        await interaction.response.defer()

        settings = await self.bot.db.get_guild_settings(guild_id)
        model = settings["ai_model"] if settings else None

        summary = await ai_weekly_summary(self.session, items, model)
        if summary is None:
            lines = [f"- [{it['title']}]({it['link']})" for it in items[:15]]
            summary = "\n".join(lines)

        credit = "\n\n*Source: [Metacurate.io](https://metacurate.io/) — [Read more here](https://metacurate.io/)*"
        embed = discord.Embed(
            title="Weekly News Summary",
            description=summary + credit,
            color=discord.Color.blue(),
        )
        embed.set_footer(text=f"Based on {len(items)} articles from this week · Powered by Metacurate.io")
        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(RSS(bot))
