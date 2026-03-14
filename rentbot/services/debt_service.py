"""
Business logic for debt management in rentbot application.
"""
import asyncpg
from datetime import date
from decimal import Decimal
from typing import Dict, List, Optional

from ..config import (
    DEFAULT_MONTHLY_RENT,
    EVENT_RENT_CHARGE,
    EVENT_UTILITY_CHARGE,
    EVENT_TENANT_PAYMENT,
)
from ..utils import month_start, next_month


async def get_raw_balance_info(conn: asyncpg.Connection, user_id: int) -> Dict[str, Decimal]:
    """Get raw balance information for a user."""
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
    period_start: Optional[date] = None,
    description: Optional[str] = None,
    created_at=None,
):
    """Record a history entry for debt tracking."""
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


async def ensure_user_setup(pool: asyncpg.Pool, user_id: int):
    """Ensure user is set up in the rent_settings table."""
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


async def sync_monthly_rent_charges_for_user(pool: asyncpg.Pool, user_id: int, today: Optional[date] = None):
    """Sync monthly rent charges for a user up to today."""
    today = today or date.today()
    current_period = month_start(today)

    await ensure_user_setup(pool, user_id)

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


async def sync_monthly_rent_charges_for_all(pool: asyncpg.Pool):
    """Sync monthly rent charges for all users."""
    async with pool.acquire() as conn:
        user_ids = await conn.fetch("SELECT user_id FROM rent_settings")

    for row in user_ids:
        await sync_monthly_rent_charges_for_user(pool, row["user_id"])


async def get_balance_info(pool: asyncpg.Pool, user_id: int) -> Dict[str, Decimal]:
    """Get balance information for a user with sync."""
    await ensure_user_setup(pool, user_id)
    await sync_monthly_rent_charges_for_user(pool, user_id)

    async with pool.acquire() as conn:
        return await get_raw_balance_info(conn, user_id)


async def get_history(pool: asyncpg.Pool, user_id: int, limit: int = 15) -> List:
    """Get debt history for a user."""
    await ensure_user_setup(pool, user_id)
    await sync_monthly_rent_charges_for_user(pool, user_id)

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