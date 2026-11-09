import hashlib
import logging
import os
import re
import html

import httpx
from urllib.parse import urlsplit

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("moradtec-bot")

# Avoid logging Telegram API request URLs, which may contain the bot token.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

BOT_TOKEN = os.environ["BOT_TOKEN"]
OWNER_ID_RAW = os.getenv("OWNER_ID", "").strip()
CHANNEL_ID = os.getenv("CHANNEL_ID", "@MoradTecAI")
OWNER_ID = int(OWNER_ID_RAW) if OWNER_ID_RAW.isdigit() else None
MAX_POST_LENGTH = 3500
MAX_CAPTION_LENGTH = 1024
MAX_LINK_BUTTONS = 4

WEBHOOK_SECRET = hashlib.sha256(BOT_TOKEN.encode("utf-8")).hexdigest()
WEBHOOK_PATH = hashlib.sha256((BOT_TOKEN + ":path").encode("utf-8")).hexdigest()


def is_owner(update: Update) -> bool:
    user = update.effective_user
    return bool(user and OWNER_ID is not None and user.id == OWNER_ID)


def parse_post_content(content: str):
    """Extract optional link-button directives from post text.

    Format: زر: عنوان الزر | https://example.com
    """
    lines = content.splitlines()
    clean_lines = []
    buttons = []
    for line in lines:
        if line.strip().startswith("زر:"):
            if len(buttons) >= MAX_LINK_BUTTONS:
                return None, None, f"يمكن إضافة {MAX_LINK_BUTTONS} أزرار روابط كحد أقصى."
            directive = line.strip()[len("زر:"):].strip()
            if "|" not in directive:
                return None, None, "صيغة زر الرابط غير صحيحة. استخدم: زر: عنوان الزر | https://example.com"
            label, url = (part.strip() for part in directive.split("|", 1))
            parsed = urlsplit(url)
            if not label or len(label) > 64:
                return None, None, "عنوان الزر مطلوب ويجب ألا يتجاوز 64 حرفاً."
            if parsed.scheme != "https" or not parsed.netloc:
                return None, None, "يجب أن يبدأ رابط الزر بـ https:// وأن يكون رابطاً صالحاً."
            buttons.append({"label": label, "url": url})
        else:
            clean_lines.append(line)
    text = "\n".join(clean_lines).strip()
    if not text:
        return None, None, "أضف نص المنشور قبل أزرار الروابط."
    return text, buttons, None


def link_keyboard(buttons):
    if not buttons:
        return None
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(button["label"], url=button["url"])] for button in buttons]
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "مرحباً بك في مساعد MoradTec 🤖\n\n"
        "أرسل /id لمعرفة رقم حسابك Telegram.\n"
        "استخدم /ideas لاقتراح مواضيع، و/draft الموضوع لإنشاء مسودة، أو /post لنشر محتوى ترسله بنفسك.\n"
        "استخدم /post لإرسال منشور نصي أو صورة مع تعليق، "
        "وسيُنشر تلقائياً بعد استلامه."
    )


async def show_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if user:
        await update.message.reply_text(f"معرّف حسابك Telegram هو:\n{user.id}")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_owner(update):
        await update.message.reply_text("هذا الأمر متاح لمالك البوت فقط.")
        return
    await update.message.reply_text(
        "الأوامر المتاحة:\n"
        "/draft الموضوع - إنشاء مسودة تقنية قابلة للتعديل (لا تُنشر تلقائياً)\n"
        "/ideas - اقتراح أفكار منشورات تقنية\n"
        "/post - إرسال منشور نصي أو صورة مع تعليق (نشر تلقائي)\n"
        "لإضافة زر رابط، أضف سطراً مثل: زر: افتح الموقع | https://example.com\n"
        "يمكن إضافة 4 أزرار روابط HTTPS كحد أقصى.\n"
        "/cancel - إلغاء إعداد المنشور\n"
        "/id - عرض معرّف حسابك"
    )



def clean_topic(raw_topic: str) -> str:
    """Remove command-like suffixes that are not part of the actual topic."""
    topic = re.sub(
        r"\s+(?:لتجربة|لإنشاء|لانشاء|لإعداد|لاعداد|من أجل تجربة|من اجل تجربة)\s+"
        r"(?:إعداد|اعداد|إنشاء|انشاء)?\s*مسودة.*$",
        "",
        raw_topic.strip(),
        flags=re.IGNORECASE,
    )
    topic = re.sub(r"\s+", " ", topic).strip(" .،؛:-")
    return topic or raw_topic.strip()


def topic_profile(topic: str):
    """Return a focused editorial angle, practical points, and relevant tags."""
    normalized = topic.lower()
    if any(word in normalized for word in ("ذكاء", "ai", "اصطناعي", "تعلم آلي", "تعلم الآلة")):
        return (
            "الذكاء الاصطناعي",
            [
                "ابدأ بهدف تعليمي واضح: تلخيص مفهوم، توليد أسئلة للمراجعة، أو تبسيط درس صعب.",
                "اطلب من الأداة شرح الفكرة بمستوى يناسبك، ثم اطلب مثالاً وتمريناً لاختبار فهمك.",
                "تحقق من المعلومات بالرجوع إلى الكتاب أو المعلم أو مصدر موثوق، ولا تنسَ أن الإجابة قد تخطئ.",
            ],
            "#ذكاء_اصطناعي #AI #التعليم #أدوات_رقمية",
            "كيف يمكن توظيف الذكاء الاصطناعي لدعم التعلّم دون أن يحل محل جهد الطالب؟",
        )
    if any(word in normalized for word in ("أمن", "حماية", "اختراق", "خصوصية", "كلمة مرور", "سيبر")):
        return (
            "الأمن الرقمي",
            [
                "فعّل المصادقة الثنائية للحسابات المهمة، ويفضّل استخدام تطبيق موثوق لإدارة كلمات المرور.",
                "افحص عنوان الرابط قبل فتحه، ولا تدخل بياناتك بعد الوصول إلى صفحة من رسالة غير متوقعة.",
                "حدّث نظام التشغيل والتطبيقات، واحتفظ بنسخة احتياطية من الملفات المهمة.",
            ],
            "#الأمن_السيبراني #حماية_البيانات #خصوصية",
            "ما الخطوة الأمنية التي تعتقد أن الجميع يجب أن يبدأ بها اليوم؟",
        )
    if any(word in normalized for word in ("هاتف", "تطبيق", "أندرويد", "اندرويد", "آيفون", "ايفون")):
        return (
            "الهواتف والتطبيقات",
            [
                "راجع اسم المطوّر والتقييمات وتاريخ التحديث قبل تثبيت أي تطبيق.",
                "افتح إعدادات الخصوصية وامنع الأذونات التي لا يحتاجها التطبيق لأداء وظيفته.",
                "احذف التطبيقات غير المستخدمة، وثبّت التحديثات من المتجر الرسمي.",
            ],
            "#هواتف #تطبيقات #Android #نصائح_تقنية",
            "ما التطبيق أو الإعداد الذي أحدث فرقاً حقيقياً في تجربتك؟",
        )
    return (
        "التقنية",
        [
            "حدّد المشكلة التي تريد حلها قبل اختيار التطبيق أو الجهاز؛ فالأداة المناسبة تبدأ من الحاجة.",
            "اختبر الحل على مهمة صغيرة، وقارن الوقت والنتيجة قبل اعتماده في عملك اليومي.",
            "راجع الخصوصية والتكلفة ومصدر المعلومات، ولا تعتمد على ميزة لمجرد أنها جديدة.",
        ],
        "#MoradTec #تقنية #تكنولوجيا #نصائح_تقنية",
        "ما التقنية التي تتمنى أن نشرحها لكم بتجربة عملية؟",
    )


def build_draft(topic: str) -> str:
    """Build a focused, natural Arabic technology post."""
    angle, points, tags, question = topic_profile(topic)
    bullets = "\n".join(f"▪️ {point}" for point in points)
    return (
        f"🚀 {topic}\n\n"
        f"لم يعد {angle} مجرد موضوع نظري؛ إذ يمكن الاستفادة منه في مواقف يومية، "
        "بشرط فهم حدوده واختيار الاستخدام المناسب.\n\n"
        f"📌 **كيف تبدأ؟**\n{bullets}\n\n"
        "🛠️ **جرّب بنفسك:**\n"
        "اختر مثالاً واحداً مرتبطاً بالموضوع، وطبّق الخطوات على نطاق بسيط. "
        "دوّن النتيجة، ثم قارنها بما كنت تفعله سابقاً لتعرف إن كانت الأداة أو الطريقة مفيدة فعلاً.\n\n"
        "⚠️ **قبل الاعتماد عليها:**\n"
        "تحقق من صحة المعلومات، وانتبه إلى خصوصية بياناتك، وارجع إلى المصادر الرسمية عند الحاجة. "
        "قد تختلف الخصائص والنتائج باختلاف الأداة وإصدارها.\n\n"
        f"💬 **نقاش MoradTec:**\n{question}\n"
        "شاركونا آراءكم وتجاربكم في التعليقات.\n\n"
        f"{tags}"
    )


async def find_commons_photo(topic: str):
    """Find a relevant freely licensed photograph on Wikimedia Commons."""
    api_url = "https://commons.wikimedia.org/w/api.php"
    params = {
        "action": "query",
        "generator": "search",
        "gsrsearch": f"{topic} filetype:bitmap",
        "gsrnamespace": 6,
        "gsrlimit": 10,
        "prop": "imageinfo",
        "iiprop": "url|mime|extmetadata",
        "iiurlwidth": 1280,
        "format": "json",
    }
    headers = {"User-Agent": "MoradTecTelegramBot/1.0 (content draft image lookup)"}
    try:
        async with httpx.AsyncClient(timeout=12.0, follow_redirects=True) as client:
            response = await client.get(api_url, params=params, headers=headers)
            response.raise_for_status()
            payload = response.json()
        pages = payload.get("query", {}).get("pages", {})
        for page in pages.values():
            info = (page.get("imageinfo") or [{}])[0]
            mime = info.get("mime", "")
            image_url = info.get("thumburl") or info.get("url")
            if mime not in ("image/jpeg", "image/png") or not image_url:
                continue
            title = page.get("title", "")
            # Prefer ordinary photographs; skip obvious logos, icons, diagrams and maps.
            if re.search(r"(logo|icon|diagram|map|flag|symbol|screenshot|illustration|drawing|artwork|poster|chart|graph|render)", title, re.I):
                continue
            metadata = info.get("extmetadata", {})
            license_name = metadata.get("LicenseShortName", {}).get("value", "ترخيص غير محدد")
            description_url = "https://commons.wikimedia.org/wiki/" + title.replace(" ", "_")
            artist = metadata.get("Artist", {}).get("value", "المؤلف غير مذكور")
            artist = re.sub(r"<[^>]+>", "", html.unescape(artist))
            artist = re.sub(r"\s+", " ", artist).strip()[:180]
            license_url = metadata.get("LicenseUrl", {}).get("value", "")
            return {
                "url": image_url,
                "page": description_url,
                "license": re.sub(r"<[^>]+>", "", html.unescape(license_name))[:100],
                "license_url": license_url,
                "artist": artist,
                "title": title,
            }
    except Exception:
        logger.warning("Wikimedia Commons photo lookup failed")
    return None


async def draft_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Create an editable Arabic tech-post draft from an owner-supplied topic."""
    if not is_owner(update):
        await update.message.reply_text("هذا الأمر متاح لمالك البوت فقط.")
        return

    topic = " ".join(context.args).strip()
    if not topic:
        await update.message.reply_text(
            "اكتب موضوع المنشور بعد الأمر بهذا الشكل:\n"
            "/draft الذكاء الاصطناعي في التعليم"
        )
        return
    if len(topic) > 180:
        await update.message.reply_text("اجعل الموضوع أقصر من 180 حرفاً ثم أعد المحاولة.")
        return

    topic = clean_topic(topic)
    draft = build_draft(topic)
    photo = await find_commons_photo(topic)

    if photo:
        try:
            await update.message.reply_photo(
                photo=photo["url"],
                caption=(
                    f"📷 صورة فوتوغرافية مقترحة\nالمصدر: Wikimedia Commons\n"
                    f"المؤلف: {photo['artist']}\nالترخيص: {photo['license']}\n"
                    f"تفاصيل الترخيص: {photo['license_url'] or photo['page']}"
                ),
            )
            await update.message.reply_text(f"🔗 صفحة الصورة ومصدرها:\n{photo['page']}")
        except Exception:
            logger.warning("Could not send the suggested Commons photo")
            await update.message.reply_text(
                "📷 لم أتمكن من إرفاق الصورة تلقائياً؛ يمكنك فتح صفحة المصدر:\n"
                + photo["page"]
            )
    else:
        await update.message.reply_text(
            "📷 لم أعثر على صورة فوتوغرافية مناسبة لهذا الموضوع حالياً؛ "
            "يمكنك إضافة صورة من اختيارك قبل النشر."
        )

    await update.message.reply_text(
        "📝 هذه مسودة أولية قابلة للتعديل، ولم تُنشر في القناة.\n\n" + draft
    )



async def ideas_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Suggest evergreen technology topics; does not publish anything."""
    if not is_owner(update):
        await update.message.reply_text("هذا الأمر متاح لمالك البوت فقط.")
        return

    await update.message.reply_text(
        "💡 أفكار محتوى لقناة MoradTec\n\n"
        "🤖 الذكاء الاصطناعي:\n"
        "1. كيف تكتب طلباً واضحاً للحصول على نتائج أفضل من أدوات الذكاء الاصطناعي؟\n"
        "2. استخدامات الذكاء الاصطناعي في الدراسة والعمل.\n"
        "3. أخطاء شائعة عند الاعتماد على إجابات الذكاء الاصطناعي.\n\n"
        "🔐 الأمن الرقمي:\n"
        "4. خطوات بسيطة لحماية حساباتك من الاختراق.\n"
        "5. كيف تميّز رسائل التصيّد والروابط المشبوهة؟\n"
        "6. لماذا يجب تفعيل المصادقة الثنائية؟\n\n"
        "📱 الهواتف والتطبيقات:\n"
        "7. أذونات التطبيقات: ما الذي يستحق الموافقة؟\n"
        "8. نصائح لتحسين أداء هاتف Android.\n"
        "9. كيف تختار تطبيقاً آمناً ومفيداً؟\n\n"
        "✍️ لإنشاء مسودة عن أي فكرة، استخدم مثلاً:\n"
        "/draft خطوات بسيطة لحماية حساباتك من الاختراق\n\n"
        "هذه أفكار تحريرية عامة وليست أخباراً مباشرة أو معلومات تم التحقق من حداثتها."
    )

async def post_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_owner(update):
        await update.message.reply_text("عذراً، هذا البوت مخصص لمالكه فقط.")
        return
    context.user_data["waiting_for_post"] = True
    context.user_data.pop("waiting_for_caption", None)
    context.user_data.pop("draft_photo_id", None)
    context.user_data.pop("pending_post", None)
    await update.message.reply_text(
        "وضع النشر التلقائي مفعّل لهذه العملية. أرسل الآن نص المنشور أو صورة مع تعليقها. "
        "سيُنشر المحتوى مباشرة في القناة بعد استلامه.\n"
        "لإضافة زر رابط أضف سطراً مثل: زر: افتح الموقع | https://example.com "
        "(حتى 4 أزرار بروابط HTTPS).\n"
        "أرسل /cancel لإلغاء العملية قبل إرسال المحتوى."
    )


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_owner(update):
        await update.message.reply_text("هذا الأمر متاح لمالك البوت فقط.")
        return
    for key in ("waiting_for_post", "waiting_for_caption", "draft_photo_id", "pending_post"):
        context.user_data.pop(key, None)
    await update.message.reply_text("تم إلغاء المنشور قيد الإعداد.")


async def publish_post(message, context: ContextTypes.DEFAULT_TYPE, draft: dict) -> None:
    """Publish the owner's submitted post immediately to the configured channel."""
    try:
        if draft.get("photo_id"):
            await context.bot.send_photo(
                chat_id=CHANNEL_ID,
                photo=draft["photo_id"],
                caption=draft.get("text") or None,
                reply_markup=link_keyboard(draft.get("buttons", [])),
            )
        else:
            await context.bot.send_message(
                chat_id=CHANNEL_ID,
                text=draft["text"],
                disable_web_page_preview=False,
                reply_markup=link_keyboard(draft.get("buttons", [])),
            )
    except Exception:
        logger.exception("Failed to publish to channel")
        await message.reply_text(
            "تعذر النشر في القناة. تأكد أن البوت مشرف ولديه صلاحية نشر الرسائل، ثم أعد المحاولة باستخدام /post."
        )
        return

    for key in ("waiting_for_post", "waiting_for_caption", "draft_photo_id", "pending_post"):
        context.user_data.pop(key, None)
    await message.reply_text("✅ تم نشر المحتوى تلقائياً في قناة MoradTec.")


async def receive_post(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_owner(update):
        return
    message = update.effective_message
    if not message:
        return

    if context.user_data.get("waiting_for_caption"):
        if not message.text:
            await message.reply_text("أرسل تعليق الصورة كنص من فضلك.")
            return
        caption, buttons, error = parse_post_content(message.text.strip())
        if error:
            await message.reply_text(error)
            return
        if len(caption) > MAX_CAPTION_LENGTH:
            await message.reply_text(
                f"تعليق الصورة يجب ألا يتجاوز {MAX_CAPTION_LENGTH} حرفاً. أعد إرساله بشكل أقصر."
            )
            return
        photo_id = context.user_data.pop("draft_photo_id", None)
        if not photo_id:
            context.user_data["waiting_for_caption"] = False
            await message.reply_text("انتهت جلسة إعداد الصورة. أرسل /post للبدء من جديد.")
            return
        await publish_post(message, context, {"photo_id": photo_id, "text": caption, "buttons": buttons})
        return

    if not context.user_data.get("waiting_for_post"):
        return

    if message.photo:
        photo_id = message.photo[-1].file_id
        caption = (message.caption or "").strip()
        if caption:
            caption, buttons, error = parse_post_content(caption)
            if error:
                await message.reply_text(error)
                return
        else:
            buttons = []
        if len(caption) > MAX_CAPTION_LENGTH:
            await message.reply_text(
                f"تعليق الصورة يجب ألا يتجاوز {MAX_CAPTION_LENGTH} حرفاً."
            )
            return
        if not caption:
            context.user_data["waiting_for_caption"] = True
            context.user_data["draft_photo_id"] = photo_id
            await message.reply_text("وصلت الصورة. أرسل الآن النص أو التعليق الذي تريد إرفاقه بها.")
            return
        await publish_post(message, context, {"photo_id": photo_id, "text": caption, "buttons": buttons})
        return

    if message.text:
        content, buttons, error = parse_post_content(message.text.strip())
        if error:
            await message.reply_text(error)
            return
        if not content:
            await message.reply_text("النص فارغ. أرسل نص المنشور من فضلك.")
            return
        if len(content) > MAX_POST_LENGTH:
            await message.reply_text(
                f"الحد الأقصى للمنشور النصي {MAX_POST_LENGTH} حرفاً. اختصر النص ثم أعد إرساله."
            )
            return
        await publish_post(message, context, {"text": content, "buttons": buttons})


def main() -> None:
    if OWNER_ID is None:
        logger.warning("OWNER_ID is not configured. Set it in the hosting environment.")

    external_url = os.environ["RENDER_EXTERNAL_URL"].rstrip("/")
    port = int(os.environ.get("PORT", "10000"))

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("id", show_id))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("draft", draft_command))
    app.add_handler(CommandHandler("ideas", ideas_command))
    app.add_handler(CommandHandler("post", post_command))
    app.add_handler(CommandHandler("cancel", cancel_command))
    app.add_handler(
        MessageHandler((filters.PHOTO | filters.TEXT) & ~filters.COMMAND, receive_post)
    )

    webhook_url = f"{external_url}/{WEBHOOK_PATH}"
    logger.info("Starting MoradTec bot webhook on port %s", port)
    app.run_webhook(
        listen="0.0.0.0",
        port=port,
        url_path=WEBHOOK_PATH,
        webhook_url=webhook_url,
        secret_token=WEBHOOK_SECRET,
        drop_pending_updates=True,
    )


if __name__ == "__main__":
    main()
