import logging

import discord

log = logging.getLogger(__name__)


class NukeConfirmView(discord.ui.View):
    def __init__(
        self, author: discord.Member, targets: list[discord.Member]
    ) -> None:
        super().__init__(timeout=60)
        self.author = author
        self.targets = targets

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.author.id

    @discord.ui.button(label="Confirm Nuke", style=discord.ButtonStyle.danger, emoji="\u2622\ufe0f")
    async def confirm(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        kicked = 0
        failed = 0
        for member in self.targets:
            try:
                await member.kick(reason=f"Nuke: inactive — initiated by {self.author}")
                kicked += 1
            except discord.Forbidden:
                failed += 1
                log.warning("Cannot kick %s — missing permissions", member)

        self.stop()
        for child in self.children:
            child.disabled = True
        await interaction.edit_original_response(view=self)
        await interaction.followup.send(
            f"Nuke complete: **{kicked}** kicked, **{failed}** failed.",
            ephemeral=True,
        )

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        self.stop()
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(content="Nuke cancelled.", view=self)
