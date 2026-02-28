import json
import logging
import re
from datetime import datetime, timedelta, timezone

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands, tasks

from checks import has_command_permission
from utils.api import fetch_qotd_feed, fetch_rss_feed

log = logging.getLogger(__name__)

# Strip HTML tags from RSS descriptions
_TAG_RE = re.compile(r"<[^>]+>")

# How long the QOTD poll stays open before the answer is revealed
QOTD_POLL_HOURS = 8


def _strip_html(text: str) -> str:
    """Remove HTML tags and collapse whitespace."""
    text = _TAG_RE.sub("", text)
    return " ".join(text.split())


def _build_daily_embeds(items: list[dict]) -> list[discord.Embed]:
    """Build pretty Discord embeds from today's RSS feed items.

    Each item from the Metacurate feed represents one day's brief.
    We display the main headline as the embed title and list the
    key stories as fields.
    """
    if not items:
        return []

    embeds = []

    for item in items[:5]:  # Limit to 5 items max to avoid spam
        title = item.get("title", "AI & Tech News")
        link = item.get("link", "")
        description = item.get("description", "")
        pub_date = item.get("published_at", "")

        # Parse the description to extract bullet points
        clean_desc = _strip_html(description)

        # Build the embed
        embed = discord.Embed(
            title=title,
            url=link,
            color=discord.Color.from_rgb(88, 101, 242),  # Discord blurple
        )

        # Try to extract main headlines and "also in this brief" sections
        # from the HTML description
        main_headlines = []
        also_items = []
        reading_main = False
        reading_also = False

        for line in description.split("\n"):
            stripped = _strip_html(line).strip()
            if not stripped:
                continue

            if "Main Headlines" in stripped:
                reading_main = True
                reading_also = False
                continue
            elif "Also in this brief" in stripped:
                reading_main = False
                reading_also = True
                continue
            elif "Read the full brief" in stripped:
                reading_main = False
                reading_also = False
                continue

            # Look for list items in HTML
            if "<li>" in line:
                text = _strip_html(line).strip()
                if text:
                    if reading_main:
                        main_headlines.append(text)
                    elif reading_also:
                        also_items.append(text)

        # If we successfully parsed sections, use structured format
        if main_headlines:
            headlines_text = "\n".join(f"> **{i}.** {h}" for i, h in enumerate(main_headlines, 1))
            embed.add_field(
                name="Headlines",
                value=headlines_text[:1024],
                inline=False,
            )

        if also_items:
            also_text = "\n".join(f"> {a}" for a in also_items[:5])
            embed.add_field(
                name="Also In This Brief",
                value=also_text[:1024],
                inline=False,
            )

        # Fallback: if parsing didn't extract anything, show plain description
        if not main_headlines and not also_items:
            if clean_desc:
                embed.description = clean_desc[:2000]

        # Add read more link
        if link:
            embed.add_field(
                name="\u200b",  # invisible separator
                value=f"[Read the full brief on Metacurate.io]({link})",
                inline=False,
            )

        # Footer with source attribution
        if pub_date:
            embed.set_footer(text=f"Source: Metacurate.io | {pub_date}")
        else:
            embed.set_footer(text="Source: Metacurate.io")

        embeds.append(embed)

    return embeds


def _build_qotd_embed(item: dict) -> discord.Embed:
    """Build a pretty Discord embed for a Question of the Day item.

    The QOTD feed items have:
    - title: the date + question
    - description: HTML with a bold answer, explanation paragraphs, and source links
    - link: URL to the full QOTD page
    - published_at: pub date string
    """
    title = item.get("title", "Question of the Day")
    link = item.get("link", "")
    description = item.get("description", "")
    pub_date = item.get("published_at", "")

    # Extract the question from the title (strip the date prefix like "2026-02-27: ")
    question = title
    if ": " in title:
        question = title.split(": ", 1)[1]

    embed = discord.Embed(
        title="Question of the Day",
        url=link,
        color=discord.Color.from_rgb(255, 183, 77),  # Warm amber/orange
    )

    # Add the question as a prominent field
    embed.add_field(
        name="The Question",
        value=f"**{question}**",
        inline=False,
    )

    # Parse the HTML description to extract the answer and sources
    answer_bold = ""
    explanation_parts = []
    sources = []
    reading_sources = False

    for line in description.split("\n"):
        stripped = _strip_html(line).strip()
        if not stripped:
            continue

        # The bold answer is in a <p><strong>...</strong></p> at the top
        if "<strong>" in line and not answer_bold and "Sources" not in stripped:
            answer_bold = _strip_html(line).strip()
            continue

        if "Sources:" in stripped:
            reading_sources = True
            continue

        if "Read on metacurate.io" in stripped:
            continue

        if reading_sources and "<li>" in line:
            # Extract source text and URL
            source_text = _strip_html(line).strip()
            # Try to extract the href for a clickable link
            href_match = re.search(r'href="([^"]+)"', line)
            if href_match and source_text:
                sources.append(f"[{source_text}]({href_match.group(1)})")
            elif source_text:
                sources.append(source_text)
        elif not reading_sources and "<p>" in line:
            para = _strip_html(line).strip()
            if para and para != answer_bold:
                explanation_parts.append(para)

    # Add the short answer
    if answer_bold:
        embed.add_field(
            name="TL;DR",
            value=f"> {answer_bold}"[:1024],
            inline=False,
        )

    # Add the explanation (combine paragraphs, trim to fit)
    if explanation_parts:
        explanation = "\n\n".join(explanation_parts)
        if len(explanation) > 1024:
            explanation = explanation[:1021] + "..."
        embed.add_field(
            name="Details",
            value=explanation,
            inline=False,
        )

    # Add sources
    if sources:
        sources_text = "\n".join(f"> {s}" for s in sources[:4])
        embed.add_field(
            name="Sources",
            value=sources_text[:1024],
            inline=False,
        )

    # Read more link
    if link:
        embed.add_field(
            name="\u200b",
            value=f"[Read on Metacurate.io]({link})",
            inline=False,
        )

    # Footer
    if pub_date:
        embed.set_footer(text=f"Source: Metacurate.io | {pub_date}")
    else:
        embed.set_footer(text="Source: Metacurate.io")

    return embed


def _extract_question(item: dict) -> str:
    """Extract the question text from a QOTD feed item title."""
    title = item.get("title", "Question of the Day")
    # Strip the date prefix like "2026-02-27: "
    if ": " in title:
        return title.split(": ", 1)[1]
    return title


class RSS(commands.Cog):
    """Fetches and posts daily AI & tech news and Question of the Day from Metacurate.io."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.session: aiohttp.ClientSession | None = None

    async def cog_load(self) -> None:
        self.session = aiohttp.ClientSession()
        self.daily_post.start()
        self.daily_qotd.start()
        self.qotd_reveal_check.start()
        self.cleanup_old_items.start()

    async def cog_unload(self) -> None:
        self.daily_post.cancel()
        self.daily_qotd.cancel()
        self.qotd_reveal_check.cancel()
        self.cleanup_old_items.cancel()
        if self.session:
            await self.session.close()

    # -- Background tasks -----------------------------------------------------

    @tasks.loop(hours=24)
    async def daily_post(self) -> None:
        """Fetch today's RSS feed and post it to all configured guilds."""
        await self.bot.wait_until_ready()

        items = await fetch_rss_feed(self.session)
        if not items:
            log.info("RSS daily post: no items returned")
            return

        guilds = await self.bot.db.get_rss_guilds()
        for guild_id, channel_id in guilds:
            # Store items for deduplication / history
            count = await self.bot.db.store_rss_items(guild_id, items)
            log.info("RSS: stored %d new items for guild %d", count, guild_id)

            # Post the news
            await self._post_daily_news(guild_id, channel_id, items)

    @daily_post.before_loop
    async def before_daily_post(self) -> None:
        await self.bot.wait_until_ready()

    @tasks.loop(hours=24)
    async def daily_qotd(self) -> None:
        """Fetch today's QOTD and post it as a poll to all configured guilds."""
        await self.bot.wait_until_ready()

        items = await fetch_qotd_feed(self.session)
        if not items:
            log.info("QOTD daily post: no items returned")
            return

        guilds = await self.bot.db.get_qotd_guilds()
        for guild_id, channel_id in guilds:
            await self._post_qotd_poll(guild_id, channel_id, items)

    @daily_qotd.before_loop
    async def before_daily_qotd(self) -> None:
        await self.bot.wait_until_ready()

    @tasks.loop(minutes=15)
    async def qotd_reveal_check(self) -> None:
        """Check for QOTD polls that are ready for their answer reveal."""
        await self.bot.wait_until_ready()

        pending = await self.bot.db.get_pending_qotd_reveals()
        for poll_row in pending:
            await self._reveal_qotd_answer(poll_row)

    @qotd_reveal_check.before_loop
    async def before_qotd_reveal_check(self) -> None:
        await self.bot.wait_until_ready()

    @tasks.loop(hours=168)  # weekly cleanup
    async def cleanup_old_items(self) -> None:
        """Delete RSS items older than 30 days and old revealed polls."""
        await self.bot.wait_until_ready()
        deleted = await self.bot.db.delete_old_rss_items(30)
        if deleted:
            log.info("RSS cleanup: deleted %d old items", deleted)
        deleted_polls = await self.bot.db.cleanup_old_qotd_polls(7)
        if deleted_polls:
            log.info("QOTD cleanup: deleted %d old revealed polls", deleted_polls)

    @cleanup_old_items.before_loop
    async def before_cleanup(self) -> None:
        await self.bot.wait_until_ready()

    # -- Helpers --------------------------------------------------------------

    async def _post_daily_news(
        self, guild_id: int, channel_id: int, items: list[dict]
    ) -> None:
        """Format and send the daily news embeds to the configured channel."""
        guild = self.bot.get_guild(guild_id)
        if guild is None:
            log.warning("RSS: guild %d not found, skipping post", guild_id)
            return

        channel = guild.get_channel(channel_id)
        if channel is None:
            log.warning(
                "RSS: channel %d not found in guild %d, skipping",
                channel_id,
                guild_id,
            )
            return

        # Only post the latest item (today's brief)
        embeds = _build_daily_embeds(items[:1])
        if not embeds:
            log.info("RSS: no embeds to post for guild %d", guild_id)
            return

        try:
            for embed in embeds:
                await channel.send(embed=embed)
            log.info("RSS: posted daily news to guild %d", guild_id)
        except discord.Forbidden:
            log.warning(
                "RSS: missing permissions to post in channel %d (guild %d)",
                channel_id,
                guild_id,
            )

    async def _post_qotd_poll(
        self, guild_id: int, channel_id: int, items: list[dict]
    ) -> discord.Message | None:
        """Send today's QOTD as a Discord poll and schedule the answer reveal."""
        guild = self.bot.get_guild(guild_id)
        if guild is None:
            log.warning("QOTD: guild %d not found, skipping post", guild_id)
            return None

        channel = guild.get_channel(channel_id)
        if channel is None:
            log.warning(
                "QOTD: channel %d not found in guild %d, skipping",
                channel_id,
                guild_id,
            )
            return None

        if not items:
            log.info("QOTD: no items to post for guild %d", guild_id)
            return None

        item = items[0]
        question = _extract_question(item)

        # Build a Discord poll with fixed answer choices
        poll = discord.Poll(
            question=question[:300],  # Discord poll question limit
            duration=timedelta(hours=QOTD_POLL_HOURS),
        )
        poll.add_answer(text="Yes", emoji="\U0001f44d")          # 👍
        poll.add_answer(text="No", emoji="\U0001f44e")            # 👎
        poll.add_answer(text="It's Complicated", emoji="\U0001f914")  # 🤔

        try:
            msg = await channel.send(
                content="**Question of the Day** \U00002753",  # ❓
                poll=poll,
            )
            log.info("QOTD: posted poll to guild %d (msg %d)", guild_id, msg.id)
        except discord.Forbidden:
            log.warning(
                "QOTD: missing permissions to post in channel %d (guild %d)",
                channel_id,
                guild_id,
            )
            return None

        # Calculate the reveal time and save to DB
        reveal_at = datetime.now(timezone.utc) + timedelta(hours=QOTD_POLL_HOURS)
        await self.bot.db.save_qotd_poll(
            guild_id=guild_id,
            channel_id=channel_id,
            message_id=msg.id,
            question=question,
            answer_data=json.dumps(item),
            reveal_at=reveal_at.strftime("%Y-%m-%d %H:%M:%S"),
        )

        return msg

    async def _reveal_qotd_answer(self, poll_row: dict) -> None:
        """Post the answer embed as a reply to the original poll message."""
        guild = self.bot.get_guild(poll_row["guild_id"])
        if guild is None:
            log.warning(
                "QOTD reveal: guild %d not found, marking revealed",
                poll_row["guild_id"],
            )
            await self.bot.db.mark_qotd_revealed(poll_row["id"])
            return

        channel = guild.get_channel(poll_row["channel_id"])
        if channel is None:
            log.warning(
                "QOTD reveal: channel %d not found, marking revealed",
                poll_row["channel_id"],
            )
            await self.bot.db.mark_qotd_revealed(poll_row["id"])
            return

        # Build the answer embed from the stored feed item data
        item = json.loads(poll_row["answer_data"])
        embed = _build_qotd_embed(item)
        embed.title = "Answer Reveal"

        try:
            # Try to reply to the original poll message
            try:
                poll_msg = await channel.fetch_message(poll_row["message_id"])
                await poll_msg.reply(embed=embed)
            except discord.NotFound:
                # Poll message was deleted; post standalone
                await channel.send(
                    content=f"**Answer Reveal** for: *{poll_row['question'][:200]}*",
                    embed=embed,
                )
            log.info(
                "QOTD reveal: posted answer for guild %d (poll msg %d)",
                poll_row["guild_id"],
                poll_row["message_id"],
            )
        except discord.Forbidden:
            log.warning(
                "QOTD reveal: missing permissions in channel %d (guild %d)",
                poll_row["channel_id"],
                poll_row["guild_id"],
            )

        await self.bot.db.mark_qotd_revealed(poll_row["id"])

    # -- Slash commands -------------------------------------------------------

    @app_commands.command(
        name="rss-channel",
        description="Set or view the channel for daily AI & tech news",
    )
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(channel="The channel to post daily news in (omit to view current)")
    @has_command_permission("rss-channel")
    async def rss_channel(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel | None = None,
    ) -> None:
        guild_id = interaction.guild_id
        await self.bot.db.ensure_guild(guild_id)

        if channel is None:
            current = await self.bot.db.get_rss_channel(guild_id)
            if current is None:
                await interaction.response.send_message(
                    "No daily news channel configured. "
                    "Use `/rss-channel #channel` to set one.",
                    ephemeral=True,
                )
            else:
                await interaction.response.send_message(
                    f"Daily AI & tech news is posted to <#{current}>.",
                    ephemeral=True,
                )
            return

        await self.bot.db.set_rss_channel(guild_id, channel.id)
        await interaction.response.send_message(
            f"Daily AI & tech news will now be posted to {channel.mention}.",
            ephemeral=True,
        )

    @app_commands.command(
        name="qotd-channel",
        description="Set or view the channel for the daily Question of the Day",
    )
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(channel="The channel to post QOTD in (omit to view current)")
    @has_command_permission("qotd-channel")
    async def qotd_channel(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel | None = None,
    ) -> None:
        guild_id = interaction.guild_id
        await self.bot.db.ensure_guild(guild_id)

        if channel is None:
            current = await self.bot.db.get_qotd_channel(guild_id)
            if current is None:
                await interaction.response.send_message(
                    "No QOTD channel configured. "
                    "Use `/qotd-channel #channel` to set one.",
                    ephemeral=True,
                )
            else:
                await interaction.response.send_message(
                    f"Question of the Day is posted to <#{current}>.",
                    ephemeral=True,
                )
            return

        await self.bot.db.set_qotd_channel(guild_id, channel.id)
        await interaction.response.send_message(
            f"Question of the Day will now be posted to {channel.mention}.",
            ephemeral=True,
        )

    @app_commands.command(
        name="rss-fetch",
        description="Manually fetch and post today's news now (for testing)",
    )
    @app_commands.default_permissions(administrator=True)
    @has_command_permission("rss-fetch")
    async def rss_fetch(self, interaction: discord.Interaction) -> None:
        guild_id = interaction.guild_id
        await self.bot.db.ensure_guild(guild_id)

        rss_channel = await self.bot.db.get_rss_channel(guild_id)
        if rss_channel is None:
            await interaction.response.send_message(
                "No RSS channel configured yet. Use `/rss-channel #channel` first.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        items = await fetch_rss_feed(self.session)
        if not items:
            await interaction.followup.send(
                "RSS fetch returned no items. The feed may be temporarily unavailable.",
                ephemeral=True,
            )
            return

        count = await self.bot.db.store_rss_items(guild_id, items)

        # Post the news to the configured channel
        await self._post_daily_news(guild_id, rss_channel, items)

        await interaction.followup.send(
            f"Fetched **{len(items)}** article(s) from Metacurate.io -- "
            f"**{count}** new item(s) stored. News posted to <#{rss_channel}>.",
            ephemeral=True,
        )

    @app_commands.command(
        name="dailynews",
        description="Get today's AI & tech news on demand",
    )
    @app_commands.checks.cooldown(1, 30.0)
    @has_command_permission("dailynews")
    async def daily_news_cmd(self, interaction: discord.Interaction) -> None:
        guild_id = interaction.guild_id
        await self.bot.db.ensure_guild(guild_id)

        await interaction.response.defer()

        items = await fetch_rss_feed(self.session)
        if not items:
            await interaction.followup.send(
                "Could not fetch the news feed right now. Try again later.",
                ephemeral=True,
            )
            return

        embeds = _build_daily_embeds(items[:1])
        if not embeds:
            await interaction.followup.send(
                "No news articles available right now.",
                ephemeral=True,
            )
            return

        for embed in embeds:
            await interaction.followup.send(embed=embed)

    @app_commands.command(
        name="qotd",
        description="Post today's Question of the Day as a poll",
    )
    @app_commands.checks.cooldown(1, 30.0)
    @has_command_permission("qotd")
    async def qotd_cmd(self, interaction: discord.Interaction) -> None:
        guild_id = interaction.guild_id
        await self.bot.db.ensure_guild(guild_id)

        await interaction.response.defer()

        items = await fetch_qotd_feed(self.session)
        if not items:
            await interaction.followup.send(
                "Could not fetch the QOTD feed right now. Try again later.",
                ephemeral=True,
            )
            return

        # Post the poll to the channel where the command was used
        msg = await self._post_qotd_poll(
            guild_id, interaction.channel_id, items
        )
        if msg:
            await interaction.followup.send(
                f"QOTD poll posted! The answer will be revealed in {QOTD_POLL_HOURS} hours.",
                ephemeral=True,
            )
        else:
            await interaction.followup.send(
                "Failed to post the QOTD poll. Check bot permissions.",
                ephemeral=True,
            )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(RSS(bot))
