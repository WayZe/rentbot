"""
Telegram keyboards for rentbot application.
"""
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup
from .config import (
    BUTTON_BALANCE,
    BUTTON_TENANT_PAYMENT,
    BUTTON_UTILITY_CHARGE,
    BUTTON_HISTORY,
    BUTTON_DB_RESTORE,
)
from .security import is_admin


def main_keyboard(user_id: int = None):
    """Create main keyboard with conditional admin buttons."""
    keyboard_buttons = [
        [KeyboardButton(text=BUTTON_BALANCE)],
        [KeyboardButton(text=BUTTON_TENANT_PAYMENT)],
        [KeyboardButton(text=BUTTON_UTILITY_CHARGE)],
        [KeyboardButton(text=BUTTON_HISTORY)],
    ]

    # Add admin-only button for database restore
    if user_id and is_admin(user_id):
        keyboard_buttons.append([KeyboardButton(text=BUTTON_DB_RESTORE)])

    return ReplyKeyboardMarkup(
        keyboard=keyboard_buttons,
        resize_keyboard=True,
        input_field_placeholder="Выберите действие",
    )