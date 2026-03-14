"""
Test utility functions.
"""
import pytest
from decimal import Decimal
from datetime import date


class TestParseAmount:
    """Test parse_amount function."""

    def test_valid_amounts(self, sample_amounts):
        """Test parsing valid amounts."""
        from rentbot.utils import parse_amount

        for input_str, expected in sample_amounts['valid']:
            result = parse_amount(input_str)
            assert result == expected, f"Failed for input: {input_str}"

    def test_invalid_amounts(self, sample_amounts):
        """Test parsing invalid amounts returns None."""
        from rentbot.utils import parse_amount

        for invalid_input in sample_amounts['invalid']:
            result = parse_amount(invalid_input)
            assert result is None, f"Should return None for: {invalid_input}"

    def test_decimal_precision_handling(self):
        """Test that values with more than 2 decimal places are handled correctly."""
        from rentbot.utils import parse_amount

        # Values with extra decimal places should be quantized to 2 places
        result = parse_amount("1000.123")
        assert result == Decimal("1000.12"), "Should quantize to 2 decimal places"

        result = parse_amount("1000.999")
        assert result == Decimal("1001.00"), "Should round to nearest cent"

    def test_negative_amounts(self):
        """Test negative amounts return None."""
        from rentbot.utils import parse_amount

        negative_amounts = ["-100", "-0.01", "-1500.50"]
        for amount in negative_amounts:
            result = parse_amount(amount)
            assert result is None

    def test_zero_handling(self):
        """Test zero amount handling with allow_zero parameter."""
        from rentbot.utils import parse_amount

        # Without allow_zero (default False)
        assert parse_amount("0") is None
        assert parse_amount("0.00") is None

        # With allow_zero=True
        assert parse_amount("0", allow_zero=True) == Decimal("0.00")
        assert parse_amount("0.00", allow_zero=True) == Decimal("0.00")

    def test_decimal_precision(self):
        """Test decimal precision is maintained."""
        from rentbot.utils import parse_amount

        result = parse_amount("1500.50")
        assert result == Decimal("1500.50")
        assert str(result) == "1500.50"

    def test_comma_replacement(self):
        """Test comma to dot replacement."""
        from rentbot.utils import parse_amount

        assert parse_amount("1500,50") == Decimal("1500.50")  # Comma as decimal separator
        assert parse_amount("1500.50") == Decimal("1500.50")  # Standard dot separator

    def test_whitespace_handling(self):
        """Test whitespace trimming."""
        from rentbot.utils import parse_amount

        assert parse_amount("  1500.50  ") == Decimal("1500.50")
        assert parse_amount("\t1500\n") == Decimal("1500.00")


class TestFormatAmount:
    """Test format_amount function."""

    def test_valid_decimal_formatting(self):
        """Test formatting valid Decimal objects."""
        from rentbot.utils import format_amount

        test_cases = [
            (Decimal("1500.50"), "1500.50"),
            (Decimal("0.00"), "0.00"),
            (Decimal("1234567.89"), "1234567.89"),
            (Decimal("10"), "10.00"),
            (Decimal("0.01"), "0.01"),
        ]

        for amount, expected in test_cases:
            result = format_amount(amount)
            assert result == expected

    def test_none_handling(self):
        """Test None input returns default."""
        from rentbot.utils import format_amount

        result = format_amount(None)
        assert result == "0.00"

    def test_precision_rounding(self):
        """Test precision is always 2 decimal places."""
        from rentbot.utils import format_amount

        assert format_amount(Decimal("1500")) == "1500.00"
        assert format_amount(Decimal("1500.5")) == "1500.50"
        assert format_amount(Decimal("1500.123")) == "1500.12"  # Should be rounded


class TestDateFunctions:
    """Test date utility functions."""

    def test_month_start(self):
        """Test month_start function."""
        from rentbot.utils import month_start

        test_cases = [
            (date(2024, 3, 15), date(2024, 3, 1)),
            (date(2024, 12, 31), date(2024, 12, 1)),
            (date(2024, 1, 1), date(2024, 1, 1)),
            (date(2025, 2, 28), date(2025, 2, 1)),
        ]

        for input_date, expected in test_cases:
            result = month_start(input_date)
            assert result == expected

    def test_next_month(self):
        """Test next_month function."""
        from rentbot.utils import next_month

        test_cases = [
            (date(2024, 3, 1), date(2024, 4, 1)),
            (date(2024, 12, 1), date(2025, 1, 1)),
            (date(2024, 1, 15), date(2024, 2, 1)),  # Day doesn't matter
            (date(2024, 11, 30), date(2024, 12, 1)),
        ]

        for input_date, expected in test_cases:
            result = next_month(input_date)
            assert result == expected

    def test_december_to_january_transition(self):
        """Test year transition from December to January."""
        from rentbot.utils import next_month

        december_date = date(2023, 12, 15)
        result = next_month(december_date)
        assert result == date(2024, 1, 1)
        assert result.year == 2024


class TestFormatHistoryLine:
    """Test format_history_line function."""

    def test_rent_charge_formatting(self, mock_debt_history_row):
        """Test rent charge history formatting."""
        from rentbot.utils import format_history_line

        row = mock_debt_history_row.copy()
        row['event_type'] = 'rent_charge'
        row['amount_delta'] = Decimal('47700.00')

        result = format_history_line(row)

        assert "01.01.2024" in result  # Date
        assert "Аренда" in result      # Title
        assert "+47700.00" in result   # Amount with sign
        assert "01.2024" in result     # Period

    def test_utility_charge_formatting(self, mock_debt_history_row):
        """Test utility charge history formatting."""
        from rentbot.utils import format_history_line

        row = mock_debt_history_row.copy()
        row['event_type'] = 'utility_charge'
        row['amount_delta'] = Decimal('3200.00')
        row['description'] = 'Начисление ЖКХ'
        row['period_start'] = None

        result = format_history_line(row)

        assert "01.01.2024" in result     # Date
        assert "ЖКХ" in result           # Title
        assert "+3200.00" in result      # Amount
        assert "Начисление ЖКХ" in result # Description

    def test_tenant_payment_formatting(self, mock_debt_history_row):
        """Test tenant payment history formatting."""
        from rentbot.utils import format_history_line

        row = mock_debt_history_row.copy()
        row['event_type'] = 'tenant_payment'
        row['amount_delta'] = Decimal('-15000.00')
        row['description'] = 'Платёж жильца'
        row['period_start'] = None

        result = format_history_line(row)

        assert "01.01.2024" in result       # Date
        assert "Платёж" in result          # Title
        assert "-15000.00" in result       # Amount with negative sign
        assert "Платёж жильца" in result   # Description

    def test_no_description_formatting(self, mock_debt_history_row):
        """Test formatting when description is None or empty."""
        from rentbot.utils import format_history_line

        row = mock_debt_history_row.copy()
        row['event_type'] = 'utility_charge'
        row['description'] = None
        row['period_start'] = None

        result = format_history_line(row)

        # Should not have pipe after amount when no description
        parts = result.split("|")
        assert len(parts) == 2  # Date | Title +Amount

    def test_amount_sign_handling(self):
        """Test positive and negative amount sign handling."""
        from rentbot.utils import format_history_line
        from datetime import datetime

        base_row = {
            'event_type': 'utility_charge',
            'description': 'Test',
            'created_at': datetime(2024, 1, 1),
            'period_start': None
        }

        # Positive amount
        row_positive = base_row.copy()
        row_positive['amount_delta'] = Decimal('1000.00')
        result_positive = format_history_line(row_positive)
        assert "+1000.00" in result_positive

        # Negative amount
        row_negative = base_row.copy()
        row_negative['amount_delta'] = Decimal('-1000.00')
        result_negative = format_history_line(row_negative)
        assert "-1000.00" in result_negative