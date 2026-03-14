"""
Utility functions for rentbot application.
"""
from decimal import Decimal, InvalidOperation
from datetime import date
from .config import EVENT_RENT_CHARGE, EVENT_UTILITY_CHARGE, EVENT_TENANT_PAYMENT


def parse_amount(raw_value: str, *, allow_zero: bool = False) -> Decimal | None:
    """Parse amount from string input."""
    normalized = raw_value.strip().replace(",", ".")
    try:
        amount = Decimal(normalized).quantize(Decimal("0.01"))
    except InvalidOperation:
        return None

    if amount < 0 or (amount == 0 and not allow_zero):
        return None

    return amount


def format_amount(amount: Decimal | None) -> str:
    """Format amount for display."""
    if amount is None:
        return "0.00"
    return f"{amount:.2f}"


def month_start(day: date) -> date:
    """Get the first day of the month."""
    return date(day.year, day.month, 1)


def next_month(day: date) -> date:
    """Get the first day of the next month."""
    if day.month == 12:
        return date(day.year + 1, 1, 1)
    return date(day.year, day.month + 1, 1)


def format_history_line(row) -> str:
    """Format a history line for display."""
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