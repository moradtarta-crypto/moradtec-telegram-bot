"""Conservative relevance checks for Commons images used in automated tool posts."""
from __future__ import annotations

import re
import unicodedata


_STOPWORDS = {
    "about", "from", "with", "that", "this", "your", "into", "using",
    "tool", "tools", "photo", "image", "images", "technology", "digital",
    "artificial", "intelligence", "assistant", "online", "free", "the",
    "and", "for", "how", "make", "maker", "generation", "generator",
    "ai", "of", "in", "to", "a", "an",
}


def _tokens(value: str) -> set[str]:
    normalized = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return {
        token for token in re.findall(r"[a-z0-9\u0600-\u06ff]+", normalized)
        if len(token) >= 4 and token not in _STOPWORDS
    }


def commons_image_matches_topic(topic: str, image_title: str) -> bool:
    """Require at least two meaningful shared terms; one generic word is not enough."""
    topic_tokens = _tokens(topic)
    image_tokens = _tokens(image_title.replace("_", " "))
    return len(topic_tokens & image_tokens) >= 2
