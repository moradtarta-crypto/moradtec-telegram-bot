"""Small, curated fallback catalog of verified official AI tool pages."""
from __future__ import annotations

from tool_search import canonical_tool_url, is_relevant_tool, normalize_search_text


# Keep entries limited to first-party product pages. Descriptions state only
# broadly documented capabilities; users should verify current plan limits.
OFFICIAL_TOOL_CATALOG = (
    {
        "title": "DeepAI AI Video Generator",
        "url": "https://deepai.org/video",
        "aliases": ("deepai", "deep ai", "ديب اي", "ديب اي اي"),
        "description": "Official DeepAI video generator for creating and editing AI videos.",
        "content": (
            "AI Video Generator. Text-to-video turns a written scene description into a video. "
            "Image-to-video starts from a still image. Video Edit changes elements in an uploaded "
            "clip, and Video Extend continues an existing clip. Check the official page for current "
            "availability, plan limits, pricing, and privacy terms."
        ),
    },
    {
        "title": "DeepL Translator",
        "url": "https://www.deepl.com/en/translator",
        "aliases": ("deepl", "deep l", "ديب ال", "ديبل"),
        "description": "Official DeepL translation tool for text and supported documents.",
        "content": (
            "DeepL Translator supports text translation and document translation between supported "
            "languages. Available languages, file types, and plan limits can vary; check the official "
            "translator and help pages for current details."
        ),
    },
    {
        "title": "Canva AI",
        "url": "https://www.canva.com/ai/",
        "aliases": ("canva ai", "canva", "كانفا"),
        "description": "Canva AI brings AI-assisted design and content creation features into Canva.",
        "content": (
            "Canva AI provides AI-assisted design and content creation features within Canva. "
            "Available tools and usage limits depend on product availability and plan. Check the "
            "official Canva AI page for the current feature set and terms."
        ),
    },
    {
        "title": "Adobe Firefly",
        "url": "https://firefly.adobe.com/",
        "aliases": ("adobe firefly", "firefly", "فايرفلاي"),
        "description": "Adobe Firefly is Adobe's generative AI creative tool for images and other media.",
        "content": (
            "Adobe Firefly is a generative AI creative tool. The Firefly web app provides generation "
            "and editing workflows for supported creative media. Features, generative credits, and "
            "commercial-use terms vary; consult Adobe's official product and terms pages."
        ),
    },
    {
        "title": "ElevenLabs",
        "url": "https://elevenlabs.io/",
        "aliases": ("elevenlabs", "eleven labs", "إليفن لابس"),
        "description": "ElevenLabs offers AI audio tools including text-to-speech and voice generation.",
        "content": (
            "ElevenLabs provides AI audio tools, including text-to-speech and voice generation. "
            "Voice cloning and other features may require consent and are subject to platform rules. "
            "Check the official site for supported languages, usage limits, and pricing."
        ),
    },
    {
        "title": "Zapier AI Workflows",
        "url": "https://zapier.com/automations",
        "aliases": ("zapier", "zapier ai", "ai automation", "ai automation tools", "أتمتة الذكاء الاصطناعي"),
        "description": "Zapier connects apps and automates workflows, including AI-powered steps and agents.",
        "content": (
            "Zapier Workflows connect apps through triggers and actions. AI features can help build "
            "workflows, summarize and classify information, and route tasks across connected apps. "
            "Available features and task limits depend on the plan; check Zapier's official pages "
            "for current availability and pricing."
        ),
    },
    {
        "title": "ChatGPT",
        "url": "https://chatgpt.com/",
        "aliases": (
            "chatgpt", "chat gpt", "شات جي بي تي", "ai language learning",
            "language learning", "language practice", "تعلم اللغات بالذكاء الاصطناعي",
        ),
        "description": "ChatGPT can support language practice through conversation, vocabulary explanations, and learning exercises.",
        "content": (
            "ChatGPT is an AI assistant that can support language learning when prompted to practice "
            "conversations, explain vocabulary or grammar, translate examples, and create learning "
            "exercises. Learners should verify important translations and corrections. Available "
            "features, voice access, and usage limits vary by plan and may change; check the official "
            "site for current features and terms."
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
