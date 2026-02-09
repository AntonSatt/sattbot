import asyncio
import logging
import sys

import discord
from discord.ext import commands

import config
from database import Database

log = logging.getLogger("sattbot")

EXTENSIONS = [
    "cogs.general",
    "cogs.fun",
    "cogs.moderation",
    "cogs.activity",
    "cogs.admin",
    "cogs.listeners",
]


class SattBot(commands.Bot):
    def __init__(self, db: Database) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(command_prefix="!", intents=intents)
        self.db = db

    async def setup_hook(self) -> None:
        await self.db.connect()
        for ext in EXTENSIONS:
            try:
                await self.load_extension(ext)
                log.info("Loaded extension: %s", ext)
            except Exception:
                log.exception("Failed to load extension: %s", ext)
        await self.tree.sync()
        log.info("Slash commands synced globally.")

    async def on_ready(self) -> None:
        log.info("Logged in as %s (ID: %s)", self.user, self.user.id)
        log.info("Connected to %d guild(s)", len(self.guilds))

    async def close(self) -> None:
        await self.db.close()
        await super().close()

    async def on_command_error(
        self, ctx: commands.Context, error: commands.CommandError
    ) -> None:
        # Slash command errors are handled by the tree error handler
        pass


async def main() -> None:
    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if not config.DISCORD_TOKEN:
        log.error("DISCORD_TOKEN not set. Add it to your .env file.")
        sys.exit(1)

    db = Database(config.DATABASE_PATH)
    bot = SattBot(db)

    @bot.tree.error
    async def on_app_command_error(
        interaction: discord.Interaction, error: discord.app_commands.AppCommandError
    ) -> None:
        if isinstance(error, discord.app_commands.CommandOnCooldown):
            await interaction.response.send_message(
                f"Cooldown! Try again in {error.retry_after:.0f}s.",
                ephemeral=True,
            )
        elif isinstance(error, discord.app_commands.CheckFailure):
            await interaction.response.send_message(
                "You don't have permission to use this command.",
                ephemeral=True,
            )
        else:
            log.exception("Unhandled app command error", exc_info=error)
            if interaction.response.is_done():
                await interaction.followup.send(
                    "Something went wrong.", ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    "Something went wrong.", ephemeral=True
                )

    async with bot:
        await bot.start(config.DISCORD_TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
