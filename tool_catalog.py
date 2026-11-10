"""Small, curated fallback catalog of verified official AI tool pages."""
from __future__ import annotations

from tool_search import canonical_tool_url, is_relevant_tool, normalize_search_text


# Keep entries limited to official product pages whose purpose and capabilities
# have been checked. Add new entries only with a first-party source URL.
OFFICIAL_TOOL_CATALOG = (
    {
        "title": "DeepAI AI Video Generator",
        "url": "https://deepai.org/video",
        "aliases": ("deepai", "deep ai", "ديب اي", "ديب اي اي"),
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
    {
        "title": "DeepL Translator",
        "url": "https://www.deepl.com/en/translator",
        "aliases": ("deepl", "deep l", "ديب ال", "ديبل"),
        "description": (
            "Official DeepL translation tool for translating text and documents "
            "between supported languages."
        ),
        "content": (
            "DeepL Translator supports text translation and document translation. "
            "The official help center also lists image translation, desktop and "
            "mobile apps, browser extensions, and API access. Available languages "
            "and plan limits can vary; check the official translator and help pages."
        ),
    },
)


def catalog_tools_for_query(query: str) -> list[dict]:
    """Return verified first-party catalog entries relevant to a known task."""
    normalized_query = normalize_search_text(query)
    results = []
    for entry in OFFICIAL_TOOL_CATALOG:
        url = canonical_tool_url(entry["url"])
        if not url:
            continue

        # A direct brand lookup should return that brand's own official product
        # page even when the user enters only the brand name (e.g. /tools DeepAI).
        aliases = tuple(normalize_search_text(alias) for alias in entry.get("aliases", ()))
        direct_brand_match = any(
            normalized_query == alias or normalized_query.startswith(alias + " ")
            for alias in aliases
        )
        task_match = is_relevant_tool(
            query,
            title=entry["title"],
            url=url,
            description=entry["description"],
            content=entry["content"],
        )
        if not direct_brand_match and not task_match:
            continue

        results.append({
            key: value for key, value in {**entry, "url": url}.items()
            if key != "aliases"
        })
    return results
