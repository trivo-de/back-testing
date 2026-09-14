from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from ..config import BACKTEST
from ..domain.portfolio import decimal
from ..domain.strategies import get_strategy

@dataclass(frozen=True)
class RunConfig:
    """Immutable configuration required to execute and reproduce one run."""

    dataset_id: str
    dataset_version: str
    symbol: str
    start_date: date
    end_date: date
    strategy_id: str
    initial_cash: Decimal
    fee_rate: Decimal
    slippage_rate: Decimal

    def __post_init__(self) -> None:
        """Reject unsupported scope and invalid numeric or date ranges."""

        if not self.dataset_id.strip() or not self.dataset_version.strip():
            raise ValueError("dataset_id and dataset_version are required")
        if self.symbol != BACKTEST.supported_symbol:
            raise ValueError(f"only {BACKTEST.supported_symbol} is supported")
        get_strategy(self.strategy_id)
        if self.start_date > self.end_date:
            raise ValueError("start_date must be <= end_date")
        if decimal(self.initial_cash) <= 0 or decimal(self.fee_rate) < 0 or not 0 <= decimal(self.slippage_rate) < 1:
            raise ValueError("invalid cash, fee_rate, or slippage_rate")
