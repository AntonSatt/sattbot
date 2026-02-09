import discord

from config import DEFAULT_COMMAND_ACCESS


class CommandAccessSelect(discord.ui.Select):
    """Dropdown to pick access level for a single command."""

    def __init__(self, command: str, current: str) -> None:
        self.command = command
        options = [
            discord.SelectOption(
                label="Public",
                value="public",
                description="Everyone can use this command",
                default=current == "public",
            ),
            discord.SelectOption(
                label="Admin Only",
                value="admin_only",
                description="Only server admins",
                default=current == "admin_only",
            ),
            discord.SelectOption(
                label="Restricted",
                value="restricted",
                description="Only specific roles (set with /permissions)",
                default=current == "restricted",
            ),
        ]
        super().__init__(
            placeholder=f"/{command} access level",
            options=options,
            min_values=1,
            max_values=1,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        self.view.choices[self.command] = self.values[0]
        await interaction.response.defer()


class PermissionsView(discord.ui.View):
    """View to set access levels for multiple commands during setup."""

    def __init__(self, current_defaults: dict[str, str]) -> None:
        super().__init__(timeout=300)
        self.choices: dict[str, str] = dict(current_defaults)
        self.confirmed = False

        for cmd, access in sorted(current_defaults.items()):
            self.add_item(CommandAccessSelect(cmd, access))

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.success, row=4)
    async def confirm(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        self.confirmed = True
        self.stop()
        await interaction.response.defer()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, row=4)
    async def cancel(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        self.stop()
        await interaction.response.defer()
