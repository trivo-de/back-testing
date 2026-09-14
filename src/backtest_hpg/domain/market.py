from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

@dataclass(frozen=True)
class Bar:
    """Minimal Open/Close bar required by the execution engine."""
    trading_date: date
    open: Decimal
    close: Decimal


@dataclass(frozen=True)
class StrategyBar:
    trading_date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    index_close: Decimal


@dataclass(frozen=True)
class DatasetSnapshot:
    metadata: dict[str, Any]
    bars: tuple[StrategyBar, ...]
