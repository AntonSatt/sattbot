import logging

import discord
from discord import app_commands
from discord.ext import commands

from config import DEFAULT_COMMAND_ACCESS
from views.setup_wizard import SetupWizardStartView
from views.permissions_ui import PermissionsView

log = logging.getLogger(__name__)

CONFIGURABLE_COMMANDS = list(DEFAULT_COMMAND_ACCESS.keys())


class Admin(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # ── /setup ──────────────────────────────────────────────────────

    @app_commands.command(
        name="setup", description="Run the interactive setup wizard"
    )
    @app_commands.default_permissions(administrator=True)
    async def setup_cmd(self, interaction: discord.Interaction) -> None:
        await self.bot.db.ensure_guild(interaction.guild_id)
        view = SetupWizardStartView(self.bot.db, interaction.guild_id)
        embed = discord.Embed(
            title="SattBot Setup Wizard",
            description=(
                "Welcome! This wizard will help you configure SattBot for your server.\n\n"
                "You can set up:\n"
                "- **Command permissions** — who can use what\n"
                "- **Moderation settings** — spam threshold, mute duration, scan depth\n"
                "- **AI config** — choose the AI model\n\n"
                "Click **Start** to begin, or **Skip** to use defaults."
            ),
            color=discord.Color.green(),
        )
        await interaction.response.send_message(
            embed=embed, view=view, ephemeral=True
        )

    # ── /permissions ────────────────────────────────────────────────

    @app_commands.command(
        name="permissions",
        description="Grant or revoke a role's access to a command",
    )
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(
        command="The command to modify",
        action="Grant or Revoke access",
        role="The role to grant/revoke",
    )
    @app_commands.choices(
        action=[
            app_commands.Choice(name="Grant", value="grant"),
            app_commands.Choice(name="Revoke", value="revoke"),
        ]
    )
    async def permissions(
        self,
        interaction: discord.Interaction,
        command: str,
        action: app_commands.Choice[str],
        role: discord.Role,
    ) -> None:
        if command not in CONFIGURABLE_COMMANDS:
            await interaction.response.send_message(
                f"Unknown command `{command}`. Valid: {', '.join(CONFIGURABLE_COMMANDS)}",
                ephemeral=True,
            )
            return

        guild_id = interaction.guild_id
        await self.bot.db.ensure_guild(guild_id)

        if action.value == "grant":
            await self.bot.db.set_command_access(guild_id, command, "restricted")
            await self.bot.db.add_command_role(guild_id, command, role.id)
            await interaction.response.send_message(
                f"Granted **{role.name}** access to `/{command}`. "
                f"Command is now **restricted** (only allowed roles + admins).",
                ephemeral=True,
            )
        else:
            await self.bot.db.remove_command_role(guild_id, command, role.id)
            remaining = await self.bot.db.get_command_roles(guild_id, command)
            if not remaining:
                default = DEFAULT_COMMAND_ACCESS.get(command, "public")
                await self.bot.db.set_command_access(guild_id, command, default)
                await interaction.response.send_message(
                    f"Revoked **{role.name}** from `/{command}`. "
                    f"No roles left — reverted to **{default}**.",
                    ephemeral=True,
                )
            else:
                await interaction.response.send_message(
                    f"Revoked **{role.name}** from `/{command}`. "
                    f"{len(remaining)} role(s) still have access.",
                    ephemeral=True,
                )

    @permissions.autocomplete("command")
    async def permissions_command_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        return [
            app_commands.Choice(name=c, value=c)
            for c in CONFIGURABLE_COMMANDS
            if current.lower() in c.lower()
        ][:25]

    # ── /permissions-view ───────────────────────────────────────────

    @app_commands.command(
        name="permissions-view",
        description="View current command permission settings",
    )
    @app_commands.default_permissions(administrator=True)
    async def permissions_view(self, interaction: discord.Interaction) -> None:
        guild_id = interaction.guild_id
        await self.bot.db.ensure_guild(guild_id)

        defaults = await self.bot.db.get_all_command_defaults(guild_id)
        permissions = await self.bot.db.get_all_command_permissions(guild_id)

        embed = discord.Embed(
            title="Command Permissions",
            color=discord.Color.blurple(),
        )
        for cmd in sorted(defaults):
            access = defaults[cmd]
            roles = permissions.get(cmd, [])
            role_names = []
            for rid in roles:
                r = interaction.guild.get_role(rid)
                role_names.append(r.mention if r else f"(deleted: {rid})")
            value = f"**{access}**"
            if role_names:
                value += f"\nRoles: {', '.join(role_names)}"
            embed.add_field(name=f"/{cmd}", value=value, inline=True)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── /config ─────────────────────────────────────────────────────

    @app_commands.command(
        name="config",
        description="View or change a server setting",
    )
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(
        setting="The setting to change",
        value="The new value",
    )
    @app_commands.choices(
        setting=[
            app_commands.Choice(name="spam_max_msgs", value="spam_max_msgs"),
            app_commands.Choice(name="spam_mute_secs", value="spam_mute_secs"),
            app_commands.Choice(name="scan_limit", value="scan_limit"),
            app_commands.Choice(name="nuke_days", value="nuke_days"),
            app_commands.Choice(name="ai_model", value="ai_model"),
        ]
    )
    async def config_cmd(
        self,
        interaction: discord.Interaction,
        setting: app_commands.Choice[str] | None = None,
        value: str | None = None,
    ) -> None:
        guild_id = interaction.guild_id
        await self.bot.db.ensure_guild(guild_id)
        settings = await self.bot.db.get_guild_settings(guild_id)

        if setting is None:
            # Show all settings
            embed = discord.Embed(
                title="Server Configuration", color=discord.Color.blurple()
            )
            for key in (
                "spam_max_msgs",
                "spam_mute_secs",
                "scan_limit",
                "nuke_days",
                "ai_model",
            ):
                embed.add_field(
                    name=key, value=f"`{settings[key]}`", inline=True
                )
            await interaction.response.send_message(
                embed=embed, ephemeral=True
            )
            return

        if value is None:
            await interaction.response.send_message(
                f"Current value of **{setting.value}**: `{settings[setting.value]}`",
                ephemeral=True,
            )
            return

        # Validate numeric settings
        if setting.value != "ai_model":
            try:
                int_val = int(value)
                if int_val < 1:
                    raise ValueError
                value = int_val
            except ValueError:
                await interaction.response.send_message(
                    f"**{setting.value}** must be a positive integer.",
                    ephemeral=True,
                )
                return

        await self.bot.db.update_guild_setting(guild_id, setting.value, value)
        await interaction.response.send_message(
            f"Updated **{setting.value}** to `{value}`.", ephemeral=True
        )

    # ── /sync (owner-only utility) ──────────────────────────────────

    @app_commands.command(
        name="sync", description="Sync slash commands (bot owner only)"
    )
    @app_commands.default_permissions(administrator=True)
    async def sync_cmd(self, interaction: discord.Interaction) -> None:
        if not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message(
                "Only the bot owner can use this.", ephemeral=True
            )
            return
        await interaction.response.defer(ephemeral=True)
        synced = await self.bot.tree.sync()
        await interaction.followup.send(
            f"Synced {len(synced)} command(s) globally.", ephemeral=True
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Admin(bot))
