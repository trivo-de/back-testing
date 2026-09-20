from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

BarTime = date | datetime


def trading_day(value: BarTime) -> date:
    """Keep intraday filtering on the local Open date."""
    return value.date() if isinstance(value, datetime) else value

@dataclass(frozen=True)
class Bar:
    """Minimal Open/Close bar required by the execution engine."""
    trading_date: BarTime
    open: Decimal
    close: Decimal
    close_time: BarTime | None = None

    @property
    def closed_at(self) -> BarTime:
        return self.close_time if self.close_time is not None else self.trading_date


@dataclass(frozen=True)
class StrategyBar:
    trading_date: BarTime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    index_close: Decimal | None = None
    close_time: BarTime | None = None

    @property
    def closed_at(self) -> BarTime:
        return self.close_time if self.close_time is not None else self.trading_date


@dataclass(frozen=True)
class DatasetSnapshot:
    metadata: dict[str, Any]
    bars: tuple[StrategyBar, ...]
    market_bars: tuple[Bar, ...] = ()
