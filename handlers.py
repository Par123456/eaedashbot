"""
🎯 ماژول هندلرها - پردازش تمام رویدادهای ربات
Telegram Group Monitor Bot - Event Handlers
"""

import logging
from datetime import datetime
from typing import Any

from telegram import (
    Chat,
    ChatMember,
    ChatMemberUpdated,
    Update,
    User,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.constants import ChatMemberStatus, ChatType
from telegram.ext import (
    ChatMemberHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from config import Config
from database import Database

logger = logging.getLogger(__name__)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  نمونه دیتابیس
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

db = Database()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  ابزارهای کمکی
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def extract_status_change(chat_member_update: ChatMemberUpdated) -> tuple[str | None, str | None]:
    """
    استخراج تغییر وضعیت کاربر

    Returns:
        (old_status, new_status)
    """
    old = chat_member_update.old_chat_member
    new = chat_member_update.new_chat_member
    return old.status if old else None, new.status if new else None


def get_user_display_name(user: User) -> str:
    """دریافت نام نمایشی کاربر"""
    name = user.first_name or ""
    if user.last_name:
        name += f" {user.last_name}"
    return name.strip() or "ناشناس"


def get_user_mention(user: User) -> str:
    """دریافت منشن کاربر با لینک"""
    name = get_user_display_name(user)
    return f'<a href="tg://user?id={user.id}">{name}</a>'


def format_event_emoji(event_type: str) -> str:
    """دریافت ایموجی مناسب برای هر نوع رویداد"""
    emojis = {
        "join": "🟢",
        "left": "🔴",
        "name_change": "✏️",
        "username_change": "🔄",
        "photo_change": "📸",
    }
    return emojis.get(event_type, "📌")


def format_event_name(event_type: str) -> str:
    """دریافت نام فارسی نوع رویداد"""
    names = {
        "join": "ورود به گروه",
        "left": "خروج از گروه",
        "name_change": "تغییر نام",
        "username_change": "تغییر آیدی",
        "photo_change": "تغییر پروفایل",
    }
    return names.get(event_type, event_type)


def is_admin(chat: Chat, user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """بررسی ادمین بودن کاربر"""
    try:
        member = chat.get_member(user_id)
        return member.status in (
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.OWNER,
        )
    except Exception:
        # اگر ادمین کل ربات باشد
        return user_id in Config.ADMIN_IDS


async def safe_reply(
    update: Update,
    text: str,
    parse_mode: str = "HTML",
    reply_markup: Any = None,
    **kwargs,
) -> None:
    """پاسخ امن با مدیریت خطا"""
    try:
        await update.effective_message.reply_text(
            text=text,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
            disable_web_page_preview=True,
            **kwargs,
        )
    except Exception as e:
        logger.error(f"خطا در ارسال پیام: {e}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  هندلر رویدادهای اعضا (ورود، خروج، تغییر نام/آیدی)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def track_chat_members(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    پردازش تغییرات اعضای گروه
    - ورود اعضای جدید
    - خروج اعضا
    - تغییر نام
    - تغییر آیدی/یوزرنیم
    """
    result = extract_status_change(update.chat_member)
    old_status, new_status = result

    chat = update.effective_chat
    user = update.chat_member.new_chat_member.user

    # ─── ثبت اطلاعات کاربر ───
    db.upsert_user(
        user_id=user.id,
        first_name=user.first_name or "",
        last_name=user.last_name or "",
        username=user.username or "",
    )

    # ─── ثبت اطلاعات گروه ───
    if chat.type in (ChatType.GROUP, ChatType.SUPERGROUP):
        db.upsert_group(
            chat_id=chat.id,
            chat_title=chat.title or "",
        )

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #  ورود عضو جدید
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    if (
        old_status in (ChatMemberStatus.LEFT, ChatMemberStatus.BANNED)
        and new_status == ChatMemberStatus.MEMBER
    ):
        # ثبت رویداد ورود
        db.log_event(
            chat_id=chat.id,
            user_id=user.id,
            event_type="join",
            new_value=get_user_display_name(user),
        )
        logger.info(f"✅ کاربر {get_user_display_name(user)} وارد گروه {chat.title} شد")

        # ارسال پیام خوش‌آمدگویی
        settings = db.get_group_settings(chat.id)
        if settings and settings.get("welcome_enabled", 1):
            welcome_msg = settings.get("welcome_message") or Config.DEFAULT_WELCOME_MESSAGE
            mention = get_user_mention(user)

            try:
                text = welcome_msg.format(
                    name=mention,
                    chat_title=chat.title or "گروه",
                    first_name=user.first_name or "",
                    last_name=user.last_name or "",
                    username=user.username or "ندارد",
                    user_id=user.id,
                )
            except (KeyError, IndexError):
                text = f"👋 خوش آمدی {mention}!"

            await safe_reply(update, text)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #  خروج عضو
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    elif (
        old_status == ChatMemberStatus.MEMBER
        and new_status in (ChatMemberStatus.LEFT, ChatMemberStatus.BANNED)
    ):
        db.log_event(
            chat_id=chat.id,
            user_id=user.id,
            event_type="left",
            old_value=get_user_display_name(user),
        )
        logger.info(f"❌ کاربر {get_user_display_name(user)} از گروه {chat.title} خارج شد")

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #  تشخیص تغییر نام یا آیدی
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    if old_status == new_status and old_status in (
        ChatMemberStatus.MEMBER,
        ChatMemberStatus.ADMINISTRATOR,
        ChatMemberStatus.OWNER,
    ):
        old_user = update.chat_member.old_chat_member.user
        new_user = update.chat_member.new_chat_member.user

        # ─── تغییر نام ───
        old_name = get_user_display_name(old_user)
        new_name = get_user_display_name(new_user)
        if old_name != new_name:
            db.log_event(
                chat_id=chat.id,
                user_id=user.id,
                event_type="name_change",
                old_value=old_name,
                new_value=new_name,
            )
            mention = get_user_mention(user)
            text = (
                f"✏️ <b>تغییر نام</b>\n\n"
                f"👤 کاربر: {mention}\n"
                f"📛 نام قبلی: <s>{old_name}</s>\n"
                f"✅ نام جدید: <b>{new_name}</b>"
            )
            await safe_reply(update, text)
            logger.info(f"✏️ کاربر {old_name} → {new_name}")

        # ─── تغییر آیدی (یوزرنیم) ───
        old_username = old_user.username or ""
        new_username = new_user.username or ""
        if old_username != new_username:
            db.log_event(
                chat_id=chat.id,
                user_id=user.id,
                event_type="username_change",
                old_value=f"@{old_username}" if old_username else "ندارد",
                new_value=f"@{new_username}" if new_username else "ندارد",
            )
            mention = get_user_mention(user)
            text = (
                f"🔄 <b>تغییر آیدی</b>\n\n"
                f"👤 کاربر: {mention}\n"
                f"📛 آیدی قبلی: <code>{('@' + old_username) if old_username else 'ندارد'}</code>\n"
                f"✅ آیدی جدید: <code>{('@' + new_username) if new_username else 'ندارد'}</code>"
            )
            await safe_reply(update, text)
            logger.info(f"🔄 آیدی کاربر: @{old_username} → @{new_username}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  هندلر تشخیص تغییر پروفایل
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def track_profile_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    بررسی تغییر عکس پروفایل کاربران هنگام ارسال پیام
    """
    if not update.effective_user:
        return

    chat = update.effective_chat
    user = update.effective_user

    # فقط در گروه‌ها
    if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return

    try:
        # دریافت عکس پروفایل فعلی
        photos = await context.bot.get_user_profile_photos(user_id=user.id, limit=1)
        current_photo_id = None

        if photos.total_count > 0:
            # کوچکترین عکس رو می‌گیریم برای مقایسه
            current_photo_id = photos.photos[0][-1].file_id

        # دریافت اطلاعات ذخیره شده
        stored_user = db.get_user(user.id)

        if stored_user and stored_user.get("photo_file_id"):
            stored_photo_id = stored_user["photo_file_id"]

            if stored_photo_id != current_photo_id:
                # تغییر پروفایل تشخیص داده شد!
                db.log_event(
                    chat_id=chat.id,
                    user_id=user.id,
                    event_type="photo_change",
                    old_value=stored_photo_id,
                    new_value=current_photo_id or "حذف شده",
                )

                mention = get_user_mention(user)
                text = (
                    f"📸 <b>تغییر عکس پروفایل</b>\n\n"
                    f"👤 کاربر: {mention}\n"
                    f"🕐 زمان: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                )
                await safe_reply(update, text)
                logger.info(f"📸 کاربر {get_user_display_name(user)} عکس پروفایل را تغییر داد")

        # بروزرسانی عکس پروفایل ذخیره شده
        db.upsert_user(
            user_id=user.id,
            first_name=user.first_name or "",
            last_name=user.last_name or "",
            username=user.username or "",
            photo_file_id=current_photo_id,
        )

    except Exception as e:
        logger.debug(f"خطا در بررسی پروفایل: {e}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  هندلر گزارش (دستور /lm)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def report_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    دستور /lm - نمایش گزارش کامل فعالیت‌های گروه
    شامل: ورود، خروج، تغییر نام، تغییر آیدی، تغییر پروفایل
    فقط ادمین‌ها می‌توانند استفاده کنند.
    """
    chat = update.effective_chat
    user = update.effective_user

    # ─── بررسی ادمین بودن ───
    if not is_admin(chat, user.id, context):
        await safe_reply(update, "⛔ این دستور فقط برای ادمین‌هاست!")
        return

    # فقط در گروه‌ها
    if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        await safe_reply(update, "⛔ این دستور فقط در گروه‌ها کار می‌کند!")
        return

    # ─── بررسی آرگومان‌ها ───
    args = context.args or []
    limit = Config.REPORT_PAGE_SIZE

    if args:
        try:
            limit = int(args[0])
            limit = min(limit, 100)  # حداکثر ۱۰۰
        except ValueError:
            pass

    # ─── دریافت آمار ───
    stats = db.get_group_stats(chat.id)
    events = db.get_group_report(chat.id, limit=limit)

    if not events:
        await safe_reply(update, "📭 هیچ رویدادی ثبت نشده است!")
        return

    # ─── ساخت گزارش ───
    total_events = sum(stats.values())

    report = (
        f"📊 <b>گزارش کامل فعالیت‌های گروه</b>\n"
        f"🏷️ <b>{chat.title}</b>\n"
        f"{'─' * 30}\n\n"
        f"📈 <b>آمار کلی:</b>\n"
        f"🟢 ورود: <b>{stats.get('join', 0)}</b>\n"
        f"🔴 خروج: <b>{stats.get('left', 0)}</b>\n"
        f"✏️ تغییر نام: <b>{stats.get('name_change', 0)}</b>\n"
        f"🔄 تغییر آیدی: <b>{stats.get('username_change', 0)}</b>\n"
        f"📸 تغییر پروفایل: <b>{stats.get('photo_change', 0)}</b>\n"
        f"{'─' * 30}\n\n"
        f"📋 <b>آخرین {len(events)} رویداد:</b>\n\n"
    )

    for i, event in enumerate(events, 1):
        emoji = format_event_emoji(event["event_type"])
        event_name = format_event_name(event["event_type"])

        # نام کاربر
        display_name = event.get("full_name") or event.get("first_name") or "ناشناس"
        username_str = f" (@{event['username']})" if event.get("username") else ""

        report += (
            f"{emoji} <b>{i}.</b> {event_name}\n"
            f"   👤 {display_name}{username_str}\n"
        )

        # نمایش تغییرات
        if event["event_type"] in ("name_change", "username_change"):
            if event.get("old_value"):
                report += f"   📛 قبلی: <code>{event['old_value']}</code>\n"
            if event.get("new_value"):
                report += f"   ✅ جدید: <code>{event['new_value']}</code>\n"
        elif event["event_type"] == "photo_change":
            report += f"   📸 عکس پروفایل تغییر کرد\n"
        elif event["event_type"] == "join":
            report += f"   🟢 وارد گروه شد\n"
        elif event["event_type"] == "left":
            report += f"   🔴 از گروه خارج شد\n"

        report += f"   🕐 {event['created_at']}\n\n"

    report += f"{'─' * 30}\n📊 مجموع: <b>{total_events}</b> رویداد"

    # ─── ارسال با دکمه شیشه‌ای ───
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🟢 فقط ورودها", callback_data="report_join"),
            InlineKeyboardButton("🔴 فقط خروج‌ها", callback_data="report_left"),
        ],
        [
            InlineKeyboardButton("✏️ تغییرات نام", callback_data="report_name"),
            InlineKeyboardButton("🔄 تغییرات آیدی", callback_data="report_username"),
        ],
        [
            InlineKeyboardButton("📸 تغییرات پروفایل", callback_data="report_photo"),
            InlineKeyboardButton("📋 گزارش کامل", callback_data="report_all"),
        ],
    ])

    await safe_reply(update, report, reply_markup=keyboard)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  هندلر دکمه‌های شیشه‌ای گزارش
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def report_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """پردازش دکمه‌های شیشه‌ای گزارش"""
    query = update.callback_query
    await query.answer()

    chat = update.effective_chat
    user = update.effective_user

    if not is_admin(chat, user.id, context):
        await query.answer("⛔ فقط ادمین‌ها!", show_alert=True)
        return

    data = query.data
    type_map = {
        "report_join": "join",
        "report_left": "left",
        "report_name": "name_change",
        "report_username": "username_change",
        "report_photo": "photo_change",
    }

    if data == "report_all":
        events = db.get_group_report(chat.id, limit=50)
        title = "📋 گزارش کامل"
    elif data in type_map:
        event_type = type_map[data]
        events = db.get_events_by_type(chat.id, event_type, limit=50)
        title = f"{format_event_emoji(event_type)} {format_event_name(event_type)}"
    else:
        return

    if not events:
        await query.answer("📭 رویدادی یافت نشد!", show_alert=True)
        return

    text = f"{title}\n{'─' * 25}\n\n"

    for i, event in enumerate(events, 1):
        emoji = format_event_emoji(event["event_type"])
        display_name = event.get("full_name") or event.get("first_name") or "ناشناس"
        username_str = f" (@{event['username']})" if event.get("username") else ""

        text += (
            f"{emoji} <b>{i}.</b> {display_name}{username_str}\n"
        )

        if event.get("old_value") or event.get("new_value"):
            if event["old_value"]:
                text += f"   📛 {event['old_value']}"
            if event["new_value"]:
                text += f" → {event['new_value']}"
            text += "\n"

        text += f"   🕐 {event['created_at']}\n\n"

    text += f"{'─' * 25}\n📊 تعداد: {len(events)} رویداد"

    try:
        await query.edit_message_text(
            text=text,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
    except Exception:
        pass


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  سایر دستورات
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """دستور /start"""
    text = (
        "🤖 <b>سلام! من ربات مانیتور گروه هستم</b>\n\n"
        "📌 <b>امکانات من:</b>\n"
        "👋 خوش‌آمدگویی به اعضای جدید\n"
        "📢 اطلاع از خروج اعضا\n"
        "✏️ اطلاع از تغییر نام\n"
        "🔄 اطلاع از تغییر آیدی\n"
        "📸 اطلاع از تغییر عکس پروفایل\n"
        "📊 گزارش کامل فعالیت‌ها\n\n"
        "💡 <b>من رو به گروه اضافه کن تا شروع کنم!</b>\n\n"
        "📝 <b>دستورات:</b>\n"
        "/lm - گزارش کامل فعالیت‌ها (فقط ادمین)\n"
        "/lm [عدد] - گزارش با تعداد مشخص\n"
        "/setwelcome [متن] - تنظیم پیام خوش‌آمدگویی (فقط ادمین)\n"
        "/togglewelcome - فعال/غیرفعال خوش‌آمدگویی (فقط ادمین)\n"
        "/stats - آمار سریع گروه\n"
        "/help - راهنما"
    )
    await safe_reply(update, text)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """دستور /help"""
    text = (
        "📖 <b>راهنمای ربات مانیتور گروه</b>\n"
        f"{'─' * 30}\n\n"
        "🔑 <b>دستورات ادمین:</b>\n\n"
        "📊 <code>/lm</code>\n"
        "   → نمایش گزارش کامل فعالیت‌ها\n"
        "   → شامل: ورود، خروج، تغییر نام، آیدی، پروفایل\n\n"
        "📊 <code>/lm 50</code>\n"
        "   → نمایش ۵۰ رویداد آخر\n\n"
        "💬 <code>/setwelcome سلام {name} به {chat_title} خوش آمدی!</code>\n"
        "   → تنظیم پیام خوش‌آمدگویی سفارشی\n"
        "   → متغیرها: {name}, {chat_title}, {first_name}, {last_name}, {username}, {user_id}\n\n"
        "🔘 <code>/togglewelcome</code>\n"
        "   → فعال/غیرفعال کردن خوش‌آمدگویی\n\n"
        "📈 <code>/stats</code>\n"
        "   → نمایش آمار سریع گروه\n\n"
        "🔔 <b>قابلیت‌های خودکار:</b>\n"
        "✅ خوش‌آمدگویی به اعضای جدید\n"
        "✅ اطلاع از خروج اعضا\n"
        "✅ اطلاع از تغییر نام\n"
        "✅ اطلاع از تغییر آیدی/یوزرنیم\n"
        "✅ اطلاع از تغییر عکس پروفایل\n"
    )
    await safe_reply(update, text)


async def set_welcome_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """تنظیم پیام خوش‌آمدگویی سفارشی"""
    chat = update.effective_chat
    user = update.effective_user

    if not is_admin(chat, user.id, context):
        await safe_reply(update, "⛔ این دستور فقط برای ادمین‌هاست!")
        return

    if not context.args:
        current = db.get_group_settings(chat.id)
        current_msg = current.get("welcome_message") if current else None
        text = (
            "💬 <b>تنظیم پیام خوش‌آمدگویی</b>\n\n"
            f"📝 پیام فعلی:\n<code>{current_msg or Config.DEFAULT_WELCOME_MESSAGE}</code>\n\n"
            "📌 <b>متغیرهای قابل استفاده:</b>\n"
            "• <code>{name}</code> - نام کاربر (با لینک)\n"
            "• <code>{chat_title}</code> - نام گروه\n"
            "• <code>{first_name}</code> - نام کوچک\n"
            "• <code>{last_name}</code> - نام خانوادگی\n"
            "• <code>{username}</code> - یوزرنیم\n"
            "• <code>{user_id}</code> - آیدی عددی\n\n"
            "💡 <b>مثال:</b>\n"
            "<code>/setwelcome 🎉 سلام {name}! به {chat_title} خوش آمدی!</code>"
        )
        await safe_reply(update, text)
        return

    welcome_text = " ".join(context.args)
    db.upsert_group(chat.id, chat.title or "")
    db.set_welcome_message(chat.id, welcome_text)

    await safe_reply(
        update,
        f"✅ <b>پیام خوش‌آمدگویی ذخیره شد!</b>\n\n"
        f"📝 پیش‌نمایش:\n{welcome_text}",
    )


async def toggle_welcome_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """فعال/غیرفعال کردن خوش‌آمدگویی"""
    chat = update.effective_chat
    user = update.effective_user

    if not is_admin(chat, user.id, context):
        await safe_reply(update, "⛔ این دستور فقط برای ادمین‌هاست!")
        return

    settings = db.get_group_settings(chat.id)
    if not settings:
        db.upsert_group(chat.id, chat.title or "")
        settings = db.get_group_settings(chat.id)

    current = bool(settings.get("welcome_enabled", 1))
    new_state = not current
    db.toggle_welcome(chat.id, new_state)

    status = "✅ فعال" if new_state else "❌ غیرفعال"
    await safe_reply(update, f"🔘 <b>خوش‌آمدگویی:</b> {status}")


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """نمایش آمار سریع گروه"""
    chat = update.effective_chat

    if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        await safe_reply(update, "⛔ این دستور فقط در گروه‌ها کار می‌کند!")
        return

    stats = db.get_group_stats(chat.id)
    total = sum(stats.values())

    text = (
        f"📈 <b>آمار گروه {chat.title}</b>\n"
        f"{'─' * 25}\n\n"
        f"🟢 ورود: <b>{stats.get('join', 0)}</b>\n"
        f"🔴 خروج: <b>{stats.get('left', 0)}</b>\n"
        f"✏️ تغییر نام: <b>{stats.get('name_change', 0)}</b>\n"
        f"🔄 تغییر آیدی: <b>{stats.get('username_change', 0)}</b>\n"
        f"📸 تغییر پروفایل: <b>{stats.get('photo_change', 0)}</b>\n"
        f"{'─' * 25}\n"
        f"📊 مجموع: <b>{total}</b> رویداد\n\n"
        f"💡 برای گزارش کامل: <code>/lm</code>"
    )
    await safe_reply(update, text)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  هندلر اضافه شدن ربات به گروه
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def greet_on_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """هنگام اضافه شدن ربات به گروه"""
    chat = update.effective_chat

    if chat.type in (ChatType.GROUP, ChatType.SUPERGROUP):
        db.upsert_group(chat.id, chat.title or "")

        text = (
            f"🤖 <b>سلام! من اضافه شدم!</b>\n\n"
            f"✅ از این به بعد فعالیت‌های گروه «{chat.title}» رو مانیتور می‌کنم:\n\n"
            f"👋 خوش‌آمدگویی به اعضای جدید\n"
            f"📢 اطلاع از خروج اعضا\n"
            f"✏️ اطلاع از تغییر نام\n"
            f"🔄 اطلاع از تغییر آیدی\n"
            f"📸 اطلاع از تغییر عکس پروفایل\n\n"
            f"📋 برای گزارش: <code>/lm</code>\n"
            f"📖 راهنما: <code>/help</code>"
        )

        try:
            await chat.send_message(text=text, parse_mode="HTML")
        except Exception as e:
            logger.error(f"خطا در ارسال پیام شروع: {e}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  ثبت تمام هندلرها
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def register_handlers(application) -> None:
    """ثبت تمام هندلرها در اپلیکیشن"""

    # ─── هندلر اضافه شدن به گروه ───
    application.add_handler(
        MessageHandler(
            filters.StatusUpdate.NEW_CHAT_MEMBERS,
            greet_on_add,
        )
    )

    # ─── هندلر تغییرات اعضا (ورود، خروج، تغییر نام/آیدی) ───
    application.add_handler(
        ChatMemberHandler(track_chat_members, ChatMemberHandler.CHAT_MEMBER)
    )

    # ─── هندلر بررسی پروفایل ───
    application.add_handler(
        MessageHandler(
            filters.ChatType.GROUPS & ~filters.COMMAND,
            track_profile_photo,
        )
    )

    # ─── دستورات ───
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("lm", report_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("setwelcome", set_welcome_command))
    application.add_handler(CommandHandler("togglewelcome", toggle_welcome_command))

    # ─── دکمه‌های شیشه‌ای ───
    application.add_handler(
        MessageHandler(
            filters.Regex(r"^report_"),
            report_callback,
        )
    )

    logger.info("✅ تمام هندلرها با موفقیت ثبت شدند")
