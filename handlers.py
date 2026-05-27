"""
🎯 ماژول هندلرها - پردازش تمام رویدادهای ربات
Telegram Group Monitor Bot - Event Handlers
"""

import logging
from datetime import datetime
from typing import Any

from telegram import (
    Chat,
    ChatMemberUpdated,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
    User,
)
from telegram.constants import ChatMemberStatus, ChatType
from telegram.ext import (
    CallbackQueryHandler,
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
#  نمونه دیتابیس و ثابت‌ها
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

db = Database()

EMOJI_MAP = {
    "join": "🟢",
    "left": "🔴",
    "name_change": "✏️",
    "username_change": "🔄",
    "photo_change": "📸",
}

EVENT_NAMES = {
    "join": "ورود به گروه",
    "left": "خروج از گروه",
    "name_change": "تغییر نام",
    "username_change": "تغییر آیدی",
    "photo_change": "تغییر پروفایل",
}

CALLBACK_TYPE_MAP = {
    "report_join": "join",
    "report_left": "left",
    "report_name": "name_change",
    "report_username": "username_change",
    "report_photo": "photo_change",
}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  ابزارهای کمکی
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def extract_status_change(
    chat_member_update: ChatMemberUpdated,
) -> tuple[str | None, str | None]:
    """استخراج تغییر وضعیت کاربر → (old_status, new_status)"""
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
    return EMOJI_MAP.get(event_type, "📌")


def format_event_name(event_type: str) -> str:
    """دریافت نام فارسی نوع رویداد"""
    return EVENT_NAMES.get(event_type, event_type)


def is_admin(chat: Chat, user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """بررسی ادمین بودن کاربر"""
    try:
        member = chat.get_member(user_id)
        return member.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER)
    except Exception:
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
        logger.error("خطا در ارسال پیام: %s", e)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  هندلر رویدادهای اعضا (ورود، خروج، تغییر نام/آیدی)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def _handle_join(chat, user, update, old_status, new_status) -> bool:
    """پردازش ورود عضو جدید. True اگر ورود بود."""
    return old_status in (ChatMemberStatus.LEFT, ChatMemberStatus.BANNED) and new_status == ChatMemberStatus.MEMBER


def _handle_left(old_status, new_status) -> bool:
    """پردازش خروج عضو. True اگر خروج بود."""
    return old_status == ChatMemberStatus.MEMBER and new_status in (ChatMemberStatus.LEFT, ChatMemberStatus.BANNED)


def _is_still_member(status) -> bool:
    """آیا کاربر هنوز عضو است (برای بررسی تغییر نام/آیدی)"""
    return status in (
        ChatMemberStatus.MEMBER,
        ChatMemberStatus.ADMINISTRATOR,
        ChatMemberStatus.OWNER,
    )


async def _send_welcome(chat, user, update) -> None:
    """ارسال پیام خوش‌آمدگویی"""
    settings = db.get_group_settings(chat.id)
    if not settings or not settings.get("welcome_enabled", 1):
        return

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


async def _check_name_change(update, chat, old_user, new_user) -> None:
    """بررسی و اعلام تغییر نام"""
    old_name = get_user_display_name(old_user)
    new_name = get_user_display_name(new_user)
    if old_name == new_name:
        return

    db.log_event(
        chat_id=chat.id,
        user_id=new_user.id,
        event_type="name_change",
        old_value=old_name,
        new_value=new_name,
    )
    mention = get_user_mention(new_user)
    text = (
        "✏️ <b>تغییر نام</b>\n\n"
        f"👤 کاربر: {mention}\n"
        f"📛 نام قبلی: <s>{old_name}</s>\n"
        f"✅ نام جدید: <b>{new_name}</b>"
    )
    await safe_reply(update, text)
    logger.info("✏️ نام: %s → %s", old_name, new_name)


async def _check_username_change(update, chat, old_user, new_user) -> None:
    """بررسی و اعلام تغییر آیدی"""
    old_username = old_user.username or ""
    new_username = new_user.username or ""
    if old_username == new_username:
        return

    old_display = f"@{old_username}" if old_username else "ندارد"
    new_display = f"@{new_username}" if new_username else "ندارد"
    db.log_event(
        chat_id=chat.id,
        user_id=new_user.id,
        event_type="username_change",
        old_value=old_display,
        new_value=new_display,
    )
    mention = get_user_mention(new_user)
    text = (
        "🔄 <b>تغییر آیدی</b>\n\n"
        f"👤 کاربر: {mention}\n"
        f"📛 آیدی قبلی: <code>{old_display}</code>\n"
        f"✅ آیدی جدید: <code>{new_display}</code>"
    )
    await safe_reply(update, text)
    logger.info("🔄 آیدی: %s → %s", old_display, new_display)


async def track_chat_members(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """پردازش تغییرات اعضای گروه: ورود، خروج، تغییر نام، تغییر آیدی"""
    old_status, new_status = extract_status_change(update.chat_member)
    chat = update.effective_chat
    user = update.chat_member.new_chat_member.user

    # ثبت اطلاعات کاربر و گروه
    db.upsert_user(
        user_id=user.id,
        first_name=user.first_name or "",
        last_name=user.last_name or "",
        username=user.username or "",
    )
    if chat.type in (ChatType.GROUP, ChatType.SUPERGROUP):
        db.upsert_group(chat_id=chat.id, chat_title=chat.title or "")

    # ─── ورود عضو جدید ───
    if _handle_join(chat, user, update, old_status, new_status):
        db.log_event(
            chat_id=chat.id,
            user_id=user.id,
            event_type="join",
            new_value=get_user_display_name(user),
        )
        logger.info("✅ %s وارد %s شد", get_user_display_name(user), chat.title)
        await _send_welcome(chat, user, update)

    # ─── خروج عضو ───
    elif _handle_left(old_status, new_status):
        db.log_event(
            chat_id=chat.id,
            user_id=user.id,
            event_type="left",
            old_value=get_user_display_name(user),
        )
        logger.info("❌ %s از %s خارج شد", get_user_display_name(user), chat.title)

    # ─── تغییر نام/آیدی (فقط اگر هنوز عضو باشد) ───
    if old_status == new_status and _is_still_member(old_status):
        old_user = update.chat_member.old_chat_member.user
        new_user = update.chat_member.new_chat_member.user
        await _check_name_change(update, chat, old_user, new_user)
        await _check_username_change(update, chat, old_user, new_user)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  هندلر تشخیص تغییر پروفایل
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


async def track_profile_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """بررسی تغییر عکس پروفایل کاربران هنگام ارسال پیام"""
    if not update.effective_user:
        return

    chat = update.effective_chat
    user = update.effective_user

    if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return

    try:
        photos = await context.bot.get_user_profile_photos(user_id=user.id, limit=1)
        current_photo_id = None
        if photos.total_count > 0:
            current_photo_id = photos.photos[0][-1].file_id

        stored_user = db.get_user(user.id)
        if stored_user and stored_user.get("photo_file_id"):
            if stored_user["photo_file_id"] != current_photo_id:
                db.log_event(
                    chat_id=chat.id,
                    user_id=user.id,
                    event_type="photo_change",
                    old_value=stored_user["photo_file_id"],
                    new_value=current_photo_id or "حذف شده",
                )
                mention = get_user_mention(user)
                text = (
                    "📸 <b>تغییر عکس پروفایل</b>\n\n"
                    f"👤 کاربر: {mention}\n"
                    f"🕐 زمان: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                )
                await safe_reply(update, text)
                logger.info("📸 پروفایل %s تغییر کرد", get_user_display_name(user))

        db.upsert_user(
            user_id=user.id,
            first_name=user.first_name or "",
            last_name=user.last_name or "",
            username=user.username or "",
            photo_file_id=current_photo_id,
        )
    except Exception as e:
        logger.debug("خطا در بررسی پروفایل: %s", e)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  هندلر گزارش (دستور /lm)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def _build_event_detail(event: dict) -> str:
    """ساخت جزئیات یک رویداد برای گزارش"""
    etype = event["event_type"]
    if etype in ("name_change", "username_change"):
        lines = ""
        if event.get("old_value"):
            lines += f"   📛 قبلی: <code>{event['old_value']}</code>\n"
        if event.get("new_value"):
            lines += f"   ✅ جدید: <code>{event['new_value']}</code>\n"
        return lines
    descriptions = {
        "photo_change": "   📸 عکس پروفایل تغییر کرد\n",
        "join": "   🟢 وارد گروه شد\n",
        "left": "   🔴 از گروه خارج شد\n",
    }
    return descriptions.get(etype, "")


def _build_report_text(chat, stats: dict, events: list[dict]) -> str:
    """ساخت متن کامل گزارش"""
    separator = "─" * 30
    total_events = sum(stats.values())

    report = (
        f"📊 <b>گزارش کامل فعالیت‌های گروه</b>\n"
        f"🏷️ <b>{chat.title}</b>\n"
        f"{separator}\n\n"
        f"📈 <b>آمار کلی:</b>\n"
        f"🟢 ورود: <b>{stats.get('join', 0)}</b>\n"
        f"🔴 خروج: <b>{stats.get('left', 0)}</b>\n"
        f"✏️ تغییر نام: <b>{stats.get('name_change', 0)}</b>\n"
        f"🔄 تغییر آیدی: <b>{stats.get('username_change', 0)}</b>\n"
        f"📸 تغییر پروفایل: <b>{stats.get('photo_change', 0)}</b>\n"
        f"{separator}\n\n"
        f"📋 <b>آخرین {len(events)} رویداد:</b>\n\n"
    )

    for i, event in enumerate(events, 1):
        emoji = format_event_emoji(event["event_type"])
        event_name = format_event_name(event["event_type"])
        display_name = event.get("full_name") or event.get("first_name") or "ناشناس"
        username_str = f" (@{event['username']})" if event.get("username") else ""

        report += f"{emoji} <b>{i}.</b> {event_name}\n"
        report += f"   👤 {display_name}{username_str}\n"
        report += _build_event_detail(event)
        report += f"   🕐 {event['created_at']}\n\n"

    report += f"{separator}\n📊 مجموع: <b>{total_events}</b> رویداد"
    return report


def _build_report_keyboard() -> InlineKeyboardMarkup:
    """ساخت کیبورد گزارش"""
    return InlineKeyboardMarkup(
        [
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
        ]
    )


async def report_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """دستور /lm - نمایش گزارش کامل فعالیت‌های گروه (فقط ادمین)"""
    chat = update.effective_chat
    user = update.effective_user

    if not is_admin(chat, user.id, context):
        await safe_reply(update, "⛔ این دستور فقط برای ادمین‌هاست!")
        return

    if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        await safe_reply(update, "⛔ این دستور فقط در گروه‌ها کار می‌کند!")
        return

    limit = Config.REPORT_PAGE_SIZE
    args = context.args or []
    if args:
        try:
            limit = min(int(args[0]), 100)
        except ValueError:
            pass

    stats = db.get_group_stats(chat.id)
    events = db.get_group_report(chat.id, limit=limit)

    if not events:
        await safe_reply(update, "📭 هیچ رویدادی ثبت نشده است!")
        return

    report = _build_report_text(chat, stats, events)
    keyboard = _build_report_keyboard()
    await safe_reply(update, report, reply_markup=keyboard)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  هندلر دکمه‌های شیشه‌ای گزارش
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def _build_callback_text(events: list[dict], title: str) -> str:
    """ساخت متن پاسخ callback"""
    separator = "─" * 25
    text = f"{title}\n{separator}\n\n"

    for i, event in enumerate(events, 1):
        emoji = format_event_emoji(event["event_type"])
        display_name = event.get("full_name") or event.get("first_name") or "ناشناس"
        username_str = f" (@{event['username']})" if event.get("username") else ""

        text += f"{emoji} <b>{i}.</b> {display_name}{username_str}\n"

        parts = []
        if event.get("old_value"):
            parts.append(event["old_value"])
        if event.get("new_value"):
            parts.append(event["new_value"])
        if parts:
            text += f"   {' → '.join(parts)}\n"

        text += f"   🕐 {event['created_at']}\n\n"

    text += f"{separator}\n📊 تعداد: {len(events)} رویداد"
    return text


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

    if data == "report_all":
        events = db.get_group_report(chat.id, limit=50)
        title = "📋 گزارش کامل"
    elif data in CALLBACK_TYPE_MAP:
        event_type = CALLBACK_TYPE_MAP[data]
        events = db.get_events_by_type(chat.id, event_type, limit=50)
        title = f"{format_event_emoji(event_type)} {format_event_name(event_type)}"
    else:
        return

    if not events:
        await query.answer("📭 رویدادی یافت نشد!", show_alert=True)
        return

    text = _build_callback_text(events, title)

    try:
        await query.edit_message_text(text=text, parse_mode="HTML", disable_web_page_preview=True)
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
    separator = "─" * 30
    text = (
        f"📖 <b>راهنمای ربات مانیتور گروه</b>\n"
        f"{separator}\n\n"
        "🔑 <b>دستورات ادمین:</b>\n\n"
        "📊 <code>/lm</code>\n"
        "   → گزارش کامل فعالیت‌ها\n\n"
        "📊 <code>/lm 50</code>\n"
        "   → ۵۰ رویداد آخر\n\n"
        "💬 <code>/setwelcome سلام {name} به {chat_title} خوش آمدی!</code>\n"
        "   → تنظیم پیام خوش‌آمدگویی سفارشی\n\n"
        "🔘 <code>/togglewelcome</code>\n"
        "   → فعال/غیرفعال خوش‌آمدگویی\n\n"
        "📈 <code>/stats</code>\n"
        "   → آمار سریع گروه\n\n"
        "🔔 <b>قابلیت‌های خودکار:</b>\n"
        "✅ خوش‌آمدگویی به اعضای جدید\n"
        "✅ اطلاع از خروج اعضا\n"
        "✅ اطلاع از تغییر نام/آیدی\n"
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
            "📌 <b>متغیرها:</b>\n"
            "• <code>{name}</code> - نام کاربر\n"
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
        "✅ <b>پیام خوش‌آمدگویی ذخیره شد!</b>\n\n" f"📝 پیش‌نمایش:\n{welcome_text}",
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

    new_state = not bool(settings.get("welcome_enabled", 1))
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
    separator = "─" * 25

    text = (
        f"📈 <b>آمار گروه {chat.title}</b>\n"
        f"{separator}\n\n"
        f"🟢 ورود: <b>{stats.get('join', 0)}</b>\n"
        f"🔴 خروج: <b>{stats.get('left', 0)}</b>\n"
        f"✏️ تغییر نام: <b>{stats.get('name_change', 0)}</b>\n"
        f"🔄 تغییر آیدی: <b>{stats.get('username_change', 0)}</b>\n"
        f"📸 تغییر پروفایل: <b>{stats.get('photo_change', 0)}</b>\n"
        f"{separator}\n"
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

    if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return

    db.upsert_group(chat.id, chat.title or "")

    text = (
        f"🤖 <b>سلام! من اضافه شدم!</b>\n\n"
        f"✅ از این به بعد فعالیت‌های گروه «{chat.title}» رو مانیتور می‌کنم:\n\n"
        "👋 خوش‌آمدگویی به اعضای جدید\n"
        "📢 اطلاع از خروج اعضا\n"
        "✏️ اطلاع از تغییر نام\n"
        "🔄 اطلاع از تغییر آیدی\n"
        "📸 اطلاع از تغییر عکس پروفایل\n\n"
        "📋 برای گزارش: <code>/lm</code>\n"
        "📖 راهنما: <code>/help</code>"
    )

    try:
        await chat.send_message(text=text, parse_mode="HTML")
    except Exception as e:
        logger.error("خطا در ارسال پیام شروع: %s", e)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  ثبت تمام هندلرها
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def register_handlers(application) -> None:
    """ثبت تمام هندلرها در اپلیکیشن"""

    # هندلر اضافه شدن به گروه
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, greet_on_add))

    # هندلر تغییرات اعضا (ورود، خروج، تغییر نام/آیدی)
    application.add_handler(ChatMemberHandler(track_chat_members, ChatMemberHandler.CHAT_MEMBER))

    # هندلر بررسی پروفایل
    application.add_handler(
        MessageHandler(
            filters.ChatType.GROUPS & ~filters.COMMAND,
            track_profile_photo,
        )
    )

    # دستورات
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("lm", report_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("setwelcome", set_welcome_command))
    application.add_handler(CommandHandler("togglewelcome", toggle_welcome_command))

    # دکمه‌های شیشه‌ای (Callback)
    application.add_handler(CallbackQueryHandler(report_callback, pattern="^report_"))

    logger.info("✅ تمام هندلرها با موفقیت ثبت شدند")
