"""Deterministic relevance and URL normalization for AI-tool search results."""
from __future__ import annotations

import ipaddress
import re
import unicodedata
from urllib.parse import urlsplit, urlunsplit


TASK_TERMS = {
    "video": {
        "فيديو", "فيديوهات", "مقاطع", "video",
        "ai video", "video generator", "text to video", "image to video",
        "video creation", "video editing",
    },
    "image": {
        "صورة", "صور", "تصميم الصور", "image",
        "ai image", "image generator", "text to image", "image generation",
    },
    "logo": {
        "شعار", "شعارات", "logo",
        "logo maker", "logo generator", "ai logo",
    },
    "voice": {
        "صوت", "تعليق صوتي", "تحويل النص الى صوت", "tts", "text to speech",
        "voice generator", "speech synthesis", "ai voice",
    },
    "music": {
        "موسيقى", "اغاني", "music", "song",
        "ai music", "music generator", "music generation",
    },
    "presentation": {
        "عروض", "تقديمية", "presentation", "slides",
        "ai presentation", "presentation maker", "slide generator",
    },
    "writing": {
        "كتابة", "مقالات", "كتابة المحتوى", "writing",
        "ai writing", "writing assistant", "content generator",
    },
    "coding": {
        "برمجة", "كود", "coding", "code",
        "ai coding", "coding assistant", "code generator",
    },
    "translation": {
        "ترجمة", "translation",
        "ai translation", "translation tool", "machine translation",
    },
    "data": {
        "تحليل البيانات", "بيانات", "data analysis", "data analytics",
        "analytics", "business intelligence", "bi tool",
    },
    "chatbot": {
        "روبوت محادثة", "شات بوت", "chatbot", "chat bot",
        "ai chatbot", "conversational ai",
    },
    "transcription": {
        "تفريغ صوت", "تحويل الصوت الى نص", "transcription",
        "speech to text", "audio to text",
    },
    "research": {
        "بحث", "بحث علمي", "research", "ai research assistant",
        "literature review",
    },
}

PRODUCT_SIGNALS = (
    "generator", "studio", "editor", "assistant", "maker", "create",
    "platform", "software", "tool", "app", "product",
)
DIRECTORY_SIGNALS = (
    "directory", "directories", "best ai tools", "top ai tools",
    "tool directory", "tools list", "product hunt",
)
TRACKING_KEYS = {"fbclid", "gclid", "ref", "source"}


def normalize_search_text(value: str) -> str:
    """Normalize Arabic and Latin text for stable, accent-insensitive matching."""
    value = unicodedata.normalize("NFKC", str(value or "")).casefold()
    value = value.replace("ـ", "")
    value = "".join(
        char for char in value
        if unicodedata.category(char) != "Mn"
    )
    value = re.sub(r"[إأآٱ]", "ا", value)
    value = re.sub(r"ى", "ي", value)
    value = re.sub(r"[^\w\s.+-]", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def task_category(query: str) -> str | None:
    """Return the best known task category for Arabic or English queries."""
    normalized = normalize_search_text(query)
    for category, terms in TASK_TERMS.items():
        if any(normalize_search_text(term) in normalized for term in terms):
            return category
    return None


def canonical_tool_url(url: str) -> str | None:
    """Accept public HTTPS URLs and remove fragments and common tracking data."""
    try:
        parsed = urlsplit(str(url or "").strip())
        if parsed.scheme.lower() != "https" or not parsed.hostname:
            return None
        if parsed.username or parsed.password:
            return None
        host = parsed.hostname.encode("idna").decode("ascii").lower().rstrip(".")
        try:
            address = ipaddress.ip_address(host)
            if not address.is_global:
                return None
        except ValueError:
            if "." not in host or host in {"localhost", "localhost.localdomain"}:
                return None
        if parsed.port not in (None, 443):
            return None
        if host.startswith("www."):
            host = host[4:]
        path = re.sub(r"/{2,}", "/", parsed.path or "/")
        if path != "/":
            path = path.rstrip("/")
        # Search-result parameters are not needed to identify the product page.
        query_parts = []
        for part in parsed.query.split("&"):
            if not part:
                continue
            key = part.split("=", 1)[0].lower()
            if key in TRACKING_KEYS or key.startswith("utm_"):
                continue
            query_parts.append(part)
        query = "&".join(sorted(query_parts))
        return urlunsplit(("https", host, path, query, ""))
    except (UnicodeError, ValueError):
        return None


def _category_evidence(category: str, fields: str) -> bool:
    normalized = normalize_search_text(fields)
    return any(
        normalize_search_text(term) in normalized
        for term in TASK_TERMS[category]
    )


def is_relevant_tool(
    query: str,
    *,
    title: str = "",
    url: str = "",
    description: str = "",
    content: str = "",
) -> bool:
    """Require category evidence in product metadata or meaningful page content."""
    category = task_category(query)
    metadata = " ".join((title, url, description))
    metadata_norm = normalize_search_text(metadata)
    content_norm = normalize_search_text(content[:5000])

    if any(signal in metadata_norm for signal in DIRECTORY_SIGNALS):
        return False

    if category:
        if _category_evidence(category, metadata):
            return True
        # Body evidence is accepted only when metadata also identifies a product.
        has_product_identity = any(
            signal in metadata_norm for signal in PRODUCT_SIGNALS
        )
        return has_product_identity and _category_evidence(category, content_norm)

    query_tokens = {
        token for token in normalize_search_text(query).split()
        if len(token) > 2 and token not in {"the", "for", "with", "and", "من", "في", "عن"}
    }
    metadata_tokens = set(metadata_norm.split())
    overlap = len(query_tokens & metadata_tokens)
    return overlap >= min(2, len(query_tokens)) and any(
        signal in metadata_norm for signal in PRODUCT_SIGNALS
    )


def deduplicate_tool_results(tools: list[dict]) -> list[dict]:
    """Keep the first result for each canonical hostname and product URL."""
    unique = []
    seen_hosts = set()
    seen_urls = set()
    for tool in tools:
        canonical = canonical_tool_url(tool.get("url", ""))
        if not canonical:
            continue
        parsed = urlsplit(canonical)
        host = parsed.hostname or ""
        if host in seen_hosts or canonical in seen_urls:
            continue
        seen_hosts.add(host)
        seen_urls.add(canonical)
        item = dict(tool)
        item["url"] = canonical
        unique.append(item)
    return unique
