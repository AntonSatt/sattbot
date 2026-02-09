from __future__ import annotations

import functools
from typing import TYPE_CHECKING

import discord
from discord import app_commands

if TYPE_CHECKING:
    from bot import SattBot


def has_command_permission(command_name: str):
    """App-command check: verifies the invoker has access per the guild's DB config.

    Layers:
      1. DMs or missing guild → deny
      2. Server admins always pass
      3. 'public' → allow everyone
      4. 'admin_only' → deny non-admins
      5. 'restricted' → allow only if user has a listed role
    """

    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.guild is None:
            return False

        if interaction.user.guild_permissions.administrator:
            return True

        bot: SattBot = interaction.client  # type: ignore[assignment]
        guild_id = interaction.guild_id

        access = await bot.db.get_command_access(guild_id, command_name)

        if access == "public":
            return True

        if access == "admin_only":
            return False

        if access == "restricted":
            allowed_roles = await bot.db.get_command_roles(guild_id, command_name)
            user_role_ids = {r.id for r in interaction.user.roles}
            return bool(set(allowed_roles) & user_role_ids)

        return False

    return app_commands.check(predicate)
