"""
🗄️ ماژول دیتابیس - مدیریت ذخیره‌سازی رویدادها و اطلاعات کاربران
Telegram Group Monitor Bot - Database Module
"""

import os
import sqlite3
from typing import Optional

from config import Config


class Database:
    """مدیریت دیتابیس SQLite برای ذخیره رویدادها"""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or Config.DATABASE_PATH
        self._ensure_directory()
        self._init_db()

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #  مقداردهی اولیه
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def _ensure_directory(self) -> None:
        """ساخت پوشه دیتابیس اگر وجود نداشت"""
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

    def _get_connection(self) -> sqlite3.Connection:
        """دریافت اتصال به دیتابیس"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_db(self) -> None:
        """ساخت جداول دیتابیس"""
        conn = self._get_connection()
        try:
            conn.executescript("""
                -- جدول رویدادها
                CREATE TABLE IF NOT EXISTS events (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id         INTEGER NOT NULL,
                    user_id         INTEGER NOT NULL,
                    event_type      TEXT    NOT NULL,
                    old_value       TEXT    DEFAULT NULL,
                    new_value       TEXT    DEFAULT NULL,
                    extra_data      TEXT    DEFAULT NULL,
                    created_at      DATETIME DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime'))
                );

                -- جدول اطلاعات کاربران
                CREATE TABLE IF NOT EXISTS users (
                    user_id         INTEGER PRIMARY KEY,
                    first_name      TEXT    DEFAULT '',
                    last_name       TEXT    DEFAULT '',
                    username        TEXT    DEFAULT '',
                    full_name       TEXT    DEFAULT '',
                    photo_file_id   TEXT    DEFAULT NULL,
                    updated_at      DATETIME DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime'))
                );

                -- جدول تنظیمات هر گروه
                CREATE TABLE IF NOT EXISTS group_settings (
                    chat_id         INTEGER PRIMARY KEY,
                    chat_title      TEXT    DEFAULT '',
                    welcome_enabled INTEGER DEFAULT 1,
                    welcome_message TEXT    DEFAULT NULL,
                    created_at      DATETIME DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime'))
                );

                -- ایندکس‌ها برای کارایی بیشتر
                CREATE INDEX IF NOT EXISTS idx_events_chat_id    ON events(chat_id);
                CREATE INDEX IF NOT EXISTS idx_events_user_id   ON events(user_id);
                CREATE INDEX IF NOT EXISTS idx_events_type      ON events(event_type);
                CREATE INDEX IF NOT EXISTS idx_events_created   ON events(created_at);
                CREATE INDEX IF NOT EXISTS idx_events_chat_type ON events(chat_id, event_type);
            """)
            conn.commit()
        finally:
            conn.close()

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #  ثبت رویدادها
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def log_event(
        self,
        chat_id: int,
        user_id: int,
        event_type: str,
        old_value: Optional[str] = None,
        new_value: Optional[str] = None,
        extra_data: Optional[str] = None,
    ) -> int:
        """
        ثبت یک رویداد در دیتابیس

        Args:
            chat_id: آیدی گروه
            user_id: آیدی کاربر
            event_type: نوع رویداد (join, left, name_change, username_change, photo_change)
            old_value: مقدار قبلی
            new_value: مقدار جدید
            extra_data: اطلاعات اضافی

        Returns:
            آیدی رکورد ثبت شده
        """
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                "INSERT INTO events (chat_id, user_id, event_type, old_value, new_value, extra_data) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (chat_id, user_id, event_type, old_value, new_value, extra_data),
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #  مدیریت کاربران
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def upsert_user(
        self,
        user_id: int,
        first_name: str = "",
        last_name: str = "",
        username: str = "",
        photo_file_id: Optional[str] = None,
    ) -> None:
        """ذخیره یا بروزرسانی اطلاعات کاربر"""
        full_name = f"{first_name} {last_name}".strip()
        conn = self._get_connection()
        try:
            conn.execute(
                "INSERT INTO users (user_id, first_name, last_name, username, full_name, photo_file_id, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime')) "
                "ON CONFLICT(user_id) DO UPDATE SET "
                "first_name = excluded.first_name, "
                "last_name = excluded.last_name, "
                "username = excluded.username, "
                "full_name = excluded.full_name, "
                "photo_file_id = COALESCE(excluded.photo_file_id, users.photo_file_id), "
                "updated_at = strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime')",
                (user_id, first_name, last_name, username, full_name, photo_file_id),
            )
            conn.commit()
        finally:
            conn.close()

    def get_user(self, user_id: int) -> Optional[dict]:
        """دریافت اطلاعات کاربر"""
        conn = self._get_connection()
        try:
            row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #  مدیریت تنظیمات گروه
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def upsert_group(
        self,
        chat_id: int,
        chat_title: str = "",
        welcome_enabled: bool = True,
        welcome_message: Optional[str] = None,
    ) -> None:
        """ذخیره یا بروزرسانی تنظیمات گروه"""
        conn = self._get_connection()
        try:
            conn.execute(
                "INSERT INTO group_settings (chat_id, chat_title, welcome_enabled, welcome_message) "
                "VALUES (?, ?, ?, ?) "
                "ON CONFLICT(chat_id) DO UPDATE SET "
                "chat_title = excluded.chat_title, "
                "welcome_enabled = excluded.welcome_enabled, "
                "welcome_message = COALESCE(excluded.welcome_message, group_settings.welcome_message)",
                (chat_id, chat_title, int(welcome_enabled), welcome_message),
            )
            conn.commit()
        finally:
            conn.close()

    def get_group_settings(self, chat_id: int) -> Optional[dict]:
        """دریافت تنظیمات گروه"""
        conn = self._get_connection()
        try:
            row = conn.execute("SELECT * FROM group_settings WHERE chat_id = ?", (chat_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def set_welcome_message(self, chat_id: int, message: str) -> None:
        """تنظیم پیام خوش‌آمدگویی سفارشی"""
        conn = self._get_connection()
        try:
            conn.execute(
                "UPDATE group_settings SET welcome_message = ? WHERE chat_id = ?",
                (message, chat_id),
            )
            conn.commit()
        finally:
            conn.close()

    def toggle_welcome(self, chat_id: int, enabled: bool) -> None:
        """فعال/غیرفعال کردن خوش‌آمدگویی"""
        conn = self._get_connection()
        try:
            conn.execute(
                "UPDATE group_settings SET welcome_enabled = ? WHERE chat_id = ?",
                (int(enabled), chat_id),
            )
            conn.commit()
        finally:
            conn.close()

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #  گزارش‌گیری
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def get_group_report(self, chat_id: int, limit: Optional[int] = None) -> list[dict]:
        """دریافت گزارش کامل رویدادهای یک گروه"""
        limit = limit or Config.REPORT_PAGE_SIZE
        conn = self._get_connection()
        try:
            rows = conn.execute(
                "SELECT e.*, u.first_name, u.last_name, u.username, u.full_name "
                "FROM events e LEFT JOIN users u ON e.user_id = u.user_id "
                "WHERE e.chat_id = ? ORDER BY e.created_at DESC LIMIT ?",
                (chat_id, limit),
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def get_group_stats(self, chat_id: int) -> dict:
        """دریافت آمار کلی گروه"""
        conn = self._get_connection()
        try:
            stats = {}
            for etype in ("join", "left", "name_change", "username_change", "photo_change"):
                row = conn.execute(
                    "SELECT COUNT(*) as count FROM events WHERE chat_id = ? AND event_type = ?",
                    (chat_id, etype),
                ).fetchone()
                stats[etype] = row["count"]
            return stats
        finally:
            conn.close()

    def get_events_by_type(self, chat_id: int, event_type: str, limit: Optional[int] = None) -> list[dict]:
        """دریافت رویدادها بر اساس نوع"""
        limit = limit or Config.REPORT_PAGE_SIZE
        conn = self._get_connection()
        try:
            rows = conn.execute(
                "SELECT e.*, u.first_name, u.last_name, u.username, u.full_name "
                "FROM events e LEFT JOIN users u ON e.user_id = u.user_id "
                "WHERE e.chat_id = ? AND e.event_type = ? "
                "ORDER BY e.created_at DESC LIMIT ?",
                (chat_id, event_type, limit),
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #  ابزارهای کمکی
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def search_user_events(self, chat_id: int, user_id: int) -> list[dict]:
        """جستجوی تمام رویدادهای یک کاربر در یک گروه"""
        conn = self._get_connection()
        try:
            rows = conn.execute(
                "SELECT e.*, u.first_name, u.last_name, u.username, u.full_name "
                "FROM events e LEFT JOIN users u ON e.user_id = u.user_id "
                "WHERE e.chat_id = ? AND e.user_id = ? "
                "ORDER BY e.created_at DESC",
                (chat_id, user_id),
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def clear_old_events(self, days: int = 90) -> int:
        """حذف رویدادهای قدیمی‌تر از N روز"""
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                "DELETE FROM events WHERE created_at < datetime('now', ? || ' days')",
                (f"-{days}",),
            )
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()
