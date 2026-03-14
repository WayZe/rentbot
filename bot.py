import asyncio
import logging
import os
from datetime import date
from decimal import Decimal, InvalidOperation

import asyncpg
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger(__name__)
logging.getLogger("apscheduler").setLevel(logging.INFO)

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
DEFAULT_MONTHLY_RENT = Decimal("47700.00")

EVENT_RENT_CHARGE = "rent_charge"
EVENT_UTILITY_CHARGE = "utility_charge"
EVENT_TENANT_PAYMENT = "tenant_payment"

BUTTON_BALANCE = "📊 Текущий долг"
BUTTON_TENANT_PAYMENT = "💰 Внести платёж жильца"
BUTTON_UTILITY_CHARGE = "🧾 Внести ЖКХ"
BUTTON_HISTORY = "📜 Получить историю"

DB_CONFIG = {
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "database": os.getenv("DB_NAME"),
    "host": os.getenv("DB_HOST"),
    "port": int(os.getenv("DB_PORT", 5432)),
}

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
pool = None


class PaymentStates(StatesGroup):
    waiting_for_tenant_payment = State()
    waiting_for_utility_charge = State()


def job_listener(event):
    if event.exception:
        logger.exception("Job crashed")
    else:
        logger.info("Job executed successfully")


def main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BUTTON_BALANCE)],
            [KeyboardButton(text=BUTTON_TENANT_PAYMENT)],
            [KeyboardButton(text=BUTTON_UTILITY_CHARGE)],
            [KeyboardButton(text=BUTTON_HISTORY)],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите действие",
    )


def parse_amount(raw_value: str, *, allow_zero: bool = False) -> Decimal | None:
    normalized = raw_value.strip().replace(",", ".")
    try:
        amount = Decimal(normalized).quantize(Decimal("0.01"))
    except InvalidOperation:
        return None

    if amount < 0 or (amount == 0 and not allow_zero):
        return None

    return amount


def month_start(day: date) -> date:
    return date(day.year, day.month, 1)


def next_month(day: date) -> date:
    if day.month == 12:
        return date(day.year + 1, 1, 1)
    return date(day.year, day.month + 1, 1)


def format_amount(amount: Decimal | None) -> str:
    if amount is None:
        return "0.00"
    return f"{amount:.2f}"


def format_history_line(row) -> str:
    event_type = row["event_type"]
    if event_type == EVENT_RENT_CHARGE:
        title = "Аренда"
    elif event_type == EVENT_UTILITY_CHARGE:
        title = "ЖКХ"
    else:
        title = "Платёж"

    amount = Decimal(row["amount_delta"])
    amount_text = format_amount(abs(amount))
    sign = "+" if amount > 0 else "-"
    created_at = row["created_at"].strftime("%d.%m.%Y")
    description = row["description"] or ""

    if event_type == EVENT_RENT_CHARGE and row["period_start"]:
        period = row["period_start"].strftime("%m.%Y")
        return f"{created_at} | {title} {sign}{amount_text} | {period}"

    if description:
        return f"{created_at} | {title} {sign}{amount_text} | {description}"

    return f"{created_at} | {title} {sign}{amount_text}"


async def init_db():
    async with pool.acquire() as conn:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS rent_settings (
                user_id BIGINT PRIMARY KEY,
                monthly_rent NUMERIC(12,2) NOT NULL,
                last_charged DATE
            );
            """
        )

        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS debt_history (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                event_type TEXT NOT NULL,
                amount_delta NUMERIC(12,2) NOT NULL,
                period_start DATE,
                description TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )

        await conn.execute(
            "ALTER TABLE debt_history DROP COLUMN IF EXISTS balance_after;"
        )
        await conn.execute(
            "ALTER TABLE debt_history DROP COLUMN IF EXISTS source_table;"
        )
        await conn.execute(
            "ALTER TABLE debt_history DROP COLUMN IF EXISTS source_id;"
        )
        await conn.execute(
            "ALTER TABLE debt_history ADD COLUMN IF NOT EXISTS period_start DATE;"
        )
        await conn.execute("DROP INDEX IF EXISTS debt_history_source_uidx;")
        await conn.execute("DROP INDEX IF EXISTS debt_history_rent_period_uidx;")
        await conn.execute(
            """
            CREATE UNIQUE INDEX debt_history_rent_period_uidx
            ON debt_history(user_id, event_type, period_start)
            WHERE event_type = 'rent_charge';
            """
        )

    await backfill_debt_history()
    async with pool.acquire() as conn:
        await conn.execute("DROP TABLE IF EXISTS debts;")
        await conn.execute("DROP TABLE IF EXISTS charges;")
        await conn.execute("DROP TABLE IF EXISTS payments;")


async def get_raw_balance_info(conn: asyncpg.Connection, user_id: int) -> dict[str, Decimal]:
    rent_charges = await conn.fetchval(
        """
        SELECT COALESCE(SUM(amount_delta), 0)
        FROM debt_history
        WHERE user_id = $1 AND event_type = $2
        """,
        user_id,
        EVENT_RENT_CHARGE,
    ) or Decimal("0.00")

    utility_charges = await conn.fetchval(
        """
        SELECT COALESCE(SUM(amount_delta), 0)
        FROM debt_history
        WHERE user_id = $1 AND event_type = $2
        """,
        user_id,
        EVENT_UTILITY_CHARGE,
    ) or Decimal("0.00")

    tenant_payments = await conn.fetchval(
        """
        SELECT COALESCE(SUM(-amount_delta), 0)
        FROM debt_history
        WHERE user_id = $1 AND event_type = $2
        """,
        user_id,
        EVENT_TENANT_PAYMENT,
    ) or Decimal("0.00")

    rent = await conn.fetchval(
        "SELECT monthly_rent FROM rent_settings WHERE user_id = $1",
        user_id,
    ) or DEFAULT_MONTHLY_RENT

    balance = await conn.fetchval(
        """
        SELECT COALESCE(SUM(amount_delta), 0)
        FROM debt_history
        WHERE user_id = $1
        """,
        user_id,
    ) or Decimal("0.00")

    return {
        "balance": balance,
        "rent_charges": rent_charges,
        "utility_charges": utility_charges,
        "tenant_payments": tenant_payments,
        "rent": rent,
    }


async def record_history_entry(
    conn: asyncpg.Connection,
    user_id: int,
    *,
    event_type: str,
    amount_delta: Decimal,
    period_start: date | None = None,
    description: str | None = None,
    created_at=None,
):
    await conn.execute(
        """
        INSERT INTO debt_history(
            user_id,
            event_type,
            amount_delta,
            period_start,
            description,
            created_at
        )
        VALUES($1, $2, $3, $4, $5, COALESCE($6, CURRENT_TIMESTAMP))
        ON CONFLICT (user_id, event_type, period_start)
        WHERE event_type = 'rent_charge'
        DO NOTHING
        """,
        user_id,
        event_type,
        amount_delta,
        period_start,
        description,
        created_at,
    )


async def backfill_debt_history():
    async with pool.acquire() as conn:
        history_exists = await conn.fetchval("SELECT COUNT(*) > 0 FROM debt_history")
        if history_exists:
            return

        has_charges_table = await conn.fetchval(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'charges'
            )
            """
        )

        if has_charges_table:
            charge_rows = await conn.fetch(
                """
                SELECT user_id, amount, charge_type, period_start, created_at
                FROM charges
                ORDER BY created_at, id
                """
            )

            for row in charge_rows:
                if row["charge_type"] == "rent":
                    description = f"Начисление аренды за {row['period_start']:%Y-%m}"
                    event_type = EVENT_RENT_CHARGE
                else:
                    description = "Начисление ЖКХ"
                    event_type = EVENT_UTILITY_CHARGE

                await conn.execute(
                    """
                    INSERT INTO debt_history(
                        user_id,
                        event_type,
                        amount_delta,
                        period_start,
                        description,
                        created_at
                    )
                    VALUES($1, $2, $3, $4, $5, $6)
                    ON CONFLICT (user_id, event_type, period_start)
                    WHERE event_type = 'rent_charge'
                    DO NOTHING
                    """,
                    row["user_id"],
                    event_type,
                    row["amount"],
                    row["period_start"],
                    description,
                    row["created_at"],
                )

        has_payments_table = await conn.fetchval(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'payments'
            )
            """
        )

        if has_payments_table:
            payment_rows = await conn.fetch(
                """
                SELECT user_id, amount, created_at
                FROM payments
                ORDER BY created_at, id
                """
            )

            for row in payment_rows:
                await conn.execute(
                    """
                    INSERT INTO debt_history(
                        user_id,
                        event_type,
                        amount_delta,
                        period_start,
                        description,
                        created_at
                    )
                    VALUES($1, $2, $3, NULL, 'Платёж жильца', $4)
                    """,
                    row["user_id"],
                    EVENT_TENANT_PAYMENT,
                    -row["amount"],
                    row["created_at"],
                )


async def ensure_user_setup(user_id: int):
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO rent_settings(user_id, monthly_rent, last_charged)
            VALUES($1, $2, NULL)
            ON CONFLICT (user_id) DO UPDATE
            SET monthly_rent = EXCLUDED.monthly_rent
            """,
            user_id,
            DEFAULT_MONTHLY_RENT,
        )


async def sync_monthly_rent_charges_for_user(user_id: int, today: date | None = None):
    today = today or date.today()
    current_period = month_start(today)

    await ensure_user_setup(user_id)

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT monthly_rent, last_charged
            FROM rent_settings
            WHERE user_id = $1
            """,
            user_id,
        )

        period = current_period if row["last_charged"] is None else next_month(row["last_charged"])
        monthly_rent = row["monthly_rent"]

        while period <= current_period:
            await record_history_entry(
                conn,
                user_id,
                event_type=EVENT_RENT_CHARGE,
                amount_delta=monthly_rent,
                period_start=period,
                description=f"Начисление аренды за {period:%Y-%m}",
            )

            await conn.execute(
                """
                UPDATE rent_settings
                SET last_charged = $2
                WHERE user_id = $1
                """,
                user_id,
                period,
            )
            period = next_month(period)


async def sync_monthly_rent_charges_for_all():
    logger.info("Starting rent synchronization for all users")
    async with pool.acquire() as conn:
        user_ids = await conn.fetch("SELECT user_id FROM rent_settings")

    for row in user_ids:
        await sync_monthly_rent_charges_for_user(row["user_id"])


async def get_balance_info(user_id: int) -> dict[str, Decimal]:
    await ensure_user_setup(user_id)
    await sync_monthly_rent_charges_for_user(user_id)

    async with pool.acquire() as conn:
        return await get_raw_balance_info(conn, user_id)


async def get_history(user_id: int, limit: int = 15):
    await ensure_user_setup(user_id)
    await sync_monthly_rent_charges_for_user(user_id)

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT event_type, amount_delta, period_start, description, created_at
            FROM debt_history
            WHERE user_id = $1
            ORDER BY created_at DESC, id DESC
            LIMIT $2
            """,
            user_id,
            limit,
        )
    return rows


@dp.message(Command("start"))
async def start(message: types.Message):
    await ensure_user_setup(message.from_user.id)
    await sync_monthly_rent_charges_for_user(message.from_user.id)
    await message.answer(
        "Я не выбиваю двери, я просто считаю долг.",
        reply_markup=main_keyboard(),
    )


@dp.message(F.text == BUTTON_TENANT_PAYMENT)
async def tenant_payment_button(message: types.Message, state: FSMContext):
    await message.answer("Введите сумму платежа жильца:")
    await state.set_state(PaymentStates.waiting_for_tenant_payment)


@dp.message(F.text == BUTTON_UTILITY_CHARGE)
async def utility_charge_button(message: types.Message, state: FSMContext):
    await message.answer("Введите сумму платежа ЖКХ:")
    await state.set_state(PaymentStates.waiting_for_utility_charge)


@dp.message(PaymentStates.waiting_for_tenant_payment)
async def process_tenant_payment(message: types.Message, state: FSMContext):
    amount = parse_amount(message.text)
    if amount is None:
        await message.answer("Введите положительное число, например 1500 или 1500.50")
        return

    await ensure_user_setup(message.from_user.id)
    await sync_monthly_rent_charges_for_user(message.from_user.id)

    async with pool.acquire() as conn:
        await record_history_entry(
            conn,
            message.from_user.id,
            event_type=EVENT_TENANT_PAYMENT,
            amount_delta=-amount,
            description="Платёж жильца",
        )

    info = await get_balance_info(message.from_user.id)
    await message.answer(
        (
            f"Платёж жильца сохранён: {format_amount(amount)}\n"
            f"Текущий долг: {format_amount(info['balance'])}"
        ),
        reply_markup=main_keyboard(),
    )
    await state.clear()


@dp.message(PaymentStates.waiting_for_utility_charge)
async def process_utility_charge(message: types.Message, state: FSMContext):
    amount = parse_amount(message.text)
    if amount is None:
        await message.answer("Введите положительное число, например 3200")
        return

    await ensure_user_setup(message.from_user.id)
    await sync_monthly_rent_charges_for_user(message.from_user.id)

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

    info = await get_balance_info(message.from_user.id)
    await message.answer(
        (
            f"Платёж ЖКХ добавлен в долг жильца: {format_amount(amount)}\n"
            f"Текущий долг: {format_amount(info['balance'])}"
        ),
        reply_markup=main_keyboard(),
    )
    await state.clear()


@dp.message(Command("pay"))
async def pay(message: types.Message):
    parts = message.text.split(maxsplit=1)
    if len(parts) != 2:
        await message.answer("Пример: /pay 1500")
        return

    amount = parse_amount(parts[1])
    if amount is None:
        await message.answer("Пример: /pay 1500")
        return

    await ensure_user_setup(message.from_user.id)
    await sync_monthly_rent_charges_for_user(message.from_user.id)

    async with pool.acquire() as conn:
        await record_history_entry(
            conn,
            message.from_user.id,
            event_type=EVENT_TENANT_PAYMENT,
            amount_delta=-amount,
            description="Платёж жильца",
        )

    info = await get_balance_info(message.from_user.id)
    await message.answer(
        (
            f"Платёж жильца сохранён: {format_amount(amount)}\n"
            f"Текущий долг: {format_amount(info['balance'])}"
        ),
        reply_markup=main_keyboard(),
    )


@dp.message(Command("utility"))
async def utility(message: types.Message):
    parts = message.text.split(maxsplit=1)
    if len(parts) != 2:
        await message.answer("Пример: /utility 3200")
        return

    amount = parse_amount(parts[1])
    if amount is None:
        await message.answer("Пример: /utility 3200")
        return

    await ensure_user_setup(message.from_user.id)
    await sync_monthly_rent_charges_for_user(message.from_user.id)

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

    info = await get_balance_info(message.from_user.id)
    await message.answer(
        (
            f"Платёж ЖКХ добавлен в долг жильца: {format_amount(amount)}\n"
            f"Текущий долг: {format_amount(info['balance'])}"
        ),
        reply_markup=main_keyboard(),
    )


@dp.message(F.text == BUTTON_BALANCE)
async def balance_button(message: types.Message):
    info = await get_balance_info(message.from_user.id)

    text = f"Текущий долг: {format_amount(info['balance'])}"

    await message.answer(text, reply_markup=main_keyboard())


@dp.message(F.text == BUTTON_HISTORY)
async def history_button(message: types.Message):
    rows = await get_history(message.from_user.id)

    if not rows:
        await message.answer("История пуста.", reply_markup=main_keyboard())
        return

    lines = [format_history_line(row) for row in rows]
    text = "📜 История\n\n" + "\n".join(lines)
    await message.answer(text, reply_markup=main_keyboard())


@dp.message(Command("history"))
async def history(message: types.Message):
    rows = await get_history(message.from_user.id)

    if not rows:
        await message.answer("История пуста.", reply_markup=main_keyboard())
        return

    lines = [format_history_line(row) for row in rows]
    text = "📜 История\n\n" + "\n".join(lines)
    await message.answer(text, reply_markup=main_keyboard())


async def main():
    global pool
    pool = await asyncpg.create_pool(**DB_CONFIG)
    await init_db()

    scheduler = AsyncIOScheduler()
    scheduler.add_job(sync_monthly_rent_charges_for_all, "cron", hour=0, minute=5)
    scheduler.add_listener(job_listener, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)
    scheduler.start()

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
