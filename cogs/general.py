import time

import discord
from discord import app_commands
from discord.ext import commands

from checks import has_command_permission


class General(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="ping", description="Check the bot's latency")
    @has_command_permission("ping")
    async def ping(self, interaction: discord.Interaction) -> None:
        start = time.perf_counter()
        await interaction.response.send_message("Pinging...", ephemeral=True)
        end = time.perf_counter()
        latency_ms = (end - start) * 1000
        ws_ms = self.bot.latency * 1000
        await interaction.edit_original_response(
            content=f"Pong! Roundtrip: {latency_ms:.0f}ms | WebSocket: {ws_ms:.0f}ms"
        )

    @app_commands.command(name="help", description="Show available commands")
    @has_command_permission("help")
    async def help(self, interaction: discord.Interaction) -> None:
        guild_id = interaction.guild_id
        db = self.bot.db
        defaults = await db.get_all_command_defaults(guild_id)
        permissions = await db.get_all_command_permissions(guild_id)
        is_admin = interaction.user.guild_permissions.administrator

        accessible = []
        for cmd_name, access in sorted(defaults.items()):
            if access == "public":
                accessible.append(cmd_name)
            elif access == "admin_only":
                if is_admin:
                    accessible.append(cmd_name)
            elif access == "restricted":
                if is_admin:
                    accessible.append(cmd_name)
                else:
                    allowed_roles = set(permissions.get(cmd_name, []))
                    user_roles = {r.id for r in interaction.user.roles}
                    if allowed_roles & user_roles:
                        accessible.append(cmd_name)

        descriptions = {
            "ping": "Check the bot's latency",
            "help": "Show available commands",
            "meme": "Get a random meme",
            "roastme": "Get roasted by AI",
            "topchatter": "See the most active chatters",
            "inactive": "List inactive members",
            "nuke": "Remove inactive members",
            "setup": "Run the setup wizard (Admin)",
            "permissions": "Manage command permissions (Admin)",
            "permissions-view": "View current permissions (Admin)",
            "config": "Change server settings (Admin)",
            "dailynews": "Get today's AI & tech news",
            "rss-channel": "Set the channel for daily news (Admin)",
            "rss-fetch": "Manually fetch and post today's news (Admin)",
            "qotd": "Post today's Question of the Day as a poll",
            "qotd-channel": "Set the channel for QOTD posts (Admin)",
        }

        # Always show admin commands to admins
        if is_admin:
            for cmd in ("setup", "permissions", "permissions-view", "config"):
                if cmd not in accessible:
                    accessible.append(cmd)

        embed = discord.Embed(
            title="SattBot Commands",
            color=discord.Color.blurple(),
        )
        for cmd_name in sorted(accessible):
            desc = descriptions.get(cmd_name, "No description")
            embed.add_field(
                name=f"/{cmd_name}", value=desc, inline=False
            )

        if not accessible:
            embed.description = "No commands available to you in this server."

        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(General(bot))
