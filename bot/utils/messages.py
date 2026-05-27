from datetime import datetime
from typing import Optional


def user_link(user_id: int, name: str) -> str:
    """لینک کلیک‌پذیر یوزر"""
    return f'<a href="tg://user?id={user_id}">{name}</a>'


def full_name(first: str, last: Optional[str] = None) -> str:
    return f"{first} {last}".strip() if last else first


def username_text(username: Optional[str]) -> str:
    return f"@{username}" if username else "—"


def format_datetime(dt_str: str) -> str:
    try:
        dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
        return dt.strftime("%Y/%m/%d ساعت %H:%M")
    except Exception:
        return dt_str


# ──────────────────────────────────────────
#  پیام‌های خوش‌آمدگویی
# ──────────────────────────────────────────

WELCOME_MESSAGES = [
    "🎉 {link} عزیز به گروه خوش اومدی!\nخوشحالیم که بهمون پیوستی 🙏",
    "👋 سلام {link}!\nبه جمع ما خوش اومدی 🌟",
    "🥳 {link} جوین شد!\nبه گروه خوش اومدی، امیدواریم اینجا خوش بگذره 😊",
    "✨ عضو جدید! {link} به گروه پیوست\nخوش اومدی دوست عزیز! 🤝",
]

import random

def welcome_text(user_id: int, name: str) -> str:
    template = random.choice(WELCOME_MESSAGES)
    return template.format(link=user_link(user_id, name))


# ──────────────────────────────────────────
#  پیام‌های رویداد
# ──────────────────────────────────────────

def left_text(user_id: int, name: str) -> str:
    return (
        f"👋 {user_link(user_id, name)} گروه رو ترک کرد\n"
        f"🕐 {format_datetime(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))}"
    )


def name_changed_text(user_id: int, old_name: str, new_name: str) -> str:
    return (
        f"✏️ یه عضو اسمشو عوض کرد:\n\n"
        f"👤 کاربر: {user_link(user_id, new_name)}\n"
        f"📝 اسم قدیم: <b>{old_name}</b>\n"
        f"📝 اسم جدید: <b>{new_name}</b>\n"
        f"🕐 {format_datetime(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))}"
    )


def username_changed_text(user_id: int, name: str,
                           old_username: Optional[str],
                           new_username: Optional[str]) -> str:
    return (
        f"🔄 یه عضو یوزرنیمشو عوض کرد:\n\n"
        f"👤 کاربر: {user_link(user_id, name)}\n"
        f"🔗 قدیم: {username_text(old_username)}\n"
        f"🔗 جدید: {username_text(new_username)}\n"
        f"🕐 {format_datetime(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))}"
    )


def photo_changed_text(user_id: int, name: str) -> str:
    return (
        f"🖼 یه عضو عکس پروفایلشو عوض کرد:\n\n"
        f"👤 کاربر: {user_link(user_id, name)}\n"
        f"🕐 {format_datetime(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))}"
    )


# ──────────────────────────────────────────
#  پیام لاگ کامل (/lm)
# ──────────────────────────────────────────

EVENT_ICONS = {
    "join":             "➕",
    "left":             "➖",
    "name_changed":     "✏️",
    "username_changed": "🔄",
    "photo_changed":    "🖼",
}

EVENT_LABELS = {
    "join":             "جوین شد",
    "left":             "لفت داد",
    "name_changed":     "اسم عوض کرد",
    "username_changed": "یوزرنیم عوض کرد",
    "photo_changed":    "عکس پروفایل عوض کرد",
}


def build_log_message(events: list[dict]) -> list[str]:
    """
    چون پیام تلگرام max 4096 کاراکتره،
    اگه لاگ زیاد بود چند پیام برمی‌گردونیم
    """
    if not events:
        return ["📭 هیچ رویدادی ثبت نشده!"]

    # گروه‌بندی بر اساس نوع رویداد
    joins    = [e for e in events if e["event_type"] == "join"]
    lefts    = [e for e in events if e["event_type"] == "left"]
    names    = [e for e in events if e["event_type"] == "name_changed"]
    usernames = [e for e in events if e["event_type"] == "username_changed"]
    photos   = [e for e in events if e["event_type"] == "photo_changed"]

    pages = []

    # ───── صفحه اول: خلاصه ─────
    summary = (
        "📊 <b>گزارش کامل گروه</b>\n"
        f"{'─' * 30}\n"
        f"➕ جوین شده‌ها:       <b>{len(joins)}</b>\n"
        f"➖ لفت داده‌ها:       <b>{len(lefts)}</b>\n"
        f"✏️ تغییر اسم:         <b>{len(names)}</b>\n"
        f"🔄 تغییر یوزرنیم:    <b>{len(usernames)}</b>\n"
        f"🖼 تغییر عکس پروفایل: <b>{len(photos)}</b>\n"
        f"{'─' * 30}\n"
        f"📌 مجموع رویدادها: <b>{len(events)}</b>"
    )
    pages.append(summary)

    # ───── تابع ساخت بخش ─────
    def build_section(title: str, section_events: list[dict]) -> str:
        if not section_events:
            return ""

        lines = [f"\n{title}\n{'─' * 28}"]

        for e in section_events:
            name = full_name(
                e.get("first_name") or "کاربر",
                e.get("last_name")
            )
            link = user_link(e["user_id"], name)
            dt   = format_datetime(e["happened_at"])

            if e["event_type"] == "join":
                lines.append(f"• {link}\n  🕐 {dt}")

            elif e["event_type"] == "left":
                lines.append(f"• {link}\n  🕐 {dt}")

            elif e["event_type"] == "name_changed":
                lines.append(
                    f"• {link}\n"
                    f"  📝 {e.get('old_value','؟')} ← {e.get('new_value','؟')}\n"
                    f"  🕐 {dt}"
                )

            elif e["event_type"] == "username_changed":
                old_u = username_text(e.get("old_value"))
                new_u = username_text(e.get("new_value"))
                lines.append(
                    f"• {link}\n"
                    f"  🔗 {old_u} ← {new_u}\n"
                    f"  🕐 {dt}"
                )

            elif e["event_type"] == "photo_changed":
                lines.append(f"• {link}\n  🕐 {dt}")

        return "\n".join(lines)

    # ساخت بخش‌ها و تقسیم به صفحات
    sections = [
        build_section("➕ <b>جوین شده‌ها</b>",           joins),
        build_section("➖ <b>لفت داده‌ها</b>",           lefts),
        build_section("✏️ <b>تغییر اسم</b>",             names),
        build_section("🔄 <b>تغییر یوزرنیم</b>",         usernames),
        build_section("🖼 <b>تغییر عکس پروفایل</b>",     photos),
    ]

    current_page = ""
    for section in sections:
        if not section:
            continue
        # اگه با این بخش از 4000 کاراکتر گذشت، صفحه جدید
        if len(current_page) + len(section) > 4000:
            if current_page:
                pages.append(current_page)
            current_page = section
        else:
            current_page += section

    if current_page:
        pages.append(current_page)

    return pages
