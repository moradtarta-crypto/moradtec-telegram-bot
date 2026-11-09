"""Deterministic, source-grounded fallback explanations for discovered AI tools."""
from __future__ import annotations

import re


def build_grounded_explanation(tool: dict, query: str = "") -> str | None:
    """Build a concise Arabic guide only from capabilities explicitly present in source text."""
    title = str(tool.get("title", ""))
    description = str(tool.get("description", ""))
    content = str(tool.get("content", ""))
    source = " ".join((title, description, content))
    normalized = re.sub(r"\\s+", " ", source).casefold()
    lines = []

    if any(term in normalized for term in (
        "text to video", "text-to-video", "text2video", "from text",
        "videos from text", "video from a text prompt",
    )):
        lines.append("• إنشاء فيديو انطلاقاً من وصف نصي (Text to Video).")
    if any(term in normalized for term in (
        "image to video", "image-to-video", "img2video",
        "animate an image", "images into videos", "from your own images",
    )):
        lines.append("• تحويل صورة إلى فيديو أو تحريكها (Image to Video).")
    if any(term in normalized for term in (
        "video edit", "video editing", "edit an uploaded video",
        "transform your video",
    )):
        lines.append("• تعديل فيديو موجود باستخدام تعليمات نصية.")
    if any(term in normalized for term in (
        "video extend", "extend a clip", "extend video",
    )):
        lines.append("• تمديد مقطع فيديو وإكماله بمحتوى مولّد.")

    if not lines:
        return None

    output = [
        f"ما الأداة؟ {title or 'هذه الأداة'} تقدم وظائف لإنشاء الفيديو بالذكاء الاصطناعي بحسب الصفحة الرسمية.",
        "الوظائف التي يؤكدها المصدر:",
        *lines,
        "طريقة البدء: افتح الموقع الرسمي، ثم اختر نوع الإنشاء المطابق لمدخلاتك (وصف نصي أو صورة). أدخل الوصف أو الصورة المطلوبة واتبع خيارات الموقع الظاهرة؛ لم أضف أسماء أزرار غير مؤكدة.",
    ]

    if "prompt" in normalized and any("Text to Video" in line for line in lines):
        output.append("مثال لوصف نصي: مشهد سينمائي لمدينة مستقبلية عند غروب الشمس، مع حركة كاميرا بطيئة وإضاءة واقعية.")

    if any(term in normalized for term in (
        "share the image and video publicly", "publicly available",
        "shared publicly", "public gallery",
    )):
        output.append("تنبيه خصوصية: يذكر المصدر أن الملفات أو النتائج قد تُشارك علناً؛ تجنب رفع صور أو مقاطع خاصة.")

    output.append("السعر والحدود: راجع صفحة الأسعار الرسمية قبل الاستخدام؛ لم أستنتج أن الخدمة مجانية.")
    return "\n".join(output)[:1700]
