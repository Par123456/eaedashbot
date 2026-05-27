"""
🚀 فایل اصلی ربات - نقطه شروع اجرا
Telegram Group Monitor Bot - Main Entry Point
"""

import logging
import os
import sys

from telegram.ext import (
    Application,
    ApplicationBuilder,
)

from config import Config
from handlers import register_handlers

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  تنظیمات لاگ
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

logging.basicConfig(
    format="%(asctime)s │ %(name)s │ %(levelname)s │ %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=getattr(logging, Config.LOG_LEVEL, logging.INFO),
)

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


def main() -> None:
    """اجرای ربات"""

    # ─── اعتبارسنجی تنظیمات ───
    logger.info("🔧 بررسی تنظیمات...")
    Config.validate()
    logger.info("✅ تنظیمات معتبر هستند")

    # ─── ساخت اپلیکیشن ───
    logger.info("🚀 در حال راه‌اندازی ربات...")

    application = (
        ApplicationBuilder()
        .token(Config.BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    # ─── ثبت هندلرها ───
    register_handlers(application)

    # ─── اجرای ربات ───
    logger.info("=" * 50)
    logger.info("🤖 ربات مانیتور گروه فعال شد!")
    logger.info("📡 در حال دریافت آپدیت‌ها...")
    logger.info("=" * 50)

    application.run_polling(
        drop_pending_updates=True,
        allowed_updates=Application.ALL_TYPES,
    )


async def post_init(application: Application) -> None:
    """عملیات بعد از مقداردهی اولیه"""
    bot_info = await application.bot.get_me()
    logger.info(f"🤖 ربات: @{bot_info.username} ({bot_info.first_name})")

    # ساخت پوشه دیتابیس
    db_dir = os.path.dirname(Config.DATABASE_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)


async def post_shutdown(application: Application) -> None:
    """عملیات قبل از خاموش شدن"""
    logger.info("👋 ربات در حال خاموش شدن...")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  اجرا
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("⛔ ربات با Ctrl+C متوقف شد")
    except ValueError as e:
        logger.error(str(e))
        sys.exit(1)
    except Exception as e:
        logger.critical(f"💥 خطای بحرانی: {e}", exc_info=True)
        sys.exit(1)
