"""Aggregated domain models returned by a completed backtest."""

from dataclasses import dataclass
from decimal import Decimal
from .portfolio import Portfolio, PortfolioSnapshot
from .contract_accounting import ContractPortfolio, ContractBook, ContractSnapshot
from .trading import Fill, OrderResult, SignalRecord, StrategyDetails, Trade, validate_details
from .market import BarTime

@dataclass(frozen=True)
class EquityPoint:
    """Portfolio valuation captured at one completed daily Close."""

    trading_date: BarTime
    snapshot: PortfolioSnapshot | ContractSnapshot

@dataclass(frozen=True)
class Summary:
    """Top-level performance values derived from the portfolio ledger."""

    initial_cash: Decimal
    final_equity: Decimal
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    total_return: Decimal

@dataclass(frozen=True)
class BacktestResult:
    """Complete in-memory audit trail and final portfolio state for one run."""

    portfolio: Portfolio | ContractPortfolio | ContractBook
    signals: tuple[SignalRecord, ...]
    orders: tuple[OrderResult, ...]
    fills: tuple[Fill, ...]
    trades: tuple[Trade, ...]
    equity_history: tuple[EquityPoint, ...]
    summary: Summary
    evaluations: tuple[dict, ...] = ()
    position_details: StrategyDetails = ()
    lot_details: tuple[tuple[str, StrategyDetails], ...] = ()

    # Validate position and lot detail values stored with the result.
    def __post_init__(self) -> None:
        validate_details(self.position_details)
        for _, details in self.lot_details:
            validate_details(details)
