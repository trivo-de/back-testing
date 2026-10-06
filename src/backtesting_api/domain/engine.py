from __future__ import annotations
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from itertools import chain
from typing import Callable, Mapping, Sequence
from .market import Bar, BarTime, StrategyBar, trading_day
from .portfolio import Portfolio, decimal
from .contract_accounting import ContractPortfolio
from .execution import BuyContext, NormalizedExecution, ContractExecution, InvalidExecution
from .results import BacktestResult, EquityPoint, Summary
from .trading import Fill, FixedSignal, OrderResult, SignalRecord, Trade

@dataclass(frozen=True)
class DecisionContext:
    """Only completed primary/support bars and the current immutable ledger."""

    bars: tuple[Bar | StrategyBar, ...]
    support_bars: tuple[Bar | StrategyBar, ...]
    portfolio: Portfolio | ContractPortfolio


SignalProvider = Callable[[DecisionContext], FixedSignal | None]
BuySizing = Callable[[BuyContext], int]
ExecutionFeedback = Callable[[FixedSignal, OrderResult, Fill | None], None]


def run_engine(
    bars: Sequence[Bar | StrategyBar],
    signal_provider: SignalProvider,
    *,
    initial_cash: Decimal | int | str,
    fee_rate: Decimal | int | str,
    slippage_rate: Decimal | int | str,
    size_buy: BuySizing | None = None,
    on_execution: ExecutionFeedback | None = None,
    support_bars: Sequence[Bar | StrategyBar] = (),
    record_start: date | None = None,
    trade_start: date | None = None,
    flat_dates: frozenset[date] = frozenset(),
    execution: Callable[[Decimal], NormalizedExecution | ContractExecution] | None = None,
    on_open: Callable[[BarTime], None] | None = None,
) -> BacktestResult:
    """Execute pending signals at Open, then evaluate new signals after Close.

    The provider receives completed prefixes, never future primary/support bars.
    Signals created for bar ``t`` remain pending until the next valid Open.
    """

    if not bars or any(current.trading_date >= following.trading_date for current, following in zip(bars, bars[1:])):
        raise ValueError("bars must be non-empty and strictly increasing")
    for bar in chain(bars, support_bars):
        if isinstance(bar.trading_date, datetime):
            if (bar.trading_date.utcoffset() is None or not isinstance(bar.close_time, datetime)
                    or bar.close_time.utcoffset() is None or bar.closed_at <= bar.trading_date):
                raise ValueError("Intraday bars require aware Open and later Close timestamps")
    if any(current.closed_at > following.trading_date for current, following in zip(bars, bars[1:])):
        raise ValueError("Next Open cannot precede the prior Close")

    def available_at(bar):
        return getattr(bar, 'available_at', None) or bar.closed_at

    if any(available_at(bar) < bar.closed_at for bar in chain(bars, support_bars)):
        raise ValueError('BAR_AVAILABLE_BEFORE_CLOSE')
    if any(available_at(bar) != bar.closed_at for bar in bars):
        raise ValueError('PRIMARY_AVAILABILITY_DELAY_UNSUPPORTED')
    if any(available_at(a) >= available_at(b) for a, b in zip(support_bars, support_bars[1:])):
        raise ValueError("Market availability timestamps must be strictly increasing")
    fee, slippage = map(decimal, (fee_rate, slippage_rate))
    if fee < 0 or not Decimal("0") <= slippage < 1:
        raise ValueError("fee_rate must be >= 0; slippage_rate in [0, 1)")

    starting_cash = decimal(initial_cash)
    if execution is not None and (fee != 0 or slippage != 0 or size_buy is not None):
        raise ValueError("Custom execution owns fees, slippage and sizing")
    executor = (execution(starting_cash) if execution is not None else
                NormalizedExecution(starting_cash, fee, slippage, size_buy))
    portfolio = executor.portfolio
    pending: tuple[BarTime, FixedSignal] | None = None
    signal_records: list[SignalRecord] = []
    orders: list[OrderResult] = []
    fills: list[Fill] = []
    trades: list[Trade] = []
    equity: list[EquityPoint] = []
    completed: list[Bar | StrategyBar] = []
    available_support: list[Bar | StrategyBar] = []
    support_index = 0

    for bar in bars:
        # Open: execute only the signal carried from the prior session.
        raw_open = decimal(bar.open)
        if raw_open <= 0:
            raise ValueError("Open must be > 0")
        if on_open is not None:
            on_open(bar.trading_date)
        if trading_day(bar.trading_date) in flat_dates:
            if pending is not None:
                signal_date, signal = pending
                orders.append(OrderResult(signal_date, signal.side, "REJECTED", "SCHEDULED_FLAT_DAY"))
                if on_execution is not None:
                    on_execution(signal, orders[-1], None)
                pending = None
            if portfolio.position is not None:
                signal = executor.close_signal("SCHEDULED_EXIT")
                signal_records.append(SignalRecord(bar.trading_date, signal.side, signal.reason, signal.details))
                pending = (bar.trading_date, signal)
        if pending is not None:
            signal_date, signal = pending
            fill = None
            try:
                fill, trade = executor.execute(signal, signal_date, bar.trading_date, raw_open)
            except InvalidExecution:
                raise
            except ValueError as error:
                orders.append(OrderResult(signal_date, signal.side, "REJECTED", str(error)))
            else:
                portfolio = executor.portfolio
                fills.append(fill)
                orders.append(OrderResult(signal_date, signal.side, "FILLED"))
                if trade is not None:
                    trades.append(trade)
            if on_execution is not None:
                on_execution(signal, orders[-1], fill)
            pending = None

        for signal, fill, trade in executor.intrabar(bar):
            signal_records.append(SignalRecord(fill.signal_date, signal.side, signal.reason, signal.details))
            order = OrderResult(fill.signal_date, signal.side, "FILLED", signal.reason)
            orders.append(order)
            fills.append(fill)
            if trade is not None:
                trades.append(trade)
            if on_execution is not None:
                on_execution(signal, order, fill)
        portfolio = executor.portfolio

        # Close: mark the portfolio before asking for the next signal.
        if record_start is None or trading_day(bar.trading_date) >= record_start:
            equity.append(EquityPoint(bar.closed_at, portfolio.mark(bar.close)))

        # After Close: evaluate using data available through this bar only.
        completed.append(bar)
        while support_index < len(support_bars) and available_at(support_bars[support_index]) <= bar.closed_at:
            available_support.append(support_bars[support_index])
            support_index += 1
        # ponytail: prefix copies cost O(n^2) over a run; use bounded read-only views if history scale requires it.
        signal = signal_provider(DecisionContext(tuple(completed), tuple(available_support), portfolio))
        if trading_day(bar.trading_date) in flat_dates or (trade_start is not None and trading_day(bar.trading_date) < trade_start):
            signal = None
        if signal is not None:
            executor.validate(signal)
            signal_records.append(SignalRecord(bar.closed_at, signal.side, signal.reason, signal.details))
            pending = (bar.closed_at, signal)

    if pending is not None:
        orders.append(OrderResult(pending[0], pending[1].side, "PENDING", "no next bar"))

    if not equity:
        raise ValueError("Report range contains no bars")
    final_snapshot = equity[-1].snapshot
    summary = Summary(
        starting_cash,
        final_snapshot.equity,
        portfolio.realized_pnl,
        final_snapshot.unrealized_pnl,
        (final_snapshot.equity - starting_cash) / starting_cash,
    )
    return BacktestResult(portfolio, tuple(signal_records), tuple(orders), tuple(fills), tuple(trades), tuple(equity), summary)


# Deterministic accounting test support
def run_fixed_signals(
    bars: Sequence[Bar],
    signals: Mapping[BarTime, FixedSignal],
    *,
    initial_cash: Decimal | int | str,
    fee_rate: Decimal | int | str,
    slippage_rate: Decimal | int | str = Decimal("0"),
    size_buy: BuySizing | None = None,
    on_execution: ExecutionFeedback | None = None,
) -> BacktestResult:
    """Run the engine with date-keyed fixed signals for accounting tests."""

    return run_engine(
        bars,
        lambda context: signals.get(context.bars[-1].trading_date),
        initial_cash=initial_cash,
        fee_rate=fee_rate,
        slippage_rate=slippage_rate,
        size_buy=size_buy,
        on_execution=on_execution,
    )
