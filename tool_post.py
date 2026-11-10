"""Formatting helpers for reviewable AI-tool channel post drafts."""


MAX_LENGTH = 3400


def build_tool_post(tool: dict, explanation: str, destination_url: str) -> str:
    """Build a transparent Arabic promo post without claiming unverified features."""
    title = str(tool.get("title") or "أداة ذكاء اصطناعي").strip()[:160]
    summary = str(tool.get("description") or "").strip()
    guide = str(explanation or "").strip()
    if not guide:
        guide = "افتح الموقع الرسمي وراجع صفحة المساعدة أو الوثائق لمعرفة طريقة الاستخدام؛ لا تتوفر في الصفحة المفحوصة تفاصيل كافية لشرح الخطوات بثقة."
    parts = [
        f"🧰 أداة اليوم: {title}",
        "",
        "🔎 ماذا تقدم؟",
        summary[:500] if summary else "راجع الموقع الرسمي للتعرف على وظائف الأداة الحالية.",
        "",
        "📌 نبذة وطريقة الاستفادة:",
        guide[:1600],
        "",
        f"🌐 جرّب الأداة: {destination_url}",
        "",
        "ℹ️ قد يمر الرابط المختصر بصفحة إعلانية قبل الوصول إلى الموقع الرسمي. تحقق من الأسعار والميزات وسياسة الخصوصية في موقع الأداة قبل الاستخدام.",
        "",
        "#MoradTec #ذكاء_اصطناعي #أدوات_رقمية",
    ]
    return "\n".join(parts)[:MAX_LENGTH]
