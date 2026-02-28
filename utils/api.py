import logging
import xml.etree.ElementTree as ET

import aiohttp

import config

log = logging.getLogger(__name__)


async def fetch_meme(session: aiohttp.ClientSession) -> dict | None:
    """Fetch a random meme from HumorAPI. Returns dict with 'url' and 'description', or None."""
    if not config.HUMOR_API_KEY:
        return None
    params = {"api-key": config.HUMOR_API_KEY, "media-type": "image"}
    try:
        async with session.get(config.HUMOR_API_URL, params=params) as resp:
            if resp.status == 200:
                return await resp.json()
            log.warning("HumorAPI returned status %d", resp.status)
            return None
    except Exception:
        log.exception("HumorAPI request failed")
        return None


async def ai_roast(
    session: aiohttp.ClientSession,
    username: str,
    model: str | None = None,
) -> str | None:
    """Get an AI-generated roast from OpenRouter. Returns the text or None."""
    if not config.OPENROUTER_API_KEY:
        return None
    model = model or config.DEFAULT_AI_MODEL
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a savage roast comedian. Roast the user in 2-3 sentences. "
                    "Be funny and creative but not hateful or bigoted."
                ),
            },
            {
                "role": "user",
                "content": f"Roast me! My name is {username}.",
            },
        ],
    }
    headers = {
        "Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    try:
        async with session.post(
            config.OPENROUTER_API_URL, json=payload, headers=headers
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data["choices"][0]["message"]["content"]
            log.warning("OpenRouter returned status %d", resp.status)
            return None
    except Exception:
        log.exception("OpenRouter request failed")
        return None


async def fetch_rss_feed(session: aiohttp.ClientSession) -> list[dict]:
    """Fetch and parse the Metacurate RSS feed. Returns a list of item dicts."""
    try:
        async with session.get(config.METACURATE_RSS_URL) as resp:
            if resp.status != 200:
                log.warning("RSS feed returned status %d", resp.status)
                return []
            text = await resp.text()
    except Exception:
        log.exception("RSS feed request failed")
        return []

    items = []
    try:
        root = ET.fromstring(text)
        # Standard RSS 2.0 structure: <rss><channel><item>...</item></channel></rss>
        channel = root.find("channel")
        if channel is None:
            log.warning("RSS feed has no <channel> element")
            return []
        for item_el in channel.findall("item"):
            title = item_el.findtext("title", "")
            link = item_el.findtext("link", "")
            description = item_el.findtext("description", "")
            pub_date = item_el.findtext("pubDate", "")
            if link:
                items.append({
                    "title": title,
                    "link": link,
                    "description": description,
                    "published_at": pub_date,
                })
    except ET.ParseError:
        log.exception("Failed to parse RSS XML")
        return []

    return items


async def fetch_qotd_feed(session: aiohttp.ClientSession) -> list[dict]:
    """Fetch and parse the Metacurate Question of the Day RSS feed."""
    try:
        async with session.get(config.METACURATE_QOTD_URL) as resp:
            if resp.status != 200:
                log.warning("QOTD feed returned status %d", resp.status)
                return []
            text = await resp.text()
    except Exception:
        log.exception("QOTD feed request failed")
        return []

    items = []
    try:
        root = ET.fromstring(text)
        channel = root.find("channel")
        if channel is None:
            log.warning("QOTD feed has no <channel> element")
            return []
        for item_el in channel.findall("item"):
            title = item_el.findtext("title", "")
            link = item_el.findtext("link", "")
            description = item_el.findtext("description", "")
            pub_date = item_el.findtext("pubDate", "")
            if link:
                items.append({
                    "title": title,
                    "link": link,
                    "description": description,
                    "published_at": pub_date,
                })
    except ET.ParseError:
        log.exception("Failed to parse QOTD XML")
        return []

    return items

