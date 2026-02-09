import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

from checks import has_command_permission
from utils.api import ai_roast, fetch_meme
import config


class Fun(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.session: aiohttp.ClientSession | None = None

    async def cog_load(self) -> None:
        self.session = aiohttp.ClientSession()

    async def cog_unload(self) -> None:
        if self.session:
            await self.session.close()

    @app_commands.command(name="meme", description="Get a random meme")
    @app_commands.checks.cooldown(1, 5.0)
    @has_command_permission("meme")
    async def meme(self, interaction: discord.Interaction) -> None:
        if not config.HUMOR_API_KEY:
            await interaction.response.send_message(
                "Meme command is unavailable — no HumorAPI key configured.",
                ephemeral=True,
            )
            return

        await interaction.response.defer()
        data = await fetch_meme(self.session)
        if data is None:
            await interaction.followup.send("Couldn't fetch a meme right now. Try again later.")
            return

        embed = discord.Embed(
            title=data.get("description", "Random Meme"),
            color=discord.Color.orange(),
        )
        embed.set_image(url=data.get("url", ""))
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="roastme", description="Get roasted by AI")
    @app_commands.checks.cooldown(1, 10.0)
    @has_command_permission("roastme")
    async def roastme(self, interaction: discord.Interaction) -> None:
        if not config.OPENROUTER_API_KEY:
            await interaction.response.send_message(
                "Roast command is unavailable — no OpenRouter API key configured.",
                ephemeral=True,
            )
            return

        await interaction.response.defer()
        settings = await self.bot.db.get_guild_settings(interaction.guild_id)
        model = settings["ai_model"] if settings else None
        roast = await ai_roast(self.session, interaction.user.display_name, model)
        if roast is None:
            await interaction.followup.send("The AI is speechless. Try again later.")
            return

        embed = discord.Embed(
            title=f"Roasting {interaction.user.display_name}",
            description=roast,
            color=discord.Color.red(),
        )
        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Fun(bot))
