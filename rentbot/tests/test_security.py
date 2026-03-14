"""
Test security functions.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock
from typing import Any


class TestIsAdmin:
    """Test is_admin function."""

    def test_admin_user_recognition(self, sample_user_ids):
        """Test that admin users are properly recognized."""
        import importlib
        from rentbot import security
        importlib.reload(security)

        assert security.is_admin(sample_user_ids['admin']) is True
        assert security.is_admin(sample_user_ids['another_admin']) is True

    def test_regular_user_rejection(self, sample_user_ids):
        """Test that regular users are rejected."""
        from rentbot.security import is_admin

        assert is_admin(sample_user_ids['regular']) is False

    def test_invalid_user_id_types(self):
        """Test handling of invalid user ID types."""
        from rentbot.security import is_admin

        # These should return False without raising exceptions
        assert is_admin(None) is False
        assert is_admin("123456789") is False
        assert is_admin(123.456) is False
        assert is_admin([123456789]) is False

    def test_zero_and_negative_ids(self):
        """Test handling of zero and negative IDs."""
        from rentbot.security import is_admin

        assert is_admin(0) is False
        assert is_admin(-1) is False
        assert is_admin(-123456789) is False

    def test_large_user_ids(self):
        """Test handling of very large user IDs."""
        from rentbot.security import is_admin

        large_id = 999999999999999999
        assert is_admin(large_id) is False


class TestAdminOnlyDecorator:
    """Test admin_only decorator."""

    @pytest.fixture
    def mock_message(self, sample_user_ids):
        """Create mock message objects."""
        def create_mock(user_id):
            message = MagicMock()
            message.from_user = MagicMock()
            message.from_user.id = user_id
            message.answer = AsyncMock()
            return message

        return {
            'admin': create_mock(sample_user_ids['admin']),
            'regular': create_mock(sample_user_ids['regular']),
        }

    @pytest.mark.asyncio
    async def test_admin_access_granted(self, mock_message):
        """Test that admin users can access decorated functions."""
        from rentbot.security import admin_only

        # Create a mock handler
        handler_called = False

        @admin_only
        async def mock_handler(message):
            nonlocal handler_called
            handler_called = True
            return "success"

        result = await mock_handler(mock_message['admin'])

        assert handler_called is True
        assert result == "success"
        mock_message['admin'].answer.assert_not_called()

    @pytest.mark.asyncio
    async def test_regular_user_access_denied(self, mock_message):
        """Test that regular users are denied access."""
        from rentbot.security import admin_only

        handler_called = False

        @admin_only
        async def mock_handler(message):
            nonlocal handler_called
            handler_called = True
            return "success"

        result = await mock_handler(mock_message['regular'])

        assert handler_called is False
        assert result is None
        mock_message['regular'].answer.assert_called_once_with(
            "❌ Доступ запрещен. Только для администраторов."
        )

    @pytest.mark.asyncio
    async def test_decorator_preserves_function_metadata(self):
        """Test that decorator preserves original function metadata."""
        from rentbot.security import admin_only

        @admin_only
        async def test_function(message):
            """Test function docstring."""
            pass

        assert test_function.__name__ == "test_function"
        assert "Test function docstring" in test_function.__doc__

    @pytest.mark.asyncio
    async def test_handler_with_additional_args(self, mock_message):
        """Test decorator works with handlers that have additional arguments."""
        from rentbot.security import admin_only

        @admin_only
        async def mock_handler(message, state=None, pool=None):
            return f"args: {state}, {pool}"

        result = await mock_handler(
            mock_message['admin'],
            state="test_state",
            pool="test_pool"
        )

        assert result == "args: test_state, test_pool"

    @pytest.mark.asyncio
    async def test_handler_exception_propagation(self, mock_message):
        """Test that exceptions in handlers are properly propagated."""
        from rentbot.security import admin_only

        @admin_only
        async def failing_handler(message):
            raise ValueError("Test exception")

        with pytest.raises(ValueError, match="Test exception"):
            await failing_handler(mock_message['admin'])

    @pytest.mark.asyncio
    async def test_message_without_user(self):
        """Test handling of message without from_user."""
        from rentbot.security import admin_only

        message_no_user = MagicMock()
        message_no_user.from_user = None
        message_no_user.answer = AsyncMock()

        @admin_only
        async def mock_handler(message):
            return "success"

        # This should raise an AttributeError when trying to access user_id
        with pytest.raises(AttributeError):
            await mock_handler(message_no_user)


class TestSecurityIntegration:
    """Test security integration scenarios."""

    def test_admin_check_with_keyboard_integration(self, sample_user_ids):
        """Test admin check integration with keyboard module."""
        from rentbot.keyboards import main_keyboard

        # Admin should see extra buttons
        admin_keyboard = main_keyboard(sample_user_ids['admin'])
        admin_keyboard_str = str(admin_keyboard)

        # Regular user should not see admin buttons
        regular_keyboard = main_keyboard(sample_user_ids['regular'])
        regular_keyboard_str = str(regular_keyboard)

        # Admin keyboard should contain DB restore button
        assert "🔄 Восстановить БД" in admin_keyboard_str

        # Regular keyboard should not contain DB restore button
        assert "🔄 Восстановить БД" not in regular_keyboard_str

    def test_admin_check_consistency(self, sample_user_ids):
        """Test that admin check is consistent across calls."""
        from rentbot.security import is_admin

        admin_id = sample_user_ids['admin']
        regular_id = sample_user_ids['regular']

        # Should always return the same result for the same ID
        assert is_admin(admin_id) is True
        assert is_admin(admin_id) is True
        assert is_admin(admin_id) is True

        assert is_admin(regular_id) is False
        assert is_admin(regular_id) is False
        assert is_admin(regular_id) is False

    def test_empty_admin_set_handling(self, monkeypatch):
        """Test behavior when no admins are configured."""
        from importlib import reload
        from rentbot import security, config

        # Set empty admin list
        monkeypatch.setenv('ADMIN_USER_IDS', '')
        reload(config)
        reload(security)

        # No user should be admin when set is empty
        assert security.is_admin(123456789) is False
        assert security.is_admin(987654321) is False