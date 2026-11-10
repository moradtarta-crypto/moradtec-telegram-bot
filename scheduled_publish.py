"""Publish one verified, monetized AI-tool post with a topic-matched image."""
from __future__ import annotations

import asyncio
import logging
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from datetime import datetime
from io import BytesIO
from zoneinfo import ZoneInfo

from telegram import Bot

from shrtfly import shorten_with_shrtfly
from tool_catalog import catalog_tools_for_query
from tool_explainer import build_grounded_explanation, hide_direct_links

logger = logging.getLogger("moradtec-scheduled-publisher")
ALGIERS = ZoneInfo("Africa/Algiers")
TOOL_ROTATION = (
    "AI video generation",
    "AI translation tools",
    "AI graphic design",
    "AI voice generation",
    "AI writing assistants",
    "AI chat assistants",
    "AI image generation",
    "AI coding assistants",
    "AI music generation",
    "AI presentation makers",
    "AI photo editing",
    "AI transcription tools",
    "AI research assistants",
    "AI website builders",
    "AI logo makers",
    "AI background removers",
    "AI data analysis",
    "AI meeting assistants",
    "AI automation tools",
    "AI language learning",
    "AI document summarizers",
    "AI 3D generation",
    "AI chatbot builders",
    "AI video editing",
)


def select_hourly_topic(now: datetime) -> str:
    """Select a deterministic, rotating topic for each Algiers-local hour."""
    local_now = now.astimezone(ALGIERS)
    hour_index = local_now.date().toordinal() * 24 + local_now.hour
    return TOOL_ROTATION[hour_index % len(TOOL_ROTATION)]


def build_photo_caption(
    tool: dict,
    explanation: str,
    short_url: str,
    shortened: bool,
    attribution: str = "",
) -> str:
    """Build a Telegram photo caption within Telegram's 1024-character limit."""
    title = str(tool.get("title") or "أداة ذكاء اصطناعي").strip()[:120]
    summary = str(tool.get("description") or "اكتشف الأداة من موقعها الرسمي.").strip()[:130]
    guide = " ".join(str(explanation or "").split())[:120]
    parts = [
        f"🧰 {title}",
        "",
        "🔎 ماذا تقدم؟",
        summary,
        "",
        "💡 كيف تستفيد منها؟",
        guide or "افتح الأداة وجرّب الوظائف المتاحة بحسب احتياجك.",
        "",
        f"🌐 جرّب الأداة: {short_url}",
        "",
        "ℹ️ قد يمر الرابط المختصر بصفحة إعلانية قبل الموقع الرسمي."
        if shortened else "ℹ️ رابط الموقع الرسمي.",
    ]
    if attribution:
        parts.extend(["", attribution[:350]])
    caption = "\n".join(parts)
    if len(caption) > 1024:
        excess = len(caption) - 1024
        parts[6] = parts[6][:max(40, len(parts[6]) - excess - 5)] + "…"
        caption = "\n".join(parts)
    return caption[:1024]


async def find_topic_image(topic: str):
    """Use a freely licensed Wikimedia Commons photo; avoid paid image-generation APIs."""
    from bot import find_commons_photo

    photo = await find_commons_photo(topic)
    if photo:
        attribution = (
            f"📷 Wikimedia Commons | المؤلف: {photo['artist'][:90]} | "
            f"الترخيص: {photo['license'][:60]}\nالمصدر: {photo['page'][:120]}"
            + (f"\nرابط الترخيص: {photo['license_url'][:100]}" if photo.get("license_url") else "")
        )
        return {"kind": "commons", **photo, "attribution": attribution}
    return None


def build_ffmpeg_command(input_path: str, output_path: str) -> list[str]:
    """Build a short, silent MP4 with a gentle Ken Burns zoom using local FFmpeg."""
    video_filter = (
        "scale=1280:720:force_original_aspect_ratio=decrease,"
        "pad=1280:720:(ow-iw)/2:(oh-ih)/2,"
        "zoompan=z='min(zoom+0.0008,1.12)':d=150:"
        "x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
        "s=1280x720:fps=25,format=yuv420p"
    )
    return [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-loop", "1", "-i", input_path,
        "-vf", video_filter, "-t", "6", "-an",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "28",
        "-movflags", "+faststart", output_path,
    ]


async def create_free_video(image: dict, timestamp: str) -> BytesIO | None:
    """Turn the selected photo into a six-second MP4 without any paid video API."""
    try:
        if image.get("kind") == "generated":
            image_bytes = image["bytes"]
            suffix = ".png" if image.get("content_type") == "image/png" else ".jpg"
        else:
            import httpx

            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                response = await client.get(image["url"])
                response.raise_for_status()
                image_bytes = response.content
            suffix = ".jpg"

        with tempfile.TemporaryDirectory(prefix="moradtec-video-") as temp_dir:
            input_path = Path(temp_dir) / f"source{suffix}"
            output_path = Path(temp_dir) / "moradtec-post.mp4"
            input_path.write_bytes(image_bytes)
            subprocess.run(
                build_ffmpeg_command(str(input_path), str(output_path)),
                check=True,
                capture_output=True,
                timeout=120,
            )
            video_bytes = output_path.read_bytes()
            if not video_bytes:
                raise RuntimeError("FFmpeg produced an empty video")
        video = BytesIO(video_bytes)
        video.name = f"moradtec-{timestamp}.mp4"
        return video
    except Exception as exc:
        logger.warning("Free FFmpeg video creation failed; will use the source photo: %s", type(exc).__name__)
        return None


async def publish_one() -> bool:
    token = os.environ.get("BOT_TOKEN", "").strip()
    channel_id = os.environ.get("CHANNEL_ID", "").strip() or "@MoradTecAI"
    if not token:
        raise RuntimeError("BOT_TOKEN secret is missing")
    if not os.environ.get("SHRTFLY_API_TOKEN", "").strip():
        raise RuntimeError("SHRTFLY_API_TOKEN secret is missing; refusing to publish an unmonetized post")

    from bot import explain_ai_tool, search_ai_tool_sites

    now = datetime.now(ALGIERS)
    query = select_hourly_topic(now)
    logger.info(
        "Preparing hourly post for Algiers local hour %s; topic=%s",
        now.strftime("%Y-%m-%d %H:00"),
        query,
    )

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
            "افتح الموقع الرسمي وراجع صفحة المساعدة لمعرفة الوظائف والخطوات المتاحة حاليًا. "
            "تحقق من الأسعار والميزات قبل الاستخدام."
        )

    short_url = await shorten_with_shrtfly(tool["url"])
    if not short_url:
        logger.error("ShrtFly did not return a confirmed short link; skipping publication")
        return False

    image = await find_topic_image(f"{tool.get('title', query)} {query}")
    if not image:
        logger.error("No suitable topic image found; skipping publication to preserve image-post quality")
        return False

    attribution = image.get("attribution", "")
    caption = build_photo_caption(
        tool,
        hide_direct_links(explanation),
        short_url,
        shortened=True,
        attribution=attribution,
    )

    video = await create_free_video(image, now.strftime("%Y%m%d-%H"))
    async with Bot(token=token) as telegram_bot:
        if video is not None:
            try:
                message = await telegram_bot.send_video(
                    chat_id=channel_id,
                    video=video,
                    caption=caption,
                    supports_streaming=True,
                )
                media_kind = "free_ffmpeg_video"
            except Exception:
                logger.exception("Telegram video upload failed; falling back to the source photo")
                video = None

        if video is None:
            if image["kind"] == "generated":
                extension = "png" if image["content_type"] == "image/png" else "jpg"
                image_file = BytesIO(image["bytes"])
                image_file.name = f"moradtec-hourly-{now.strftime('%Y%m%d-%H')}.{extension}"
                message = await telegram_bot.send_photo(
                    chat_id=channel_id,
                    photo=image_file,
                    caption=caption,
                )
            else:
                message = await telegram_bot.send_photo(
                    chat_id=channel_id,
                    photo=image["url"],
                    caption=caption,
                )
            media_kind = "photo_fallback"

    logger.info(
        "Published hourly post: channel=%s message_id=%s media=%s image_source=%s tool_host=%s",
        channel_id,
        message.message_id,
        media_kind,
        image["kind"],
        __import__("urllib.parse", fromlist=["urlsplit"]).urlsplit(tool["url"]).hostname,
    )
    return True


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    try:
        published = asyncio.run(publish_one())
    except Exception:
        logger.exception("Hourly scheduled publishing failed")
        return 1
    return 0 if published else 1


if __name__ == "__main__":
    sys.exit(main())
