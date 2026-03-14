"""
Security and access control functions for rentbot application.
"""
from functools import wraps
from aiogram import types
from .config import ADMIN_USER_IDS


def is_admin(user_id: int) -> bool:
    """Check if user is an administrator."""
    if not isinstance(user_id, int):
        return False
    return user_id in ADMIN_USER_IDS


def admin_only(handler):
    """Decorator to restrict handler access to admins only."""
    @wraps(handler)
    async def wrapper(message: types.Message, *args, **kwargs):
        if not is_admin(message.from_user.id):
            await message.answer("❌ Доступ запрещен. Только для администраторов.")
            return
        return await handler(message, *args, **kwargs)
    return wrapper