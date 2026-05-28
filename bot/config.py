"""
تنظیمات اصلی ربات
"""
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    BOT_TOKEN = os.getenv("BOT_TOKEN", "")
    DATABASE_PATH = os.getenv("DATABASE_PATH", "data/bot.db")
    
    # پیام‌های فارسی
    WELCOME_MESSAGE = (
        "🌹 خوش اومدی {name} عزیز به گروه!\n"
        "🎉 امیدواریم اوقات خوبی داشته باشی."
    )
    
    NAME_CHANGED = "✏️ کاربر {old_name} اسمش رو به {new_name} تغییر داد."
    USERNAME_CHANGED = "🔖 کاربر {name} یوزرنیمش رو از @{old} به @{new} تغییر داد."
    USERNAME_SET = "🔖 کاربر {name} یوزرنیم گذاشت: @{new}"
    USERNAME_REMOVED = "🔖 کاربر {name} یوزرنیمش (@{old}) رو حذف کرد."
    PHOTO_CHANGED = "🖼 کاربر {name} عکس پروفایلش رو تغییر داد."
    USER_LEFT = "👋 کاربر {name} از گروه خارج شد."
    
    NOT_ADMIN = "⛔️ این دستور فقط برای ادمین‌های گروه قابل استفاده است."
    NO_LOGS = "📭 هیچ لاگی برای این گروه ثبت نشده است."
    LOG_HEADER = "📋 گزارش فعالیت‌های گروه:\n\n"

    if not BOT_TOKEN:
        raise ValueError("❌ BOT_TOKEN در محیط تنظیم نشده!")
