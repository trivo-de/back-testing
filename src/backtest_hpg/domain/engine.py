from __future__ import annotations
from datetime import date, datetime
from decimal import Decimal
from typing import Callable, Mapping, Sequence
from ..config import CANSLIM_BREAKOUT_V0
from .market import Bar, BarTime, trading_day
from .portfolio import Portfolio, decimal
from .results import BacktestResult, EquityPoint, Summary
from .trading import Fill, FixedSignal, OrderResult, SignalRecord, Trade

SignalProvider = Callable[[int, Portfolio, Decimal | None], FixedSignal | None]

# Position sizing
def _position_size(
    portfolio: Portfolio,
    fill_price: Decimal,
    fee_rate: Decimal,
    risk_fraction: Decimal,
    stop_fraction: Decimal,
) -> int:
    """Size a BUY by risk budget while respecting available cash and fees."""

    risk_quantity = int((portfolio.cash * risk_fraction) // (fill_price * stop_fraction))
    affordable_quantity = int(portfolio.cash // (fill_price * (1 + fee_rate)))
    return min(risk_quantity, affordable_quantity)


def run_engine(
    bars: Sequence[Bar],
    signal_provider: SignalProvider,
    *,
    initial_cash: Decimal | int | str,
    fee_rate: Decimal | int | str,
    slippage_rate: Decimal | int | str,
    risk_per_trade: Decimal | int | str,
    stop_fraction: Decimal | int | str,
    record_start: date | None = None,
) -> BacktestResult:
    """Execute pending signals at Open, then evaluate new signals after Close.

    The provider receives only the current index and state. Signals created for
    session ``t`` remain pending until the next bar, preserving causal timing.
    """

    if not bars or any(current.trading_date >= following.trading_date for current, following in zip(bars, bars[1:])):
        raise ValueError("bars must be non-empty and strictly increasing")
    for bar in bars:
        if isinstance(bar.trading_date, datetime):
            if (bar.trading_date.utcoffset() is None or not isinstance(bar.close_time, datetime)
                    or bar.close_time.utcoffset() is None or bar.closed_at <= bar.trading_date):
                raise ValueError("Intraday bars require aware Open and later Close timestamps")
    if any(current.closed_at > following.trading_date for current, following in zip(bars, bars[1:])):
        raise ValueError("Next Open cannot precede the prior Close")

    fee, slippage, risk, stop = map(decimal, (fee_rate, slippage_rate, risk_per_trade, stop_fraction))
    if fee < 0 or not Decimal("0") <= slippage < 1 or not Decimal("0") < risk <= 1 or not Decimal("0") < stop < 1:
        raise ValueError("fee_rate must be >= 0; slippage_rate in [0, 1); risk_per_trade in (0, 1]; stop_fraction in (0, 1)")

    starting_cash = decimal(initial_cash)
    portfolio = Portfolio.open(starting_cash)
    pending: tuple[BarTime, FixedSignal] | None = None
    entry_fill: Fill | None = None
    entry_pivot: Decimal | None = None
    signal_records: list[SignalRecord] = []
    orders: list[OrderResult] = []
    fills: list[Fill] = []
    trades: list[Trade] = []
    equity: list[EquityPoint] = []

    for index, bar in enumerate(bars):
        # Open: execute only the signal carried from the prior session.
        raw_open = decimal(bar.open)
        if pending is not None:
            signal_date, signal = pending
            fill_price = raw_open * (1 + slippage) if signal.side == "BUY" else raw_open * (1 - slippage)
            quantity = signal.quantity
            if signal.side == "BUY" and quantity is None:
                quantity = _position_size(portfolio, fill_price, fee, risk, stop)
            if signal.side == "SELL":
                quantity = portfolio.position.quantity  # type: ignore[union-attr]
            try:
                before_fees, before_realized = portfolio.fees, portfolio.realized_pnl
                portfolio = portfolio.buy(quantity, fill_price, fee, signal.pivot) if signal.side == "BUY" else portfolio.sell(fill_price, fee)
            except ValueError as error:
                orders.append(OrderResult(signal_date, signal.side, "REJECTED", str(error)))
            else:
                fill = Fill(signal_date, bar.trading_date, signal.side, fill_price, quantity, portfolio.fees - before_fees)
                fills.append(fill)
                orders.append(OrderResult(signal_date, signal.side, "FILLED"))
                if signal.side == "BUY":
                    entry_fill, entry_pivot = fill, signal.pivot
                else:
                    assert entry_fill is not None
                    trades.append(Trade(entry_fill.fill_date, bar.trading_date, quantity, entry_fill.price, fill_price, entry_fill.fee + fill.fee, portfolio.realized_pnl - before_realized))
                    entry_fill, entry_pivot = None, None
            pending = None

        # Close: mark the portfolio before asking for the next signal.
        if record_start is None or trading_day(bar.trading_date) >= record_start:
            equity.append(EquityPoint(bar.closed_at, portfolio.mark(bar.close)))

        # After Close: evaluate using data available through this bar only.
        signal = signal_provider(index, portfolio, entry_pivot)
        if signal is not None:
            if signal.side not in ("BUY", "SELL"):
                raise ValueError("signal side must be BUY or SELL")
            if signal.side == "BUY" and portfolio.position is not None:
                raise ValueError("BUY signal requires a flat portfolio")
            if signal.side == "SELL" and portfolio.position is None:
                raise ValueError("SELL signal requires an open position")
            signal_records.append(SignalRecord(bar.closed_at, signal.side, signal.reason, signal.pivot))
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
    risk_per_trade: Decimal | int | str = CANSLIM_BREAKOUT_V0.risk_per_trade_pct,
    stop_fraction: Decimal | int | str = CANSLIM_BREAKOUT_V0.stop_loss_pct,
) -> BacktestResult:
    """Run the engine with date-keyed fixed signals for accounting tests."""

    return run_engine(
        bars,
        lambda index, _portfolio, _pivot: signals.get(bars[index].trading_date),
        initial_cash=initial_cash,
        fee_rate=fee_rate,
        slippage_rate=slippage_rate,
        risk_per_trade=risk_per_trade,
        stop_fraction=stop_fraction,
    )
