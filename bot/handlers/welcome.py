import logging
from telegram import Update
from telegram.ext import ContextTypes

import database as db
from utils.helpers import extract_status_change
from utils.messages import (
    full_name, welcome_text, left_text
)

logger = logging.getLogger(__name__)


async def member_status_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    """
    هندلر اصلی برای join و left
    آپدیت نوع ChatMemberUpdated رو می‌گیره
    """
    result = extract_status_change(update.chat_member)
    if result is None:
        return

    was_member, is_member = result
    chat  = update.effective_chat
    user  = update.chat_member.new_chat_member.user

    name = full_name(user.first_name, user.last_name)

    # ذخیره گروه
    await db.save_group(chat.id, chat.title or "گروه")

    # ─── جوین شد ───
    if not was_member and is_member:
        logger.info(f"[{chat.title}] {name} جوین شد")

        await db.add_member(
            group_id   = chat.id,
            user_id    = user.id,
            first_name = user.first_name,
            last_name  = user.last_name,
            username   = user.username,
        )

        await db.log_event(
            group_id   = chat.id,
            user_id    = user.id,
            event_type = "join",
            new_value  = name,
        )

        msg = welcome_text(user.id, name)
        await context.bot.send_message(
            chat_id    = chat.id,
            text       = msg,
            parse_mode = "HTML",
        )

    # ─── لفت داد ───
    elif was_member and not is_member:
        logger.info(f"[{chat.title}] {name} لفت داد")

        await db.remove_member(chat.id, user.id)

        await db.log_event(
            group_id   = chat.id,
            user_id    = user.id,
            event_type = "left",
            old_value  = name,
        )

        msg = left_text(user.id, name)
        await context.bot.send_message(
            chat_id    = chat.id,
            text       = msg,
            parse_mode = "HTML",
        )
