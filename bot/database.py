import aiosqlite
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

DB_PATH = "group_manager.db"


async def init_db():
    """ساخت جداول دیتابیس"""
    async with aiosqlite.connect(DB_PATH) as db:

        # جدول کاربران هر گروه
        await db.execute("""
            CREATE TABLE IF NOT EXISTS members (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id    INTEGER NOT NULL,
                user_id     INTEGER NOT NULL,
                first_name  TEXT,
                last_name   TEXT,
                username    TEXT,
                is_member   INTEGER DEFAULT 1,
                joined_at   TEXT,
                left_at     TEXT,
                UNIQUE(group_id, user_id)
            )
        """)

        # جدول لاگ رویدادها
        await db.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id    INTEGER NOT NULL,
                user_id     INTEGER NOT NULL,
                event_type  TEXT NOT NULL,
                old_value   TEXT,
                new_value   TEXT,
                happened_at TEXT NOT NULL
            )
        """)

        # جدول گروه‌ها
        await db.execute("""
            CREATE TABLE IF NOT EXISTS groups (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id    INTEGER UNIQUE NOT NULL,
                title       TEXT,
                added_at    TEXT NOT NULL
            )
        """)

        await db.commit()
        logger.info("✅ دیتابیس آماده شد")


# ──────────────────────────────────────────
#  توابع گروه
# ──────────────────────────────────────────

async def save_group(group_id: int, title: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR IGNORE INTO groups (group_id, title, added_at)
            VALUES (?, ?, ?)
        """, (group_id, title, now()))
        await db.execute("""
            UPDATE groups SET title = ? WHERE group_id = ?
        """, (title, group_id))
        await db.commit()


# ──────────────────────────────────────────
#  توابع عضو
# ──────────────────────────────────────────

async def add_member(group_id: int, user_id: int,
                     first_name: str, last_name: Optional[str],
                     username: Optional[str]):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO members
                (group_id, user_id, first_name, last_name, username, is_member, joined_at)
            VALUES (?, ?, ?, ?, ?, 1, ?)
            ON CONFLICT(group_id, user_id) DO UPDATE SET
                first_name = excluded.first_name,
                last_name  = excluded.last_name,
                username   = excluded.username,
                is_member  = 1,
                joined_at  = excluded.joined_at,
                left_at    = NULL
        """, (group_id, user_id, first_name, last_name, username, now()))
        await db.commit()


async def remove_member(group_id: int, user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE members
            SET is_member = 0, left_at = ?
            WHERE group_id = ? AND user_id = ?
        """, (now(), group_id, user_id))
        await db.commit()


async def get_member(group_id: int, user_id: int) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT * FROM members
            WHERE group_id = ? AND user_id = ?
        """, (group_id, user_id)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def update_member_info(group_id: int, user_id: int,
                              first_name: str, last_name: Optional[str],
                              username: Optional[str]):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE members
            SET first_name = ?, last_name = ?, username = ?
            WHERE group_id = ? AND user_id = ?
        """, (first_name, last_name, username, group_id, user_id))
        await db.commit()


# ──────────────────────────────────────────
#  توابع رویداد
# ──────────────────────────────────────────

async def log_event(group_id: int, user_id: int,
                    event_type: str,
                    old_value: str = None,
                    new_value: str = None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO events
                (group_id, user_id, event_type, old_value, new_value, happened_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (group_id, user_id, event_type, old_value, new_value, now()))
        await db.commit()


async def get_all_events(group_id: int) -> list[dict]:
    """همه رویدادهای یه گروه"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT
                e.*,
                m.first_name,
                m.last_name,
                m.username
            FROM events e
            LEFT JOIN members m
                ON e.group_id = m.group_id AND e.user_id = m.user_id
            WHERE e.group_id = ?
            ORDER BY e.happened_at DESC
        """, (group_id,)) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


# ──────────────────────────────────────────
#  کمکی
# ──────────────────────────────────────────

def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
