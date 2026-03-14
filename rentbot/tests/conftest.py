"""
Pytest configuration and fixtures for rentbot tests.
"""
import os
import sys
from pathlib import Path
import pytest
from decimal import Decimal

# Add the project root to the path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture(autouse=True)
def setup_test_env():
    """Setup test environment variables before each test."""
    original_env = os.environ.copy()

    # Set test environment variables
    test_env = {
        'BOT_TOKEN': 'test_token_for_testing',
        'ADMIN_USER_IDS': '123456789,987654321',
        'DB_HOST': 'localhost',
        'DB_PORT': '5432',
        'DB_NAME': 'test_db',
        'DB_USER': 'test_user',
        'DB_PASSWORD': 'test_password',
    }

    os.environ.update(test_env)

    yield

    # Restore original environment
    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture
def sample_amounts():
    """Sample amounts for testing."""
    return {
        'valid': [
            ("1500", Decimal("1500.00")),
            ("1500.50", Decimal("1500.50")),
            ("1500,50", Decimal("1500.50")),  # Use comma as decimal separator, not thousands separator
            ("0.01", Decimal("0.01")),
        ],
        'invalid': [
            "",
            "abc",
            "-100",
            "0",  # Zero is invalid by default
            "0.00",  # Zero is invalid by default
            "not_a_number",
            "1,500.50",  # This should be invalid because comma can't be thousands separator with decimal point
        ]
    }


@pytest.fixture
def sample_user_ids():
    """Sample user IDs for testing."""
    return {
        'admin': 123456789,
        'regular': 999999999,
        'another_admin': 987654321,
    }


@pytest.fixture
def mock_debt_history_row():
    """Mock debt history row for testing."""
    from datetime import datetime, date

    return {
        'event_type': 'rent_charge',
        'amount_delta': Decimal('47700.00'),
        'period_start': date(2024, 1, 1),
        'description': 'Начисление аренды за 2024-01',
        'created_at': datetime(2024, 1, 1, 0, 0, 0),
    }