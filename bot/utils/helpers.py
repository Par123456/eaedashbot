from telegram import Chat, ChatMember, ChatMemberUpdated, Update
from telegram.ext import ContextTypes


async def is_admin(update: Update,
                   context: ContextTypes.DEFAULT_TYPE,
                   user_id: int) -> bool:
    """چک می‌کنه آیا کاربر ادمین گروهه"""
    try:
        member = await context.bot.get_chat_member(
            update.effective_chat.id, user_id
        )
        return member.status in (
            ChatMember.ADMINISTRATOR,
            ChatMember.OWNER
        )
    except Exception:
        return False


def extract_status_change(
    chat_member_update: ChatMemberUpdated,
) -> tuple[bool, bool] | None:
    """
    تشخیص تغییر وضعیت عضو
    برمی‌گردونه: (was_member, is_member)
    """
    old_status = chat_member_update.old_chat_member.status
    new_status = chat_member_update.new_chat_member.status

    MEMBER_STATUSES = {
        ChatMember.MEMBER,
        ChatMember.OWNER,
        ChatMember.ADMINISTRATOR,
        ChatMember.RESTRICTED,
    }

    was_member = old_status in MEMBER_STATUSES
    is_member  = new_status in MEMBER_STATUSES

    if was_member == is_member:
        return None  # تغییری نبوده

    return was_member, is_member
