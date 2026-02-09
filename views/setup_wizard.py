import logging

import discord

from config import DEFAULT_COMMAND_ACCESS

log = logging.getLogger(__name__)


# ── Step 1: Welcome ─────────────────────────────────────────────────

class SetupWizardStartView(discord.ui.View):
    def __init__(self, db, guild_id: int) -> None:
        super().__init__(timeout=300)
        self.db = db
        self.guild_id = guild_id

    @discord.ui.button(label="Start Setup", style=discord.ButtonStyle.success)
    async def start(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        state: dict = {}
        view = PermissionsStepView(self.db, self.guild_id, state)
        embed = discord.Embed(
            title="Step 1/4 — Command Permissions",
            description=(
                "Choose the access level for each command.\n"
                "- **Public**: everyone can use it\n"
                "- **Admin Only**: only server admins\n"
                "- **Restricted**: only specific roles (configure with `/permissions` after setup)"
            ),
            color=discord.Color.blue(),
        )
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="Skip (Use Defaults)", style=discord.ButtonStyle.secondary)
    async def skip(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await self.db.update_guild_setting(self.guild_id, "setup_complete", 1)
        embed = discord.Embed(
            title="Setup Complete",
            description="Using default settings. You can change them anytime with `/config` and `/permissions`.",
            color=discord.Color.green(),
        )
        await interaction.response.edit_message(embed=embed, view=None)


# ── Step 2: Permissions ─────────────────────────────────────────────

class CommandAccessSelect(discord.ui.Select):
    def __init__(self, command: str, current: str) -> None:
        self.command = command
        options = [
            discord.SelectOption(label="Public", value="public", default=current == "public"),
            discord.SelectOption(label="Admin Only", value="admin_only", default=current == "admin_only"),
            discord.SelectOption(label="Restricted", value="restricted", default=current == "restricted"),
        ]
        super().__init__(
            placeholder=f"/{command}",
            options=options,
            min_values=1,
            max_values=1,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        self.view.access_choices[self.command] = self.values[0]
        await interaction.response.defer()


class PermissionsStepView(discord.ui.View):
    def __init__(self, db, guild_id: int, state: dict) -> None:
        super().__init__(timeout=300)
        self.db = db
        self.guild_id = guild_id
        self.state = state
        self.access_choices: dict[str, str] = dict(DEFAULT_COMMAND_ACCESS)

        for cmd, access in sorted(DEFAULT_COMMAND_ACCESS.items()):
            self.add_item(CommandAccessSelect(cmd, access))

    @discord.ui.button(label="Next", style=discord.ButtonStyle.primary, row=4)
    async def next_step(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        self.state["permissions"] = dict(self.access_choices)
        view = ModerationStepView(self.db, self.guild_id, self.state)
        embed = discord.Embed(
            title="Step 2/4 — Moderation Settings",
            description="Click the button below to configure moderation settings.",
            color=discord.Color.blue(),
        )
        await interaction.response.edit_message(embed=embed, view=view)


# ── Step 3: Moderation settings (modal) ─────────────────────────────

class ModerationModal(discord.ui.Modal, title="Moderation Settings"):
    spam_max = discord.ui.TextInput(
        label="Max messages per minute (spam threshold)",
        default="10",
        required=True,
        max_length=4,
    )
    mute_duration = discord.ui.TextInput(
        label="Mute duration (seconds)",
        default="60",
        required=True,
        max_length=5,
    )
    scan_limit = discord.ui.TextInput(
        label="Message scan limit per channel",
        default="1000",
        required=True,
        max_length=6,
    )
    nuke_days = discord.ui.TextInput(
        label="Inactivity threshold for /nuke (days)",
        default="60",
        required=True,
        max_length=4,
    )

    def __init__(self, state: dict) -> None:
        super().__init__()
        self.state = state
        # Pre-fill with current state if available
        if "moderation" in state:
            self.spam_max.default = str(state["moderation"].get("spam_max_msgs", 10))
            self.mute_duration.default = str(state["moderation"].get("spam_mute_secs", 60))
            self.scan_limit.default = str(state["moderation"].get("scan_limit", 1000))
            self.nuke_days.default = str(state["moderation"].get("nuke_days", 60))

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            self.state["moderation"] = {
                "spam_max_msgs": int(self.spam_max.value),
                "spam_mute_secs": int(self.mute_duration.value),
                "scan_limit": int(self.scan_limit.value),
                "nuke_days": int(self.nuke_days.value),
            }
        except ValueError:
            await interaction.response.send_message(
                "All values must be numbers. Try again.", ephemeral=True
            )
            return
        await interaction.response.defer()


class ModerationStepView(discord.ui.View):
    def __init__(self, db, guild_id: int, state: dict) -> None:
        super().__init__(timeout=300)
        self.db = db
        self.guild_id = guild_id
        self.state = state

    @discord.ui.button(label="Configure Moderation", style=discord.ButtonStyle.primary)
    async def open_modal(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        modal = ModerationModal(self.state)
        await interaction.response.send_modal(modal)
        await modal.wait()
        # After modal, move to AI step
        view = AIStepView(self.db, self.guild_id, self.state)
        embed = discord.Embed(
            title="Step 3/4 — AI Configuration",
            description="Choose the AI model for `/roastme` and other AI features.",
            color=discord.Color.blue(),
        )
        await interaction.edit_original_response(embed=embed, view=view)

    @discord.ui.button(label="Skip (Use Defaults)", style=discord.ButtonStyle.secondary)
    async def skip(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        view = AIStepView(self.db, self.guild_id, self.state)
        embed = discord.Embed(
            title="Step 3/4 — AI Configuration",
            description="Choose the AI model for `/roastme` and other AI features.",
            color=discord.Color.blue(),
        )
        await interaction.response.edit_message(embed=embed, view=view)


# ── Step 4: AI config ───────────────────────────────────────────────

AI_MODELS = [
    ("Llama 3.3 70B (default)", "meta-llama/llama-3.3-70b-instruct"),
    ("Llama 3.1 8B (fast)", "meta-llama/llama-3.1-8b-instruct"),
    ("Mixtral 8x7B", "mistralai/mixtral-8x7b-instruct"),
    ("Qwen 2.5 72B", "qwen/qwen-2.5-72b-instruct"),
]


class AIModelSelect(discord.ui.Select):
    def __init__(self) -> None:
        options = [
            discord.SelectOption(label=name, value=value, default=i == 0)
            for i, (name, value) in enumerate(AI_MODELS)
        ]
        super().__init__(placeholder="Select AI model", options=options)

    async def callback(self, interaction: discord.Interaction) -> None:
        self.view.selected_model = self.values[0]
        await interaction.response.defer()


class AIStepView(discord.ui.View):
    def __init__(self, db, guild_id: int, state: dict) -> None:
        super().__init__(timeout=300)
        self.db = db
        self.guild_id = guild_id
        self.state = state
        self.selected_model = AI_MODELS[0][1]
        self.add_item(AIModelSelect())

    @discord.ui.button(label="Next", style=discord.ButtonStyle.primary, row=1)
    async def next_step(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        self.state["ai_model"] = self.selected_model
        view = ConfirmationView(self.db, self.guild_id, self.state)

        # Build summary
        lines = ["**Permissions:**"]
        perms = self.state.get("permissions", DEFAULT_COMMAND_ACCESS)
        for cmd, access in sorted(perms.items()):
            lines.append(f"  `/{cmd}`: {access}")

        lines.append("\n**Moderation:**")
        mod = self.state.get("moderation", {})
        lines.append(f"  Spam threshold: {mod.get('spam_max_msgs', 10)} msgs/min")
        lines.append(f"  Mute duration: {mod.get('spam_mute_secs', 60)}s")
        lines.append(f"  Scan limit: {mod.get('scan_limit', 1000)} msgs/channel")
        lines.append(f"  Nuke threshold: {mod.get('nuke_days', 60)} days")

        lines.append(f"\n**AI Model:** `{self.state.get('ai_model', AI_MODELS[0][1])}`")

        embed = discord.Embed(
            title="Step 4/4 — Review & Confirm",
            description="\n".join(lines),
            color=discord.Color.blue(),
        )
        await interaction.response.edit_message(embed=embed, view=view)


# ── Step 5: Confirmation ────────────────────────────────────────────

class ConfirmationView(discord.ui.View):
    def __init__(self, db, guild_id: int, state: dict) -> None:
        super().__init__(timeout=300)
        self.db = db
        self.guild_id = guild_id
        self.state = state

    @discord.ui.button(label="Confirm & Save", style=discord.ButtonStyle.success)
    async def confirm(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await interaction.response.defer()

        # Save permissions
        perms = self.state.get("permissions", {})
        for cmd, access in perms.items():
            await self.db.set_command_access(self.guild_id, cmd, access)

        # Save moderation settings
        mod = self.state.get("moderation", {})
        for key, val in mod.items():
            await self.db.update_guild_setting(self.guild_id, key, val)

        # Save AI model
        if "ai_model" in self.state:
            await self.db.update_guild_setting(
                self.guild_id, "ai_model", self.state["ai_model"]
            )

        # Mark setup complete
        await self.db.update_guild_setting(self.guild_id, "setup_complete", 1)

        embed = discord.Embed(
            title="Setup Complete!",
            description=(
                "Your settings have been saved.\n"
                "Use `/config` to change settings and `/permissions` to manage role access."
            ),
            color=discord.Color.green(),
        )
        await interaction.edit_original_response(embed=embed, view=None)

    @discord.ui.button(label="Start Over", style=discord.ButtonStyle.danger)
    async def start_over(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        view = SetupWizardStartView(self.db, self.guild_id)
        embed = discord.Embed(
            title="SattBot Setup Wizard",
            description=(
                "Welcome! This wizard will help you configure SattBot for your server.\n\n"
                "Click **Start** to begin, or **Skip** to use defaults."
            ),
            color=discord.Color.green(),
        )
        await interaction.response.edit_message(embed=embed, view=view)
