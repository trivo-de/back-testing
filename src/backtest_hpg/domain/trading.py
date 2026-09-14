"""Immutable signal, order, fill, and trade event models."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Literal

Side = Literal["BUY", "SELL"]

# Trading events
@dataclass(frozen=True)
class FixedSignal:
    """Deterministic test signal or strategy intent awaiting execution."""

    side: Side
    quantity: int | None = None
    pivot: Decimal | None = None
    reason: str = "FIXED_TEST_SIGNAL"

@dataclass(frozen=True)
class SignalRecord:
    """Auditable signal created after a completed daily Close."""

    signal_date: date
    side: Side
    reason: str
    pivot: Decimal | None

@dataclass(frozen=True)
class Fill:
    """Executed order event priced at a later session Open."""

    signal_date: date
    fill_date: date
    side: Side
    price: Decimal
    quantity: int
    fee: Decimal

@dataclass(frozen=True)
class OrderResult:
    """Execution outcome for one signal, including rejected or pending states."""

    signal_date: date
    side: Side
    status: Literal["FILLED", "REJECTED", "PENDING"]
    reason: str | None = None

@dataclass(frozen=True)
class Trade:
    """Closed round trip with entry, exit, fees, and net realized P/L."""

    entry_date: date
    exit_date: date
    quantity: int
    entry_price: Decimal
    exit_price: Decimal
    fees: Decimal
    net_pnl: Decimal
