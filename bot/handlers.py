"""
هندلرهای رویدادهای تلگرام
"""
from telegram import Update, ChatMemberUpdated, User
from telegram.ext import ContextTypes
from telegram.constants import ChatMemberStatus
from datetime import datetime

from bot.config import Config
from bot.database import Database


def full_name(user: User) -> str:
    """نام کامل کاربر"""
    name = user.first_name or ""
    if user.last_name:
        name += f" {user.last_name}"
    return name.strip() or "ناشناس"


async def get_photo_id(user: User, context: ContextTypes.DEFAULT_TYPE) -> str:
    """گرفتن ID عکس پروفایل کاربر"""
    try:
        photos = await context.bot.get_user_profile_photos(user.id, limit=1)
        if photos.total_count > 0 and photos.photos:
            return photos.photos[0][0].file_unique_id
    except Exception:
        pass
    return ""


class BotHandlers:
    def __init__(self, db: Database):
        self.db = db

    # ───────────────────────────────────────
    # ورود و خروج کاربران
    # ───────────────────────────────────────
    async def chat_member_update(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """تغییر وضعیت اعضای گروه (ورود/خروج)"""
        result: ChatMemberUpdated = update.chat_member
        if not result:
            return

        old_status = result.old_chat_member.status
        new_status = result.new_chat_member.status
        user = result.new_chat_member.user
        chat_id = result.chat.id

        was_member = old_status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]
        is_member = new_status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]

        name = full_name(user)

        # کاربر جدید وارد شد
        if not was_member and is_member:
            photo_id = await get_photo_id(user, context)
            await self.db.upsert_user(
                chat_id, user.id,
                user.first_name or "",
                user.last_name or "",
                user.username or "",
                photo_id
            )
            
            welcome = Config.WELCOME_MESSAGE.format(name=name)
            await context.bot.send_message(chat_id, welcome)
            await self.db.log_event(chat_id, user.id, "JOIN", f"{name} وارد گروه شد")

        # کاربر خارج شد
        elif was_member and not is_member:
            text = Config.USER_LEFT.format(name=name)
            await context.bot.send_message(chat_id, text)
            await self.db.log_event(chat_id, user.id, "LEAVE", f"{name} از گروه خارج شد")

    # ───────────────────────────────────────
    # بررسی تغییرات روی پیام‌های ارسالی
    # ───────────────────────────────────────
    async def track_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ردیابی تغییرات کاربر هنگام ارسال پیام"""
        message = update.effective_message
        if not message or not message.from_user or message.chat.type == "private":
            return

        user = message.from_user
        chat_id = message.chat.id

        # کاربر فعلی از دیتابیس
        stored = await self.db.get_user(chat_id, user.id)
        photo_id = await get_photo_id(user, context)

        new_name = full_name(user)
        new_username = user.username or ""

        if stored:
            old_full = (stored["first_name"] or "")
            if stored["last_name"]:
                old_full += f" {stored['last_name']}"
            old_full = old_full.strip()

            # تغییر نام
            if old_full and old_full != new_name:
                text = Config.NAME_CHANGED.format(old_name=old_full, new_name=new_name)
                await context.bot.send_message(chat_id, text)
                await self.db.log_event(chat_id, user.id, "NAME_CHANGE",
                                         f"تغییر نام از «{old_full}» به «{new_name}»")

            # تغییر یوزرنیم
            old_username = stored["username"] or ""
            if old_username != new_username:
                if old_username and new_username:
                    text = Config.USERNAME_CHANGED.format(
                        name=new_name, old=old_username, new=new_username)
                    desc = f"یوزرنیم {new_name} از @{old_username} به @{new_username}"
                elif new_username:
                    text = Config.USERNAME_SET.format(name=new_name, new=new_username)
                    desc = f"یوزرنیم {new_name} تنظیم شد: @{new_username}"
                else:
                    text = Config.USERNAME_REMOVED.format(name=new_name, old=old_username)
                    desc = f"یوزرنیم {new_name} (@{old_username}) حذف شد"
                
                await context.bot.send_message(chat_id, text)
                await self.db.log_event(chat_id, user.id, "USERNAME_CHANGE", desc)

            # تغییر عکس پروفایل
            old_photo = stored["photo_id"] or ""
            if photo_id and old_photo and photo_id != old_photo:
                text = Config.PHOTO_CHANGED.format(name=new_name)
                await context.bot.send_message(chat_id, text)
                await self.db.log_event(chat_id, user.id, "PHOTO_CHANGE",
                                         f"عکس پروفایل {new_name} تغییر کرد")

        # بروزرسانی اطلاعات
        await self.db.upsert_user(
            chat_id, user.id,
            user.first_name or "",
            user.last_name or "",
            new_username,
            photo_id
        )

    # ───────────────────────────────────────
    # دستور /lm – نمایش لاگ‌ها (فقط ادمین)
    # ───────────────────────────────────────
    async def cmd_lm(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """نمایش لاگ گروه - فقط برای ادمین‌ها"""
        message = update.effective_message
        if not message or message.chat.type == "private":
            return

        chat_id = message.chat.id
        user_id = message.from_user.id

        # بررسی ادمین بودن
        try:
            member = await context.bot.get_chat_member(chat_id, user_id)
            if member.status not in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
                await message.reply_text(Config.NOT_ADMIN)
                return
        except Exception:
            await message.reply_text(Config.NOT_ADMIN)
            return

        events = await self.db.get_events(chat_id, limit=100)
        if not events:
            await message.reply_text(Config.NO_LOGS)
            return

        # ساخت متن گزارش
        icons = {
            "JOIN": "✅",
            "LEAVE": "👋",
            "NAME_CHANGE": "✏️",
            "USERNAME_CHANGE": "🔖",
            "PHOTO_CHANGE": "🖼",
        }

        text = Config.LOG_HEADER
        for event_type, description, created_at in events:
            icon = icons.get(event_type, "•")
            try:
                dt = datetime.fromisoformat(created_at)
                time_str = dt.strftime("%Y-%m-%d %H:%M")
            except Exception:
                time_str = created_at
            text += f"{icon} [{time_str}] {description}\n"

        # ارسال در چند بخش اگر طولانی بود
        max_len = 4000
        for i in range(0, len(text), max_len):
            await message.reply_text(text[i:i + max_len])

    # ───────────────────────────────────────
    # دستور start
    # ───────────────────────────────────────
    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "👋 سلام! من ربات مدیریت گروه هستم.\n"
            "منو به گروهت اضافه کن و دسترسی ادمین بده تا فعالیت‌ها رو ردیابی کنم.\n\n"
            "📌 دستورات:\n"
            "/lm — نمایش گزارش فعالیت‌ها (فقط ادمین)"
        )
