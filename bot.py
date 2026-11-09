import hashlib
import logging
import os
from urllib.parse import urlsplit

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
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
    text = "\\n".join(clean_lines).strip()
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
        "استخدم /post لإعداد منشور نصي أو صورة مع تعليق، "
        "ولن يُنشر شيء قبل موافقتك."
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
        "/post - إعداد منشور نصي أو صورة مع تعليق ومعاينته\n"
        "لإضافة زر رابط، أضف سطراً مثل: زر: افتح الموقع | https://example.com\n"
        "يمكن إضافة 4 أزرار روابط HTTPS كحد أقصى.\n"
        "/cancel - إلغاء إعداد المنشور\n"
        "/id - عرض معرّف حسابك"
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
        "أرسل نص المنشور، أو أرسل صورة مع تعليقها. "
        "لإضافة زر رابط أضف سطراً مثل: زر: افتح الموقع | https://example.com "
        "(حتى 4 أزرار بروابط HTTPS). "
        "لن يُنشر شيء قبل ضغطك على زر الموافقة."
    )


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_owner(update):
        await update.message.reply_text("هذا الأمر متاح لمالك البوت فقط.")
        return
    for key in ("waiting_for_post", "waiting_for_caption", "draft_photo_id", "pending_post"):
        context.user_data.pop(key, None)
    await update.message.reply_text("تم إلغاء المنشور قيد الإعداد.")


async def show_preview(message, context: ContextTypes.DEFAULT_TYPE, draft: dict) -> None:
    context.user_data["waiting_for_post"] = False
    context.user_data["waiting_for_caption"] = False
    context.user_data["pending_post"] = draft
    link_rows = [
        [InlineKeyboardButton(button["label"], url=button["url"])]
        for button in draft.get("buttons", [])
    ]
    link_rows.append([
        InlineKeyboardButton("✅ موافقة ونشر", callback_data="publish"),
        InlineKeyboardButton("❌ رفض", callback_data="reject"),
    ])
    keyboard = InlineKeyboardMarkup(link_rows)
    if draft.get("photo_id"):
        caption = "👀 معاينة المنشور — لم يتم النشر بعد:\n\n" + (draft.get("text") or "")
        await message.reply_photo(
            photo=draft["photo_id"],
            caption=caption,
            reply_markup=keyboard,
        )
    else:
        await message.reply_text(
            "👀 معاينة المنشور — لم يتم النشر بعد:\n\n" + draft["text"],
            reply_markup=keyboard,
        )


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
        await show_preview(message, context, {"photo_id": photo_id, "text": caption, "buttons": buttons})
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
        await show_preview(message, context, {"photo_id": photo_id, "text": caption})
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
        await show_preview(message, context, {"text": content, "buttons": buttons})


async def review_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return
    if not is_owner(update):
        await query.answer("غير مصرح لك باستخدام هذا الزر.", show_alert=True)
        return

    pending = context.user_data.get("pending_post")
    if query.data == "reject":
        context.user_data.pop("pending_post", None)
        await query.answer("تم رفض المنشور.")
        await query.edit_message_caption("❌ تم رفض المنشور ولم يُنشر.") if query.message and query.message.photo else await query.edit_message_text("❌ تم رفض المنشور ولم يُنشر.")
        return

    if query.data == "publish":
        if not pending:
            await query.answer("لا يوجد منشور معلّق.", show_alert=True)
            return
        try:
            if pending.get("photo_id"):
                await context.bot.send_photo(
                    chat_id=CHANNEL_ID,
                    photo=pending["photo_id"],
                    caption=pending.get("text") or None,
                    reply_markup=link_keyboard(pending.get("buttons", [])),
                )
            else:
                await context.bot.send_message(
                    chat_id=CHANNEL_ID,
                    text=pending["text"],
                    disable_web_page_preview=False,
                    reply_markup=link_keyboard(pending.get("buttons", [])),
                )
        except Exception:
            logger.exception("Failed to publish to channel")
            await query.answer("تعذر النشر. تحقق من صلاحيات البوت في القناة.", show_alert=True)
            return

        context.user_data.pop("pending_post", None)
        await query.answer("تم النشر.")
        if query.message and query.message.photo:
            await query.edit_message_caption("✅ تم نشر الصورة والمنشور في قناة MoradTec.")
        else:
            await query.edit_message_text("✅ تم نشر المنشور في قناة MoradTec.")


def main() -> None:
    if OWNER_ID is None:
        logger.warning("OWNER_ID is not configured. Set it in the hosting environment.")

    external_url = os.environ["RENDER_EXTERNAL_URL"].rstrip("/")
    port = int(os.environ.get("PORT", "10000"))

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("id", show_id))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("post", post_command))
    app.add_handler(CommandHandler("cancel", cancel_command))
    app.add_handler(CallbackQueryHandler(review_callback, pattern="^(publish|reject)$"))
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
