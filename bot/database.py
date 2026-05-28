"""
مدیریت دیتابیس SQLite
"""
import aiosqlite
import os
from datetime import datetime
from typing import Optional, List, Tuple


class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

    async def init(self):
        """ساخت جداول اولیه"""
        async with aiosqlite.connect(self.db_path) as db:
            # جدول کاربران برای ردیابی تغییرات
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    chat_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    first_name TEXT,
                    last_name TEXT,
                    username TEXT,
                    photo_id TEXT,
                    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (chat_id, user_id)
                )
            """)
            
            # جدول لاگ رویدادها
            await db.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    event_type TEXT NOT NULL,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            await db.execute("CREATE INDEX IF NOT EXISTS idx_events_chat ON events(chat_id)")
            await db.commit()

    async def get_user(self, chat_id: int, user_id: int) -> Optional[dict]:
        """دریافت اطلاعات کاربر"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM users WHERE chat_id=? AND user_id=?",
                (chat_id, user_id)
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def upsert_user(self, chat_id: int, user_id: int,
                          first_name: str, last_name: str,
                          username: str, photo_id: str):
        """افزودن یا بروزرسانی کاربر"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO users (chat_id, user_id, first_name, last_name, username, photo_id, last_seen)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(chat_id, user_id) DO UPDATE SET
                    first_name=excluded.first_name,
                    last_name=excluded.last_name,
                    username=excluded.username,
                    photo_id=excluded.photo_id,
                    last_seen=CURRENT_TIMESTAMP
            """, (chat_id, user_id, first_name, last_name, username, photo_id))
            await db.commit()

    async def log_event(self, chat_id: int, user_id: int,
                        event_type: str, description: str):
        """ثبت رویداد در لاگ"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO events (chat_id, user_id, event_type, description) VALUES (?, ?, ?, ?)",
                (chat_id, user_id, event_type, description)
            )
            await db.commit()

    async def get_events(self, chat_id: int, limit: int = 100) -> List[Tuple]:
        """دریافت لیست رویدادهای یک گروه"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                """SELECT event_type, description, created_at 
                   FROM events WHERE chat_id=? 
                   ORDER BY created_at DESC LIMIT ?""",
                (chat_id, limit)
            ) as cursor:
                return await cursor.fetchall()

    async def clear_events(self, chat_id: int):
        """پاک کردن لاگ‌های یک گروه"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM events WHERE chat_id=?", (chat_id,))
            await db.commit()
