"""
Database initialization and configuration for rentbot application.
"""
import asyncpg
import logging
from .config import DB_CONFIG

logger = logging.getLogger(__name__)


async def create_pool() -> asyncpg.Pool:
    """Create and return database connection pool."""
    return await asyncpg.create_pool(**DB_CONFIG)


async def init_db(pool: asyncpg.Pool):
    """Initialize database tables and perform migrations."""
    async with pool.acquire() as conn:
        # Create tables
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

        # Run migrations
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

    # Backfill debt history
    await backfill_debt_history(pool)

    # Clean up old tables
    async with pool.acquire() as conn:
        await conn.execute("DROP TABLE IF EXISTS debts;")
        await conn.execute("DROP TABLE IF EXISTS charges;")
        await conn.execute("DROP TABLE IF EXISTS payments;")


async def backfill_debt_history(pool: asyncpg.Pool):
    """Backfill debt history from legacy tables if they exist."""
    async with pool.acquire() as conn:
        history_exists = await conn.fetchval("SELECT COUNT(*) > 0 FROM debt_history")
        if history_exists:
            return

        # Check for charges table
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
                    event_type = "rent_charge"
                else:
                    description = "Начисление ЖКХ"
                    event_type = "utility_charge"

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

        # Check for payments table
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
                    "tenant_payment",
                    -row["amount"],
                    row["created_at"],
                )