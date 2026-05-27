"""
⚙️ تنظیمات ربات مانیتور گروه تلگرام
Telegram Group Monitor Bot - Configuration
"""

import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    """تنظیمات اصلی ربات"""

    # ─── توکن ربات ───
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")

    # ─── آیدی ادمین‌های کل ربات (با کاما جدا کنید) ───
    ADMIN_IDS: list[int] = [int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()]

    # ─── مسیر دیتابیس ───
    DATABASE_PATH: str = os.getenv("DATABASE_PATH", "data/bot.db")

    # ─── تنظیمات لاگ ───
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # ─── پیام خوش‌آمدگویی پیش‌فرض ───
    DEFAULT_WELCOME_MESSAGE: str = (
        "👋 سلام {name} عزیز!\n" "🎉 به گروه «{chat_title}» خوش آمدی!\n" "💎 امیدواریم لحظات خوشی رو تجربه کنی ❤️"
    )

    # ─── حداکثر رکورد در هر صفحه گزارش ───
    REPORT_PAGE_SIZE: int = 20

    # ─── فاصله بررسی تغییر پروفایل (ثانیه) ───
    PROFILE_CHECK_INTERVAL: int = int(os.getenv("PROFILE_CHECK_INTERVAL", "3600"))

    @classmethod
    def validate(cls) -> None:
        """اعتبارسنجی تنظیمات"""
        if not cls.BOT_TOKEN:
            raise ValueError("❌ BOT_TOKEN تنظیم نشده!\n" "لطفاً متغیر محیطی BOT_TOKEN را تنظیم کنید.")
