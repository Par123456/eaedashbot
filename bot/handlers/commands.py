import logging
from telegram import Update
from telegram.ext import ContextTypes

import database as db
from utils.helpers import is_admin
from utils.messages import build_log_message

logger = logging.getLogger(__name__)


async def lm_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    """
    /lm → نمایش لاگ کامل گروه
    فقط ادمین‌ها می‌تونن استفاده کنن
    """
    chat = update.effective_chat
    user = update.effective_user

    # فقط توی گروه کار می‌کنه
    if chat.type not in ("group", "supergroup"):
        await update.message.reply_text(
            "❌ این دستور فقط توی گروه کار می‌کنه!"
        )
        return

    # چک ادمین بودن
    if not await is_admin(update, context, user.id):
        await update.message.reply_text(
            "🚫 فقط ادمین‌های گروه می‌تونن این دستور رو بزنن!"
        )
        return

    # نشانه در حال پردازش
    processing_msg = await update.message.reply_text(
        "⏳ در حال آماده‌سازی گزارش..."
    )

    try:
        events = await db.get_all_events(chat.id)
        pages  = build_log_message(events)

        # حذف پیام 
