import hashlib
import logging
import os

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

# Derive Telegram's webhook secret and an unguessable URL path without
# introducing another secret that the owner must configure.
WEBHOOK_SECRET = hashlib.sha256(BOT_TOKEN.encode("utf-8")).hexdigest()
WEBHOOK_PATH = hashlib.sha256((BOT_TOKEN + ":path").encode("utf-8")).hexdigest()


def is_owner(update: Update) -> bool:
    user = update.effective_user
    return bool(user and OWNER_ID is not None and user.id == OWNER_ID)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "مرحباً بك في مساعد MoradTec 🤖\n\n"
        "أرسل /id لمعرفة رقم حسابك Telegram.\n"
        "بعد ضبط OWNER_ID في إعدادات الاستضافة، يمكنك استخدام /post "
        "لإعداد منشور ومعاينته قبل نشره."
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
        "/post - إعداد منشور جديد ومعاينته\n"
        "/cancel - إلغاء إعداد المنشور\n"
        "/id - عرض معرّف حسابك"
    )


async def post_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_owner(update):
        await update.message.reply_text("عذراً، هذا البوت مخصص لمالكه فقط.")
        return
    context.user_data["waiting_for_post"] = True
    await update.message.reply_text(
        "أرسل الآن نص المنشور الذي تريد معاينته. لن يُنشر شيء قبل ضغطك على زر الموافقة."
    )


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_owner(update):
        await update.message.reply_text("هذا الأمر متاح لمالك البوت فقط.")
        return
    context.user_data.pop("waiting_for_post", None)
    context.user_data.pop("pending_post", None)
    await update.message.reply_text("تم إلغاء المنشور قيد الإعداد.")


async def receive_post(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_owner(update) or not context.user_data.get("waiting_for_post"):
        return
    message = update.effective_message
    if not message or not message.text:
        return
    content = message.text.strip()
    if not content:
        await message.reply_text("النص فارغ. أرسل نص المنشور من فضلك.")
        return
    if len(content) > MAX_POST_LENGTH:
        await message.reply_text(
            f"الحد الأقصى في النسخة الحالية {MAX_POST_LENGTH} حرفاً. اختصر النص ثم أعد إرساله."
        )
        return

    context.user_data["waiting_for_post"] = False
    context.user_data["pending_post"] = content
    keyboard = InlineKeyboardMarkup(
        [[
            InlineKeyboardButton("✅ موافقة ونشر", callback_data="publish"),
            InlineKeyboardButton("❌ رفض", callback_data="reject"),
        ]]
    )
    await message.reply_text(
        "👀 معاينة المنشور — لم يتم النشر بعد:\n\n" + content,
        reply_markup=keyboard,
    )


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
        await query.edit_message_text("❌ تم رفض المنشور ولم يُنشر.")
        return

    if query.data == "publish":
        if not pending:
            await query.answer("لا يوجد منشور معلّق.", show_alert=True)
            return
        try:
            await context.bot.send_message(
                chat_id=CHANNEL_ID,
                text=pending,
                disable_web_page_preview=False,
            )
        except Exception:
            logger.exception("Failed to publish to channel")
            await query.answer("تعذر النشر. تحقق من صلاحيات البوت في القناة.", show_alert=True)
            return

        context.user_data.pop("pending_post", None)
        await query.answer("تم النشر.")
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
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, receive_post))

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
