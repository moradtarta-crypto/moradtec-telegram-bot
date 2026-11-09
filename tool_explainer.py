"""Deterministic, source-grounded fallback explanations for discovered AI tools."""
from __future__ import annotations

import re
from urllib.parse import urlsplit


DEEPAI_VIDEO_DOCS = "https://deepai.org/docs"
DEEPAI_VIDEO_PAGE = "https://deepai.org/video"


def _deepai_video_explanation(tool: dict) -> str:
    """Use facts verified in DeepAI's official video page and documentation."""
    title = str(tool.get("title") or "DeepAI AI Video Generator")
    return "\n".join([
        f"ما الأداة؟ {title} أداة من DeepAI لإنشاء مقاطع فيديو قصيرة وتحريرها بالذكاء الاصطناعي.",
        "ما الذي تستطيع فعله؟",
        "• إنشاء فيديو من وصف نصي (Text to Video).",
        "• تحويل صورة إلى فيديو (Image to Video)، مع إمكانية توجيه الحركة بوصف نصي.",
        "• تعديل فيديو موجود بإضافة عناصر أو تغييرها أو إزالتها، وتمديد المقطع.",
        "طريقة الاستخدام:",
        "1. افتح صفحة مولّد الفيديو الرسمية: " + DEEPAI_VIDEO_PAGE,
        "2. اختر إنشاء الفيديو من نص، أو ارفع صورة إذا أردت تحريكها.",
        "3. اكتب وصف المشهد والحركة المطلوبة، ثم اختر نمط الجودة والمدة وشكل الفيديو المتاح.",
        "4. راجع الإعدادات والتكلفة قبل الضغط على Generate Video، ثم انتظر تجهيز المقطع.",
        "مثال وصف: لقطة سينمائية لمدينة مستقبلية عند الغروب، سيارات طائرة تتحرك بين الأبراج، والكاميرا تقترب ببطء.",
        "السعر: تتطلب ميزة توليد الفيديو اشتراك DeepAI Pro. تتضمن الخطة شهرياً 25 ثانية HD و8 ثوانٍ في نمط Hollywood؛ وبعد استنفاد المخصص، السعر الإضافي 0.20 دولار/ثانية HD و0.30 دولار/ثانية Hollywood. اشتراك Pro الشهري مذكور بسعر 9.99 دولار.",
        "تنبيه خصوصية مهم: توضح وثائق DeepAI أن رفع الصورة أو الفيديو إلى مولّد الفيديو يمنح الخدمة حق مشاركة الصورة والفيديو علناً؛ لا ترفع محتوى خاصاً أو حساساً.",
        "المراجع الرسمية: " + DEEPAI_VIDEO_DOCS + " | " + DEEPAI_VIDEO_PAGE,
    ])[:2200]


def build_grounded_explanation(tool: dict, query: str = "") -> str | None:
    """Build a concise Arabic guide only from explicit source facts."""
    title = str(tool.get("title", ""))
    description = str(tool.get("description", ""))
    content = str(tool.get("content", ""))
    url = str(tool.get("url", ""))
    source = " ".join((title, description, content))
    normalized = re.sub(r"\s+", " ", source).casefold()
    host = (urlsplit(url).hostname or "").lower()
    task = (query or "").casefold()

    # DeepAI's homepage can be discovered without the detailed video documentation.
    # This fallback is deliberately limited to its official domain and video-related tasks.
    if host in {"deepai.org", "www.deepai.org", "deep.ai", "www.deep.ai"} and any(
        term in task for term in ("فيديو", "video", "مقاطع")
    ):
        return _deepai_video_explanation(tool)

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
    output.append("السعر والحدود: لم تتوفر في النص المفحوص معلومات سعرية مؤكدة؛ راجع صفحة الأسعار الرسمية.")
    return "\n".join(output)[:1700]


def hide_direct_links(explanation: str) -> str:
    """Remove direct URLs and repair link-dependent instructions when a short link is shown."""
    cleaned_lines = []
    for line in explanation.splitlines():
        cleaned = re.sub(r"https?://\S+", "", line).strip()
        cleaned = re.sub(r"\s+\|\s*$", "", cleaned).strip()
        if not cleaned:
            continue
        if re.fullmatch(r"(?:المراجع الرسمية|روابط رسمية|المصادر الرسمية)[:：]?", cleaned):
            continue
        if re.search(r"افتح\s*$", cleaned):
            cleaned = re.sub(r"افتح\s*$", "افتح الأداة من الرابط المختصر الموجود أسفل الشرح.", cleaned)
        elif re.fullmatch(r"(?:\d+[.)]\s*)?افتح (?:صفحة|الموقع|الرابط).{0,100}(?:الرسمية|رسمي)[:：]?", cleaned):
            cleaned = "افتح الأداة من الرابط المختصر الموجود أسفل الشرح."
        cleaned_lines.append(cleaned)
    return "\n".join(cleaned_lines)
