"""
نقطه شروع ربات
"""
import asyncio
import logging
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    ChatMemberHandler, filters
)

from bot.config import Config
from bot.database import Database
from bot.handlers import BotHandlers


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


async def post_init(app: Application):
    db: Database = app.bot_data["db"]
    await db.init()
    logger.info("✅ دیتابیس آماده شد.")


def main():
    db = Database(Config.DATABASE_PATH)
    handlers = BotHandlers(db)

    app = (
        Application.builder()
        .token(Config.BOT_TOKEN)
        .post_init(post_init)
        .build()
    )
    app.bot_data["db"] = db

    # دستورات
    app.add_handler(CommandHandler("start", handlers.cmd_start))
    app.add_handler(CommandHandler("lm", handlers.cmd_lm))

    # ردیابی پیام‌ها در گروه
    app.add_handler(MessageHandler(
        filters.ChatType.GROUPS & ~filters.StatusUpdate.ALL,
        handlers.track_message
    ))

    # ورود/خروج اعضا
    app.add_handler(ChatMemberHandler(
        handlers.chat_member_update,
        ChatMemberHandler.CHAT_MEMBER
    ))

    logger.info("🤖 ربات در حال اجرا...")
    app.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True
    )


if __name__ == "__main__":
    main()
