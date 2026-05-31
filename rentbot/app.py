"""
Main entry point for rentbot application.
"""
import asyncio
import logging
import sys
from typing import Optional, Any, Dict

try:
    from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    SCHEDULER_AVAILABLE = True
except ImportError:
    logger = logging.getLogger(__name__)
    logger.warning("APScheduler not available. Scheduled jobs will be disabled.")
    SCHEDULER_AVAILABLE = False

from aiogram import Bot, Dispatcher
import asyncpg

from .config import BOT_TOKEN, ADMIN_USER_IDS
from .database import create_pool, init_db
from .handlers import basic_handlers, payment_handlers, admin_handlers
from .services.debt_service import sync_monthly_rent_charges_for_all

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger(__name__)
logging.getLogger("apscheduler").setLevel(logging.INFO)

# Global database pool
pool: Optional[asyncpg.Pool] = None


def job_listener(event: Any) -> None:
    """Listen to scheduler job events."""
    if event.exception:
        logger.exception("Job crashed")
    else:
        logger.info("Job executed successfully")


async def sync_monthly_rent_job() -> None:
    """Job to sync monthly rent charges for all users."""
    if pool is None:
        logger.error("Database pool is not initialized")
        return

    logger.info("Starting rent synchronization for all users")
    await sync_monthly_rent_charges_for_all(pool)


async def main() -> None:
    """Main function to start the bot."""
    global pool

    # Check required configuration
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN is not set in environment variables")
        sys.exit(1)

    # Log startup info
    logger.info("Прочитали TOKEN: %s", BOT_TOKEN)
    logger.info("Admin users configured: %s", len(ADMIN_USER_IDS))

    # Create bot and dispatcher
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    # Create database connection pool
    pool = await create_pool()
    await init_db(pool)

    def set_pool(new_pool: asyncpg.Pool) -> None:
        """Replace the application database pool after maintenance operations."""
        global pool
        pool = new_pool

    # Inject dependencies into handlers
    async def inject_pool_middleware(handler: Any, event: Any, data: Dict[str, Any]) -> Any:
        """Middleware to inject database pool into handlers."""
        data['pool'] = pool
        data['set_pool'] = set_pool
        data['bot'] = bot
        return await handler(event, data)

    # Register middleware
    dp.message.middleware(inject_pool_middleware)

    # Include routers
    dp.include_router(basic_handlers.router)
    dp.include_router(payment_handlers.router)
    dp.include_router(admin_handlers.router)

    # Set up scheduler for rent synchronization (if available)
    scheduler = None
    if SCHEDULER_AVAILABLE:
        scheduler = AsyncIOScheduler()
        scheduler.add_job(sync_monthly_rent_job, "cron", hour=0, minute=5)
        scheduler.add_listener(job_listener, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)
        scheduler.start()
        logger.info("Scheduler started for monthly rent synchronization")
    else:
        logger.warning("Scheduler disabled due to missing APScheduler")

    try:
        # Start polling
        await dp.start_polling(bot)
    finally:
        # Clean up
        if pool:
            await pool.close()
        if scheduler:
            scheduler.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
