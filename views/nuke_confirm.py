import logging

import discord

from utils.modlog import post_kick_log

log = logging.getLogger(__name__)


class NukeConfirmView(discord.ui.View):
    def __init__(
        self,
        author: discord.Member,
        targets: list[discord.Member],
        action: str = "Nuke",
        reason: str = "Nuke: inactive",
        dm_text: str | None = None,
    ) -> None:
        # Long enough to read the list and its attachment before confirming
        super().__init__(timeout=300)
        self.author = author
        self.targets = targets
        self.action = action
        self.reason = reason
        self.dm_text = dm_text
        self.confirm.label = f"Confirm {action}"

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.author.id

    @discord.ui.button(label="Confirm Nuke", style=discord.ButtonStyle.danger, emoji="☢️")
    async def confirm(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        # Disable the buttons first so a second click can't start another run
        self.stop()
        for child in self.children:
            child.disabled = True
        await interaction.edit_original_response(view=self)

        kicked: list[discord.Member] = []
        failed = 0
        dms = 0
        for member in self.targets:
            if self.dm_text:
                # Must happen before the kick: afterwards there is no shared server
                try:
                    await member.send(self.dm_text)
                    dms += 1
                except discord.HTTPException:
                    log.info("Cannot DM %s, kicking anyway", member)
            try:
                await member.kick(reason=f"{self.reason}, initiated by {self.author}")
                kicked.append(member)
            except discord.HTTPException as exc:
                failed += 1
                log.warning("Cannot kick %s: %s", member, exc)

        summary = f"{self.action} complete: **{len(kicked)}** kicked, **{failed}** failed."
        if self.dm_text:
            summary += f" **{dms}** got the DM."
        await interaction.followup.send(summary, ephemeral=True)

        if kicked:
            await post_kick_log(
                interaction,
                self.action,
                self.reason,
                kicked,
                failed,
                dms if self.dm_text else None,
            )

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        self.stop()
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(content=f"{self.action} cancelled.", view=self)
