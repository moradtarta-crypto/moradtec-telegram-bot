"""Small, curated fallback catalog of verified official AI tool pages."""
from __future__ import annotations

from tool_search import canonical_tool_url, is_relevant_tool


# Keep entries limited to official product pages whose purpose and capabilities
# have been checked. Add new entries only with a first-party source URL.
OFFICIAL_TOOL_CATALOG = (
    {
        "title": "DeepAI AI Video Generator",
        "url": "https://deepai.org/video",
        "description": (
            "Official DeepAI video generator. Create videos from text prompts "
            "or images, use reference-to-video, edit clips, and extend videos."
        ),
        "content": (
            "AI Video Generator. Text-to-video: describe a scene and turn words "
            "into a video. Image-to-video: start with a still image and describe "
            "subject or camera movement. Reference-to-video uses reference images. "
            "Video Edit changes elements in an uploaded clip. Video Extend continues "
            "an existing clip. Video generation is part of DeepAI Pro; check the "
            "official page and documentation for current allowances and pricing. "
            "The official documentation warns uploaded images and videos may be "
            "shared publicly."
        ),
    },
)


def catalog_tools_for_query(query: str) -> list[dict]:
    """Return verified first-party catalog entries relevant to a known task."""
    results = []
    for entry in OFFICIAL_TOOL_CATALOG:
        url = canonical_tool_url(entry["url"])
        if not url:
            continue
        if not is_relevant_tool(
            query,
            title=entry["title"],
            url=url,
            description=entry["description"],
            content=entry["content"],
        ):
            continue
        results.append({**entry, "url": url})
    return results
