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

    draft = (
        f"💡 {topic}\n\n"
        f"أصبح موضوع {topic} من المواضيع التي تستحق المتابعة في عالم التقنية. "
        "فهم الفكرة وطريقة استخدامها يساعداننا على الاستفادة من الأدوات الرقمية بوعي.\n\n"
        "🔹 **ما الذي ينبغي معرفته؟**\n"
        "ابدأ بالتعرّف على المفهوم، ثم جرّب تطبيقاً موثوقاً له، وقارن النتائج قبل الاعتماد عليه.\n\n"
        "⚠️ **نصيحة مهمة:**\n"
        "تحقق من المعلومات ومصدرها، ولا تشارك بياناتك الشخصية أو الحساسة مع أي خدمة غير موثوقة.\n\n"
        "💬 ما رأيكم؟ هل تستخدمون هذه التقنية؟ شاركونا تجاربكم في التعليقات.\n\n"
        "#MoradTec #تقنية #تكنولوجيا #ذكاء_اصطناعي"
    )
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
