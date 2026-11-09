import hashlib
import logging
import os
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
        "استخدم /draft الموضوع لإنشاء مسودة تقنية، أو /post لنشر محتوى ترسله بنفسك.\n"
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
        "/post - إرسال منشور نصي أو صورة مع تعليق (نشر تلقائي)\n"
        "لإضافة زر رابط، أضف سطراً مثل: زر: افتح الموقع | https://example.com\n"
        "يمكن إضافة 4 أزرار روابط HTTPS كحد أقصى.\n"
        "/cancel - إلغاء إعداد المنشور\n"
        "/id - عرض معرّف حسابك"
    )



def build_draft(topic: str) -> str:
    """Build a richer Arabic technology post using safe, offline editorial templates."""
    normalized = topic.lower()
    if any(word in normalized for word in ("ذكاء", "ai", "اصطناعي", "تعلم آلي")):
        angle = "الذكاء الاصطناعي"
        points = [
            "حدّد المهمة التي تريد إنجازها بوضوح، واكتب طلباً محدداً بدلاً من سؤال عام.",
            "راجع المخرجات وقارنها بمصدر موثوق؛ فقد يقدّم النظام معلومات ناقصة أو غير دقيقة.",
            "استخدم الأداة للمساعدة في التفكير والتعلّم، لا بديلاً عن حكمك وخبرتك.",
        ]
        tags = "#ذكاء_اصطناعي #AI #أدوات_رقمية"
    elif any(word in normalized for word in ("أمن", "حماية", "اختراق", "خصوصية", "كلمة مرور", "سيبر")):
        angle = "الأمن الرقمي"
        points = [
            "استخدم كلمة مرور قوية ومختلفة لكل حساب، وفعّل المصادقة الثنائية.",
            "تحقّق من عنوان الموقع والمرسل قبل فتح الروابط أو تنزيل الملفات.",
            "حدّث التطبيقات والنظام بانتظام، واحتفظ بنسخة احتياطية من ملفاتك المهمة.",
        ]
        tags = "#الأمن_السيبراني #حماية_البيانات #خصوصية"
    elif any(word in normalized for word in ("هاتف", "تطبيق", "أندرويد", "اندرويد", "آيفون", "ايفون")):
        angle = "الهواتف والتطبيقات"
        points = [
            "راجع تقييمات التطبيق واسم المطوّر قبل التثبيت.",
            "امنح التطبيق الأذونات التي يحتاجها فعلاً فقط.",
            "حدّث التطبيقات من المتجر الرسمي واحذف ما لم تعد تستخدمه.",
        ]
        tags = "#هواتف #تطبيقات #Android"
    else:
        angle = "التقنية"
        points = [
            "ابدأ بفهم المشكلة التي تعالجها التقنية قبل اختيار الأداة.",
            "جرّب الحل على نطاق صغير، ثم قيّم فائدته وسهولة استخدامه.",
            "قارن أكثر من مصدر ولا تعتمد على معلومة واحدة عند اتخاذ القرار.",
        ]
        tags = "#تقنية_حديثة #تعلم_التقنية #نصائح_تقنية"

    bullets = "\\n".join(f"▪️ {point}" for point in points)
    return (
        f"🚀 {topic}\n\n"
        f"هل تعرف كيف يمكن أن تستفيد من {angle} بطريقة عملية؟ "
        "الفكرة ليست في استخدام كل أداة جديدة، بل في اختيار ما يحل مشكلة حقيقية ويوفر الوقت أو يرفع جودة العمل.\n\n"
        "📌 **3 نقاط تستحق الانتباه:**\n"
        f"{bullets}\n\n"
        "🛠️ **خطوة عملية للبدء:**\n"
        "اختر استخداماً واحداً مرتبطاً باهتمامك، جرّبه بنفسك، وسجّل ما نجح وما يحتاج إلى تحسين. "
        "لا تتخذ قراراً اعتماداً على تجربة واحدة فقط.\n\n"
        "⚠️ **تذكير مهم:**\n"
        "احمِ بياناتك الشخصية، وتحقق من المعلومات من مصادر موثوقة. تختلف النتائج والميزات حسب الأداة وإصدارها، لذلك راجع التفاصيل الرسمية قبل الاعتماد عليها.\n\n"
        "💬 **نريد رأيكم:**\n"
        f"ما أكثر جانب يهمكم في موضوع «{topic}»؟ اكتبوا تجاربكم وأسئلتكم في التعليقات.\n\n"
        f"#MoradTec #تقنية #تكنولوجيا {tags}"
    )


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

    draft = build_draft(topic)
    await update.message.reply_text(
        "📝 هذه مسودة أولية قابلة للتعديل، ولم تُنشر في القناة.\n\n" + draft
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
