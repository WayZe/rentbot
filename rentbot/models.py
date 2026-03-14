"""
FSM states and data models for rentbot application.
"""
from aiogram.fsm.state import State, StatesGroup


class PaymentStates(StatesGroup):
    """States for payment processing."""
    waiting_for_tenant_payment = State()
    waiting_for_utility_charge = State()


class DatabaseStates(StatesGroup):
    """States for database restore operations."""
    waiting_for_dump_file = State()
    waiting_for_restore_confirmation = State()