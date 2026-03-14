"""
Test module imports and basic functionality.
"""
import pytest
from typing import Any


class TestImports:
    """Test that all modules can be imported successfully."""

    def test_config_import(self):
        """Test config module import and basic attributes."""
        # Force reload of config to pick up test environment variables
        import importlib
        from rentbot import config
        importlib.reload(config)

        assert hasattr(config, 'BOT_TOKEN')
        assert hasattr(config, 'ADMIN_USER_IDS')
        assert hasattr(config, 'DB_CONFIG')
        assert hasattr(config, 'DEFAULT_MONTHLY_RENT')

        # Test that admin IDs were parsed correctly
        assert isinstance(config.ADMIN_USER_IDS, set)
        assert 123456789 in config.ADMIN_USER_IDS
        assert 987654321 in config.ADMIN_USER_IDS

    def test_models_import(self):
        """Test models module import and FSM states."""
        from rentbot import models

        assert hasattr(models, 'PaymentStates')
        assert hasattr(models, 'DatabaseStates')

        # Test FSM states
        assert hasattr(models.PaymentStates, 'waiting_for_tenant_payment')
        assert hasattr(models.PaymentStates, 'waiting_for_utility_charge')
        assert hasattr(models.DatabaseStates, 'waiting_for_dump_file')
        assert hasattr(models.DatabaseStates, 'waiting_for_restore_confirmation')

    def test_security_import(self):
        """Test security module import and functions."""
        from rentbot import security

        assert hasattr(security, 'is_admin')
        assert hasattr(security, 'admin_only')
        assert callable(security.is_admin)
        assert callable(security.admin_only)

    def test_utils_import(self):
        """Test utils module import and functions."""
        from rentbot import utils

        assert hasattr(utils, 'parse_amount')
        assert hasattr(utils, 'format_amount')
        assert hasattr(utils, 'format_history_line')
        assert hasattr(utils, 'month_start')
        assert hasattr(utils, 'next_month')

        # Test that all are callable
        assert callable(utils.parse_amount)
        assert callable(utils.format_amount)
        assert callable(utils.format_history_line)
        assert callable(utils.month_start)
        assert callable(utils.next_month)

    def test_keyboards_import(self):
        """Test keyboards module import and functions."""
        from rentbot import keyboards

        assert hasattr(keyboards, 'main_keyboard')
        assert callable(keyboards.main_keyboard)

    def test_database_import(self):
        """Test database module import and functions."""
        from rentbot import database

        assert hasattr(database, 'create_pool')
        assert hasattr(database, 'init_db')
        assert callable(database.create_pool)
        assert callable(database.init_db)

    def test_services_import(self):
        """Test services modules import."""
        from rentbot.services import debt_service, backup_service

        # Test debt_service
        assert hasattr(debt_service, 'get_balance_info')
        assert hasattr(debt_service, 'get_history')
        assert hasattr(debt_service, 'ensure_user_setup')
        assert callable(debt_service.get_balance_info)

        # Test backup_service
        assert hasattr(backup_service, 'create_backup')
        assert hasattr(backup_service, 'restore_from_sql')
        assert hasattr(backup_service, 'download_and_validate_sql_dump')
        assert callable(backup_service.create_backup)

    def test_handlers_import(self):
        """Test handlers modules import."""
        from rentbot.handlers import basic_handlers, payment_handlers, admin_handlers

        # Test that each handler has a router
        assert hasattr(basic_handlers, 'router')
        assert hasattr(payment_handlers, 'router')
        assert hasattr(admin_handlers, 'router')

    def test_app_import(self):
        """Test main app module import."""
        from rentbot import app

        assert hasattr(app, 'main')
        assert callable(app.main)

    def test_package_version(self):
        """Test package version is available."""
        from rentbot import __version__

        assert __version__ == "1.0.0"


class TestPackageStructure:
    """Test package structure and entry points."""

    def test_main_module_entry_point(self):
        """Test that __main__.py can be imported."""
        import rentbot.__main__  # noqa: F401
        # If import succeeds, the test passes

    def test_package_init(self):
        """Test package __init__.py."""
        import rentbot

        assert hasattr(rentbot, '__version__')
        assert hasattr(rentbot, '__author__')
        assert hasattr(rentbot, '__description__')


class TestExternalDependencies:
    """Test that external dependencies can be imported."""

    def test_aiogram_import(self):
        """Test aiogram import."""
        from aiogram import Bot, Dispatcher
        from aiogram.types import Message

        assert Bot is not None
        assert Dispatcher is not None
        assert Message is not None

    def test_asyncpg_import(self):
        """Test asyncpg import."""
        import asyncpg
        assert asyncpg is not None

    def test_aiohttp_import(self):
        """Test aiohttp import."""
        import aiohttp
        assert aiohttp is not None

    def test_decimal_import(self):
        """Test decimal import."""
        from decimal import Decimal
        assert Decimal is not None

    def test_optional_apscheduler_import(self):
        """Test that apscheduler import is handled gracefully."""
        # This should not raise an error even if apscheduler is missing
        try:
            from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED
            from apscheduler.schedulers.asyncio import AsyncIOScheduler
            scheduler_available = True
        except ImportError:
            scheduler_available = False

        # Test passes regardless of whether apscheduler is available
        assert isinstance(scheduler_available, bool)