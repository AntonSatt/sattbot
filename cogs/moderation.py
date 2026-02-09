import logging
from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import commands

from checks import has_command_permission
from utils.formatting import format_member_list, make_embed
from views.nuke_confirm import NukeConfirmView

log = logging.getLogger(__name__)


class Moderation(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="inactive",
        description="List members who haven't chatted in N days",
    )
    @app_commands.describe(days="Number of days to consider inactive (default: server setting)")
    @app_commands.checks.cooldown(1, 15.0)
    @has_command_permission("inactive")
    async def inactive(
        self, interaction: discord.Interaction, days: int | None = None
    ) -> None:
        await interaction.response.defer(ephemeral=True)

        settings = await self.bot.db.get_guild_settings(interaction.guild_id)
        nuke_days = days if days is not None else (settings["nuke_days"] if settings else 60)
        scan_limit = settings["scan_limit"] if settings else 1000
        cutoff = datetime.now(timezone.utc) - timedelta(days=nuke_days)

        active_ids: set[int] = set()
        for channel in interaction.guild.text_channels:
            perms = channel.permissions_for(interaction.guild.me)
            if not perms.read_message_history:
                continue
            try:
                async for msg in channel.history(limit=scan_limit, after=cutoff):
                    if not msg.author.bot:
                        active_ids.add(msg.author.id)
            except discord.Forbidden:
                continue

        inactive_members = [
            m
            for m in interaction.guild.members
            if not m.bot and m.id not in active_ids and not m.guild_permissions.administrator
        ]

        embed = make_embed(
            title=f"Inactive Members ({nuke_days}+ days)",
            description=format_member_list(inactive_members),
            color=discord.Color.orange(),
        )
        embed.set_footer(text=f"Found {len(inactive_members)} inactive member(s)")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(
        name="nuke",
        description="Kick members who haven't chatted in N days",
    )
    @app_commands.describe(days="Number of days to consider inactive (default: server setting)")
    @app_commands.checks.cooldown(1, 30.0)
    @has_command_permission("nuke")
    async def nuke(
        self, interaction: discord.Interaction, days: int | None = None
    ) -> None:
        await interaction.response.defer(ephemeral=True)

        settings = await self.bot.db.get_guild_settings(interaction.guild_id)
        nuke_days = days if days is not None else (settings["nuke_days"] if settings else 60)
        scan_limit = settings["scan_limit"] if settings else 1000
        cutoff = datetime.now(timezone.utc) - timedelta(days=nuke_days)

        active_ids: set[int] = set()
        for channel in interaction.guild.text_channels:
            perms = channel.permissions_for(interaction.guild.me)
            if not perms.read_message_history:
                continue
            try:
                async for msg in channel.history(limit=scan_limit, after=cutoff):
                    if not msg.author.bot:
                        active_ids.add(msg.author.id)
            except discord.Forbidden:
                continue

        inactive_members = [
            m
            for m in interaction.guild.members
            if not m.bot and m.id not in active_ids and not m.guild_permissions.administrator
        ]

        if not inactive_members:
            await interaction.followup.send("No inactive members found!", ephemeral=True)
            return

        embed = make_embed(
            title=f"Nuke Confirmation — {len(inactive_members)} members",
            description=(
                f"This will kick **{len(inactive_members)}** members who have been "
                f"inactive for **{nuke_days}+ days**.\n\n"
                + format_member_list(inactive_members)
            ),
            color=discord.Color.red(),
        )

        view = NukeConfirmView(interaction.user, inactive_members)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Moderation(bot))
