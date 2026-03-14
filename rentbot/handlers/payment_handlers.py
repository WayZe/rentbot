"""
Payment handlers for rentbot application.
Handles tenant payments and utility charges.
"""
import asyncpg
from typing import Optional
from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from decimal import Decimal

from ..config import (
    BUTTON_TENANT_PAYMENT,
    BUTTON_UTILITY_CHARGE,
    EVENT_TENANT_PAYMENT,
    EVENT_UTILITY_CHARGE
)
from ..keyboards import main_keyboard
from ..models import PaymentStates
from ..services.debt_service import (
    ensure_user_setup,
    sync_monthly_rent_charges_for_user,
    record_history_entry,
    get_balance_info
)
from ..utils import parse_amount, format_amount

router = Router()


def get_user_id_safe(message: types.Message) -> int:
    """Get user ID safely from message."""
    if not message.from_user:
        raise ValueError("Message has no user")
    return message.from_user.id


@router.message(F.text == BUTTON_TENANT_PAYMENT)
async def tenant_payment_button_handler(message: types.Message, state: FSMContext) -> None:
    """Handle tenant payment button press."""
    await message.answer("Введите сумму платежа жильца:")
    await state.set_state(PaymentStates.waiting_for_tenant_payment)


@router.message(F.text == BUTTON_UTILITY_CHARGE)
async def utility_charge_button_handler(message: types.Message, state: FSMContext) -> None:
    """Handle utility charge button press."""
    await message.answer("Введите сумму платежа ЖКХ:")
    await state.set_state(PaymentStates.waiting_for_utility_charge)


@router.message(PaymentStates.waiting_for_tenant_payment)
async def process_tenant_payment(message: types.Message, state: FSMContext, pool: asyncpg.Pool) -> None:
    """Process tenant payment input."""
    if not message.text:
        await message.answer("Введите положительное число, например 1500 или 1500.50")
        return

    amount = parse_amount(message.text)
    if amount is None:
        await message.answer("Введите положительное число, например 1500 или 1500.50")
        return

    user_id = get_user_id_safe(message)
    await ensure_user_setup(pool, user_id)
    await sync_monthly_rent_charges_for_user(pool, user_id)

    async with pool.acquire() as conn:
        await record_history_entry(
            conn,
            user_id,
            event_type=EVENT_TENANT_PAYMENT,
            amount_delta=-amount,
            description="Платёж жильца",
        )

    info = await get_balance_info(pool, user_id)
    await message.answer(
        (
            f"Платёж жильца сохранён: {format_amount(amount)}\n"
            f"Текущий долг: {format_amount(info['balance'])}"
        ),
        reply_markup=main_keyboard(user_id),
    )
    await state.clear()


@router.message(PaymentStates.waiting_for_utility_charge)
async def process_utility_charge(message: types.Message, state: FSMContext, pool: asyncpg.Pool) -> None:
    """Process utility charge input."""
    if not message.text:
        await message.answer("Введите положительное число, например 3200")
        return

    amount = parse_amount(message.text)
    if amount is None:
        await message.answer("Введите положительное число, например 3200")
        return

    user_id = get_user_id_safe(message)
    await ensure_user_setup(pool, user_id)
    await sync_monthly_rent_charges_for_user(pool, user_id)

    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO debt_history(user_id, event_type, amount_delta, period_start, description)
            VALUES($1, $2, $3, NULL, 'Начисление ЖКХ')
            """,
            user_id,
            EVENT_UTILITY_CHARGE,
            amount,
        )

    info = await get_balance_info(pool, user_id)
    await message.answer(
        (
            f"Платёж ЖКХ добавлен в долг жильца: {format_amount(amount)}\n"
            f"Текущий долг: {format_amount(info['balance'])}"
        ),
        reply_markup=main_keyboard(user_id),
    )
    await state.clear()


@router.message(Command("pay"))
async def pay_command(message: types.Message, pool: asyncpg.Pool):
    """Handle /pay command."""
    parts = message.text.split(maxsplit=1)
    if len(parts) != 2:
        await message.answer("Пример: /pay 1500")
        return

    amount = parse_amount(parts[1])
    if amount is None:
        await message.answer("Пример: /pay 1500")
        return

    await ensure_user_setup(pool, message.from_user.id)
    await sync_monthly_rent_charges_for_user(pool, message.from_user.id)

    async with pool.acquire() as conn:
        await record_history_entry(
            conn,
            message.from_user.id,
            event_type=EVENT_TENANT_PAYMENT,
            amount_delta=-amount,
            description="Платёж жильца",
        )

    info = await get_balance_info(pool, message.from_user.id)
    await message.answer(
        (
            f"Платёж жильца сохранён: {format_amount(amount)}\n"
            f"Текущий долг: {format_amount(info['balance'])}"
        ),
        reply_markup=main_keyboard(message.from_user.id),
    )


@router.message(Command("utility"))
async def utility_command(message: types.Message, pool: asyncpg.Pool):
    """Handle /utility command."""
    parts = message.text.split(maxsplit=1)
    if len(parts) != 2:
        await message.answer("Пример: /utility 3200")
        return

    amount = parse_amount(parts[1])
    if amount is None:
        await message.answer("Пример: /utility 3200")
        return

    await ensure_user_setup(pool, message.from_user.id)
    await sync_monthly_rent_charges_for_user(pool, message.from_user.id)

    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO debt_history(user_id, event_type, amount_delta, period_start, description)
            VALUES($1, $2, $3, NULL, 'Начисление ЖКХ')
            """,
            message.from_user.id,
            EVENT_UTILITY_CHARGE,
            amount,
        )

    info = await get_balance_info(pool, message.from_user.id)
    await message.answer(
        (
            f"Платёж ЖКХ добавлен в долг жильца: {format_amount(amount)}\n"
            f"Текущий долг: {format_amount(info['balance'])}"
        ),
        reply_markup=main_keyboard(message.from_user.id),
    )