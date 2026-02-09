import logging

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
