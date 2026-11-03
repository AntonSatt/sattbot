import io
from datetime import datetime, timedelta

import discord

from utils.formatting import format_member_list, format_member_listing, make_embed
from views.nuke_confirm import NukeConfirmView


def members_without_roles(
    members: list[discord.Member],
    keep_role_ids: set[int],
    joined_before: datetime,
    exclude_ids: set[int],
) -> list[discord.Member]:
    """Members who hold none of keep_role_ids.

    Bots, admins, members who joined after joined_before (or whose join date
    is unknown) and exclude_ids are never included.
    """
    return [
        m
        for m in members
        if not m.bot
        and m.id not in exclude_ids
        and not m.guild_permissions.administrator
        and m.joined_at is not None
        and m.joined_at <= joined_before
        and not any(r.id in keep_role_ids for r in m.roles)
    ]


class RolePurgeView(discord.ui.View):
    def __init__(
        self, author: discord.Member, grace_days: int, dm_text: str
    ) -> None:
        super().__init__(timeout=120)
        self.author = author
        self.grace_days = grace_days
        self.dm_text = dm_text

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.author.id

    @discord.ui.select(
        cls=discord.ui.RoleSelect,
        placeholder="Roles that let a member stay",
        min_values=1,
        max_values=25,
    )
    async def keep_roles(
        self, interaction: discord.Interaction, select: discord.ui.RoleSelect
    ) -> None:
        self.stop()
        guild = interaction.guild
        joined_before = discord.utils.utcnow() - timedelta(days=self.grace_days)
        candidates = members_without_roles(
            guild.members,
            {r.id for r in select.values},
            joined_before,
            {self.author.id, guild.owner_id},
        )
        # Discord only lets the bot kick members whose top role is below its own
        targets = [m for m in candidates if m.top_role < guild.me.top_role]
        blocked = len(candidates) - len(targets)
        blocked_note = (
            f"\n{blocked} member(s) with a role above the bot's can't be kicked."
            if blocked
            else ""
        )

        if not targets:
            await interaction.response.edit_message(
                content="No members to remove!" + blocked_note, view=None
            )
            return

        roles = ", ".join(r.mention for r in select.values)
        embed = make_embed(
            title=f"Role Purge Confirmation: {len(targets)} members",
            description=(
                f"This will kick **{len(targets)}** members who have none of "
                f"{roles} and joined more than **{self.grace_days}** days ago. "
                f"The full list is attached.{blocked_note}\n\n"
                + format_member_list(targets)
            ),
            color=discord.Color.red(),
        )
        embed.add_field(name="DM sent before the kick", value=self.dm_text[:1024])

        listing = discord.File(
            io.BytesIO(format_member_listing(targets).encode()),
            filename="rolepurge.txt",
        )
        view = NukeConfirmView(
            self.author,
            targets,
            action="Role Purge",
            reason="Role purge: none of the kept roles",
            dm_text=self.dm_text,
        )
        await interaction.response.edit_message(
            content=None, embed=embed, attachments=[listing], view=view
        )
