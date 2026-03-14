"""
Test configuration module.
"""
import pytest
from decimal import Decimal


class TestConfig:
    """Test configuration values and parsing."""

    def test_bot_token_configured(self):
        """Test that BOT_TOKEN is properly configured."""
        from rentbot.config import BOT_TOKEN

        assert BOT_TOKEN == 'test_token_for_testing'
        assert isinstance(BOT_TOKEN, str)
        assert len(BOT_TOKEN) > 0

    def test_admin_user_ids_parsing(self):
        """Test admin user IDs parsing from environment."""
        from rentbot.config import ADMIN_USER_IDS

        assert isinstance(ADMIN_USER_IDS, set)
        assert 123456789 in ADMIN_USER_IDS
        assert 987654321 in ADMIN_USER_IDS
        assert len(ADMIN_USER_IDS) == 2

        # Test all values are integers
        for user_id in ADMIN_USER_IDS:
            assert isinstance(user_id, int)
            assert user_id > 0

    def test_db_config_structure(self):
        """Test database configuration structure."""
        from rentbot.config import DB_CONFIG

        required_keys = {'user', 'password', 'database', 'host', 'port'}
        assert isinstance(DB_CONFIG, dict)
        assert all(key in DB_CONFIG for key in required_keys)

        # Test specific values from test environment
        assert DB_CONFIG['host'] == 'localhost'
        assert DB_CONFIG['port'] == 5432
        assert DB_CONFIG['database'] == 'test_db'
        assert DB_CONFIG['user'] == 'test_user'
        assert DB_CONFIG['password'] == 'test_password'

        # Test types
        assert isinstance(DB_CONFIG['port'], int)
        assert isinstance(DB_CONFIG['host'], str)

    def test_default_monthly_rent(self):
        """Test default monthly rent value."""
        from rentbot.config import DEFAULT_MONTHLY_RENT

        assert isinstance(DEFAULT_MONTHLY_RENT, Decimal)
        assert DEFAULT_MONTHLY_RENT == Decimal("47700.00")
        assert DEFAULT_MONTHLY_RENT > 0

    def test_event_types(self):
        """Test event type constants."""
        from rentbot.config import (
            EVENT_RENT_CHARGE,
            EVENT_UTILITY_CHARGE,
            EVENT_TENANT_PAYMENT
        )

        assert EVENT_RENT_CHARGE == "rent_charge"
        assert EVENT_UTILITY_CHARGE == "utility_charge"
        assert EVENT_TENANT_PAYMENT == "tenant_payment"

        # Test all are strings
        assert isinstance(EVENT_RENT_CHARGE, str)
        assert isinstance(EVENT_UTILITY_CHARGE, str)
        assert isinstance(EVENT_TENANT_PAYMENT, str)

    def test_button_texts(self):
        """Test button text constants."""
        from rentbot.config import (
            BUTTON_BALANCE,
            BUTTON_TENANT_PAYMENT,
            BUTTON_UTILITY_CHARGE,
            BUTTON_HISTORY,
            BUTTON_DB_RESTORE
        )

        buttons = [
            BUTTON_BALANCE,
            BUTTON_TENANT_PAYMENT,
            BUTTON_UTILITY_CHARGE,
            BUTTON_HISTORY,
            BUTTON_DB_RESTORE
        ]

        # Test all buttons are non-empty strings
        for button in buttons:
            assert isinstance(button, str)
            assert len(button) > 0
            assert button.strip() == button  # No leading/trailing whitespace

        # Test specific content
        assert "долг" in BUTTON_BALANCE.lower()
        assert "платёж" in BUTTON_TENANT_PAYMENT.lower()
        assert "жкх" in BUTTON_UTILITY_CHARGE.lower()
        assert "истори" in BUTTON_HISTORY.lower()  # "историю" contains "истори"
        assert "бд" in BUTTON_DB_RESTORE.lower()


class TestConfigEdgeCases:
    """Test configuration edge cases and error handling."""

    def test_empty_admin_ids_handling(self, monkeypatch):
        """Test handling of empty admin user IDs."""
        import os
        from importlib import reload
        from rentbot import config

        # Test empty string
        monkeypatch.setenv('ADMIN_USER_IDS', '')
        reload(config)
        assert config.ADMIN_USER_IDS == set()

        # Test missing variable
        monkeypatch.delenv('ADMIN_USER_IDS', raising=False)
        reload(config)
        assert config.ADMIN_USER_IDS == set()

    def test_malformed_admin_ids_handling(self, monkeypatch):
        """Test handling of malformed admin user IDs."""
        from importlib import reload
        from rentbot import config

        # Test with invalid characters - this should raise ValueError
        monkeypatch.setenv('ADMIN_USER_IDS', 'abc,def')

        with pytest.raises(ValueError):
            reload(config)

    def test_single_admin_id(self, monkeypatch):
        """Test single admin ID configuration."""
        from importlib import reload
        from rentbot import config

        monkeypatch.setenv('ADMIN_USER_IDS', '123456789')
        reload(config)
        assert config.ADMIN_USER_IDS == {123456789}

    def test_db_port_conversion(self):
        """Test DB port is properly converted to integer."""
        from rentbot.config import DB_CONFIG

        assert isinstance(DB_CONFIG['port'], int)
        assert DB_CONFIG['port'] == 5432