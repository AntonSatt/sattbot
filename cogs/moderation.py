import logging
from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import commands

from checks import has_command_permission
from utils.formatting import format_member_list, make_embed
from views.nuke_confirm import NukeConfirmView
from views.role_purge import RolePurgeView

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

    @app_commands.command(
        name="rolepurge",
        description="Kick members who have none of the roles you pick",
    )
    @app_commands.describe(
        grace_days="Skip members who joined within this many days (default: 7)",
        message="DM sent before the kick (default: a short notice in English)",
        invite="Invite link added at the end of the DM",
    )
    @app_commands.default_permissions(kick_members=True)
    @app_commands.checks.cooldown(1, 30.0)
    @has_command_permission("rolepurge")
    async def rolepurge(
        self,
        interaction: discord.Interaction,
        grace_days: app_commands.Range[int, 0, 365] = 7,
        message: app_commands.Range[str, 1, 1500] | None = None,
        invite: app_commands.Range[str, 1, 200] | None = None,
    ) -> None:
        if not interaction.guild.me.guild_permissions.kick_members:
            await interaction.response.send_message(
                "I need the Kick Members permission for this.", ephemeral=True
            )
            return

        dm_text = message or (
            f"You've been removed from **{interaction.guild.name}** in a clean-up "
            "of members without a role. You're welcome back any time."
        )
        if invite:
            dm_text += f"\n{invite}"

        view = RolePurgeView(interaction.user, grace_days, dm_text)
        await interaction.response.send_message(
            "Pick the roles that let a member stay. Everyone with none of them "
            "ends up on the list, and nobody is kicked until you confirm.",
            view=view,
            ephemeral=True,
        )

    @app_commands.command(
        name="modlog-channel",
        description="Set or view the channel where /nuke and /rolepurge report",
    )
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(channel="The channel for kick reports (omit to view current)")
    @has_command_permission("modlog-channel")
    async def modlog_channel(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel | None = None,
    ) -> None:
        guild_id = interaction.guild_id
        await self.bot.db.ensure_guild(guild_id)

        if channel is None:
            current = await self.bot.db.get_modlog_channel(guild_id)
            if current is None:
                await interaction.response.send_message(
                    "No moderation log channel configured. "
                    "Use `/modlog-channel #channel` to set one.",
                    ephemeral=True,
                )
            else:
                await interaction.response.send_message(
                    f"Kick reports are posted to <#{current}>.",
                    ephemeral=True,
                )
            return

        await self.bot.db.set_modlog_channel(guild_id, channel.id)
        await interaction.response.send_message(
            f"Kick reports from /nuke and /rolepurge will now be posted to {channel.mention}.",
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Moderation(bot))
