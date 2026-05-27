import logging
from telegram import Update
from telegram.ext import ContextTypes

import database as db
from utils.messages import (
    full_name,
    name_changed_text,
    username_changed_text,
    photo_changed_text,
)

logger = logging.getLogger(__name__)


async def user_update_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    """
    تشخیص تغییر اسم / یوزرنیم
    این هندلر روی هر پیام فعاله
    """
    user  = update.effective_user
    chat  = update.effective_chat

    if not user or chat.type not in ("group", "supergroup"):
        return

    # اطلاعات فعلی
    current_name     = full_name(user.first_name, user.last_name)
    current_username = user.username

    # اطلاعات قدیمی از دیتابیس
    old = await db.get_member(chat.id, user.id)

    if old is None:
        # کاربر جدیده، ذخیره کن
        await db.add_member(
            group_id   = chat.id,
            user_id    = user.id,
            first_name = user.first_name,
            last_name  = user.last_name,
            username   = user.username,
        )
        return

    old_name     = full_name(old["first_name"], old.get("last_name"))
    old_username = old.get("username")

    changed = False

    # ─── تغییر اسم ───
    if current_name != old_name:
        logger.info(f"[{chat.title}] تغییر اسم: {old_name} → {current_name}")

        await db.log_event(
            group_id   = chat.id,
            user_id    = user.id,
            event_type = "name_changed",
            old_value  = old_name,
            new_value  = current_name,
        )

        msg = name_changed_text(user.id, old_name, current_name)
        await context.bot.send_message(
            chat_id    = chat.id,
            text       = msg,
            parse_mode = "HTML",
        )
        changed = True

    # ─── تغییر یوزرنیم ───
    if current_username != old_username:
        logger.info(
            f"[{chat.title}] تغییر یوزرنیم: "
            f"@{old_username} → @{current_username}"
        )

        await db.log_event(
            group_id   = chat.id,
            user_id    = user.id,
            event_type = "username_changed",
            old_value  = old_username,
            new_value  = current_username,
        )

        msg = username_changed_text(
            user.id, current_name,
            old_username, current_username
        )
        await context.bot.send_message(
            chat_id    = chat.id,
            text       = msg,
            parse_mode = "HTML",
        )
        changed = True

    # بروزرسانی دیتابیس اگه تغییر داشت
    if changed:
        await db.update_member_info(
            group_id   = chat.id,
            user_id    = user.id,
            first_name = user.first_name,
            last_name  = user.last_name,
            username   = user.username,
        )


async def photo_update_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    """
    تشخیص تغییر عکس پروفایل
    وقتی کسی عکس پروفایلش رو عوض می‌کنه،
    تلگرام یه پیام new_chat_photo می‌فرسته
    """
    chat = update.effective_chat
    user = update.effective_user

    if not user:
        return

    name = full_name(user.first_name, user.last_name)
    logger.info(f"[{chat.title}] {name} عکس پروفایل عوض کرد")

    await db.log_event(
        group_id   = chat.id,
        user_id    = user.id,
        event_type = "photo_changed",
    )

    msg = photo_changed_text(user.id, name)
    await context.bot.send_message(
        chat_id    = chat.id,
        text       = msg,
        parse_mode = "HTML",
    )
