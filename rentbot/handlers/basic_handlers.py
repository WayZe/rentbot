"""
Basic handlers for rentbot application.
Handles start, balance, and history commands.
"""
import asyncpg
from typing import Optional, List
from aiogram import Router, F, types
from aiogram.filters import Command

from ..config import BUTTON_BALANCE, BUTTON_HISTORY
from ..keyboards import main_keyboard
from ..services.debt_service import get_balance_info, get_history, ensure_user_setup, sync_monthly_rent_charges_for_user
from ..utils import format_amount, format_history_line

router = Router()


def get_user_id_safe(message: types.Message) -> int:
    """Get user ID safely from message."""
    if not message.from_user:
        raise ValueError("Message has no user")
    return message.from_user.id


@router.message(Command("start"))
async def start_command(message: types.Message, pool: asyncpg.Pool) -> None:
    """Handle /start command."""
    user_id = get_user_id_safe(message)
    await ensure_user_setup(pool, user_id)
    await sync_monthly_rent_charges_for_user(pool, user_id)
    await message.answer(
        "Я не выбиваю двери, я просто считаю долг.",
        reply_markup=main_keyboard(user_id),
    )


@router.message(F.text == BUTTON_BALANCE)
async def balance_button_handler(message: types.Message, pool: asyncpg.Pool) -> None:
    """Handle balance button press."""
    user_id = get_user_id_safe(message)
    info = await get_balance_info(pool, user_id)
    text = f"Текущий долг: {format_amount(info['balance'])}"
    await message.answer(text, reply_markup=main_keyboard(user_id))


@router.message(F.text == BUTTON_HISTORY)
async def history_button_handler(message: types.Message, pool: asyncpg.Pool) -> None:
    """Handle history button press."""
    user_id = get_user_id_safe(message)
    rows = await get_history(pool, user_id)

    if not rows:
        await message.answer("История пуста.", reply_markup=main_keyboard(user_id))
        return

    lines = [format_history_line(row) for row in rows]
    text = "📜 История\n\n" + "\n".join(lines)
    await message.answer(text, reply_markup=main_keyboard(user_id))


@router.message(Command("history"))
async def history_command(message: types.Message, pool: asyncpg.Pool) -> None:
    """Handle /history command."""
    user_id = get_user_id_safe(message)
    rows = await get_history(pool, user_id)

    if not rows:
        await message.answer("История пуста.", reply_markup=main_keyboard(user_id))
        return

    lines = [format_history_line(row) for row in rows]
    text = "📜 История\n\n" + "\n".join(lines)
    await message.answer(text, reply_markup=main_keyboard(user_id))