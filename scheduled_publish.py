"""Publish one verified, monetized AI-tool post for a scheduled GitHub Actions slot."""
from __future__ import annotations

import asyncio
import logging
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

from telegram import Bot

from shrtfly import shorten_with_shrtfly
from tool_catalog import catalog_tools_for_query
from tool_explainer import build_grounded_explanation, hide_direct_links
from tool_post import build_tool_post

logger = logging.getLogger("moradtec-scheduled-publisher")
ALGIERS = ZoneInfo("Africa/Algiers")
SLOTS = ("morning", "afternoon", "evening")
TOOL_ROTATION = ("DeepAI", "Canva AI", "DeepL", "Adobe Firefly", "ElevenLabs", "ChatGPT")


def select_daily_tool(now: datetime, slot: str) -> str:
    """Rotate the curated tool list by local date and daily slot."""
    if slot not in SLOTS:
        raise ValueError(f"Unsupported slot: {slot}")
    local_now = now.astimezone(ALGIERS)
    day_index = local_now.date().toordinal()
    slot_index = SLOTS.index(slot)
    return TOOL_ROTATION[(day_index * len(SLOTS) + slot_index) % len(TOOL_ROTATION)]


async def publish_one(slot: str) -> bool:
    token = os.environ.get("BOT_TOKEN", "").strip()
    channel_id = os.environ.get("CHANNEL_ID", "@MoradTecAI").strip()
    if not token:
        raise RuntimeError("BOT_TOKEN secret is missing")
    if not os.environ.get("SHRTFLY_API_TOKEN", "").strip():
        raise RuntimeError("SHRTFLY_API_TOKEN secret is missing; refusing to publish an unmonetized post")

    # Import the webhook bot's search helpers only at runtime, after secrets are checked.
    from bot import explain_ai_tool, search_ai_tool_sites

    now = datetime.now(ALGIERS)
    query = select_daily_tool(now, slot)
    logger.info("Preparing scheduled %s post for curated topic %s", slot, query)

    # Prefer the exact first-party catalog entry for predictable daily publishing.
    candidates = catalog_tools_for_query(query)
    if not candidates:
        candidates = await search_ai_tool_sites(query)
    if not candidates:
        logger.error("No verified official tool page found; nothing was published")
        return False
    tool = candidates[0]

    explanation = build_grounded_explanation(tool, query)
    if not explanation:
        explanation = await explain_ai_tool(tool)
    if not explanation:
        explanation = (
            "تعرّف على الأداة من موقعها الرسمي، وراجع صفحة المساعدة لمعرفة الوظائف "
            "والخطوات المتاحة حاليًا. لم تتوفر معلومات كافية لتأكيد خطوات أكثر تفصيلًا."
        )

    short_url = await shorten_with_shrtfly(tool["url"])
    if not short_url:
        logger.error("ShrtFly did not return a confirmed short link; skipping publication")
        return False

    post = build_tool_post(
        tool,
        hide_direct_links(explanation),
        short_url,
        shortened=True,
    )
    async with Bot(token=token) as telegram_bot:
        message = await telegram_bot.send_message(
            chat_id=channel_id,
            text=post,
            disable_web_page_preview=False,
        )
    logger.info(
        "Published scheduled post: slot=%s channel=%s message_id=%s tool_host=%s",
        slot,
        channel_id,
        message.message_id,
        __import__("urllib.parse", fromlist=["urlsplit"]).urlsplit(tool["url"]).hostname,
    )
    return True


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    slot = os.environ.get("POST_SLOT", "").strip()
    if slot not in SLOTS:
        logger.error("POST_SLOT must be one of: %s", ", ".join(SLOTS))
        return 2
    try:
        published = asyncio.run(publish_one(slot))
    except Exception:
        logger.exception("Scheduled publishing failed")
        return 1
    return 0 if published else 1


if __name__ == "__main__":
    sys.exit(main())
