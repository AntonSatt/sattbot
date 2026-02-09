import discord


def make_embed(
    title: str,
    description: str = "",
    color: discord.Color = discord.Color.blurple(),
    **kwargs,
) -> discord.Embed:
    embed = discord.Embed(title=title, description=description, color=color, **kwargs)
    return embed


def format_member_list(members: list[discord.Member], limit: int = 20) -> str:
    """Format a list of members as a numbered markdown list."""
    lines = []
    for i, m in enumerate(members[:limit], 1):
        lines.append(f"{i}. {m.mention} ({m.display_name})")
    if len(members) > limit:
        lines.append(f"... and {len(members) - limit} more")
    return "\n".join(lines) if lines else "None"


def format_leaderboard(
    entries: list[tuple[discord.Member, int]], limit: int = 10
) -> str:
    """Format a leaderboard of (member, count) tuples."""
    lines = []
    medals = {1: "\U0001f947", 2: "\U0001f948", 3: "\U0001f949"}
    for i, (member, count) in enumerate(entries[:limit], 1):
        prefix = medals.get(i, f"{i}.")
        lines.append(f"{prefix} {member.mention} — **{count}** messages")
    return "\n".join(lines) if lines else "No data"
