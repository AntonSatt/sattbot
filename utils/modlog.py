import asyncio
import io
import logging
import random

import aiohttp
import discord

from utils.api import ai_kick_caption, fetch_gif
from utils.formatting import format_member_listing

log = logging.getLogger(__name__)

# Used when OpenRouter isn't configured or doesn't answer
FALLBACK_CAPTIONS = {
    "Nuke": [
        "Tactical nuke deployed. {members} vaporized.",
        "The ghosts have been exorcised: {members} gone.",
        "{members} went AFK and never came back. Now they never will.",
    ],
    "Role Purge": [
        "{members} failed the vibe check: no role, no stay.",
        "Roll call is over. {members} without a role left the building.",
        "Pick a role, they said. {members} did not listen.",
    ],
}
GIF_QUERIES = {
    "Nuke": ["nuke explosion", "mushroom cloud", "explosion"],
    "Role Purge": ["bye bye", "yeet", "see ya"],
}
ICONS = {"Nuke": "☢️", "Role Purge": "\U0001f9f9"}


async def post_kick_log(
    interaction: discord.Interaction,
    action: str,
    reason: str,
    kicked: list[discord.Member],
    failed: int,
    dms: int | None,
) -> None:
    """Post a meme-style summary of a mass kick to the guild's moderation log channel."""
    bot = interaction.client
    guild = interaction.guild
    channel_id = await bot.db.get_modlog_channel(guild.id)
    channel = guild.get_channel(channel_id) if channel_id else None
    if channel is None:
        return

    settings = await bot.db.get_guild_settings(guild.id)
    model = settings["ai_model"] if settings else None
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
        caption, gif = await asyncio.gather(
            ai_kick_caption(session, action, len(kicked), reason, model),
            fetch_gif(session, random.choice(GIF_QUERIES[action])),
        )
    if not caption:
        members = f"{len(kicked)} member" + ("" if len(kicked) == 1 else "s")
        caption = random.choice(FALLBACK_CAPTIONS[action]).format(members=members)

    embed = discord.Embed(
        title=f"{ICONS[action]} {action}: {len(kicked)} kicked",
        description=caption,
        color=discord.Color.red(),
    )
    embed.add_field(name="Initiated by", value=interaction.user.mention)
    if failed:
        embed.add_field(name="Failed", value=str(failed))
    if dms is not None:
        embed.add_field(name="Got the DM", value=str(dms))
    if gif:
        embed.set_image(url=gif)

    listing = discord.File(
        io.BytesIO(format_member_listing(kicked).encode()),
        filename=f"{action.lower().replace(' ', '')}.txt",
    )
    try:
        await channel.send(embed=embed, file=listing)
    except discord.HTTPException as exc:
        log.warning("Cannot post to modlog channel %d: %s", channel.id, exc)
