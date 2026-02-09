import logging
from collections import Counter

import discord
from discord import app_commands
from discord.ext import commands

from checks import has_command_permission
from utils.formatting import format_leaderboard

log = logging.getLogger(__name__)


class Activity(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="topchatter", description="See the most active chatters in this server"
    )
    @app_commands.checks.cooldown(1, 15.0)
    @has_command_permission("topchatter")
    async def topchatter(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()

        settings = await self.bot.db.get_guild_settings(interaction.guild_id)
        scan_limit = settings["scan_limit"] if settings else 1000

        counter: Counter[int] = Counter()
        for channel in interaction.guild.text_channels:
            perms = channel.permissions_for(interaction.guild.me)
            if not perms.read_message_history:
                continue
            try:
                async for msg in channel.history(limit=scan_limit):
                    if not msg.author.bot:
                        counter[msg.author.id] += 1
            except discord.Forbidden:
                continue

        if not counter:
            await interaction.followup.send("No message data found.")
            return

        top = counter.most_common(10)
        entries = []
        for user_id, count in top:
            member = interaction.guild.get_member(user_id)
            if member:
                entries.append((member, count))

        embed = discord.Embed(
            title="Top Chatters",
            description=format_leaderboard(entries),
            color=discord.Color.gold(),
        )
        embed.set_footer(
            text=f"Scanned up to {scan_limit} messages per channel"
        )
        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Activity(bot))
