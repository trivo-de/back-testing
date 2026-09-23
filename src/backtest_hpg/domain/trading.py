"""Immutable signal, order, fill, and trade event models."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal
from .market import BarTime

Side = Literal["BUY", "SELL"]
StrategyDetails = tuple[tuple[str, Decimal], ...]


def validate_details(details: StrategyDetails) -> None:
    """Internal v1 audit schema: immutable unique names and finite Decimals."""
    if not isinstance(details, tuple):
        raise ValueError("strategy details must be an immutable tuple")
    names = set()
    for item in details:
        if not isinstance(item, tuple) or len(item) != 2:
            raise ValueError("strategy details must contain name/value pairs")
        name, value = item
        if not isinstance(name, str) or not name or name in names:
            raise ValueError("strategy detail names must be non-empty and unique")
        if not isinstance(value, Decimal) or not value.is_finite():
            raise ValueError("strategy detail values must be finite Decimals")
        names.add(name)

# Trading events
@dataclass(frozen=True)
class FixedSignal:
    """Deterministic test signal or strategy intent awaiting execution."""

    side: Side
    quantity: int | None = None
    reason: str = "FIXED_TEST_SIGNAL"
    details: StrategyDetails = ()

    def __post_init__(self) -> None:
        validate_details(self.details)

@dataclass(frozen=True)
class SignalRecord:
    """Auditable signal created after a completed daily Close."""

    signal_date: BarTime
    side: Side
    reason: str
    details: StrategyDetails = ()

@dataclass(frozen=True)
class Fill:
    """Executed order event priced at a later session Open."""

    signal_date: BarTime
    fill_date: BarTime
    side: Side
    price: Decimal
    quantity: int
    fee: Decimal

@dataclass(frozen=True)
class OrderResult:
    """Execution outcome for one signal, including rejected or pending states."""

    signal_date: BarTime
    side: Side
    status: Literal["FILLED", "REJECTED", "PENDING"]
    reason: str | None = None

@dataclass(frozen=True)
class Trade:
    """Closed round trip with entry, exit, fees, and net realized P/L."""

    entry_date: BarTime
    exit_date: BarTime
    quantity: int
    entry_price: Decimal
    exit_price: Decimal
    fees: Decimal
    net_pnl: Decimal
