from __future__ import annotations
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Sequence
from ...config import CANSLIM_BREAKOUT_V0
from ..engine import run_engine
from ..indicators import IndicatorSnapshot, calculate_snapshot
from ..market import Bar, StrategyBar
from ..portfolio import Portfolio, decimal
from ..results import BacktestResult
from ..trading import FixedSignal


# Strategy decisions
@dataclass(frozen=True)
class Decision:
    """Strategy decision made after a completed daily Close."""

    side: str | None
    reason: str
    pivot: Decimal | None = None


def evaluate_entry(
    close: Decimal | int | str,
    volume: Decimal | int | str,
    index_close: Decimal | int | str,
    indicators: IndicatorSnapshot | None,
) -> Decision:
    """Evaluate all entry rules without treating missing warm-up data as passed."""

    if indicators is None:
        return Decision(None, "WARM_UP")
    price, current_volume, market = decimal(close), decimal(volume), decimal(index_close)
    checks = {
        "MARKET": market > indicators.market_sma200,
        "BASE_DEPTH": indicators.depth <= CANSLIM_BREAKOUT_V0.max_base_depth,
        "BREAKOUT": indicators.pivot < price <= indicators.pivot * CANSLIM_BREAKOUT_V0.buy_zone_multiplier,
        "VOLUME": indicators.average_volume > 0 and current_volume >= CANSLIM_BREAKOUT_V0.volume_multiplier * indicators.average_volume,
    }
    failed = tuple(name for name, passed in checks.items() if not passed)
    return Decision("BUY", "ALL_ENTRY_RULES_PASS", indicators.pivot) if not failed else Decision(None, "FAILED:" + ",".join(failed))


def evaluate_exit(
    close: Decimal | int | str,
    entry_fill_price: Decimal | int | str,
    entry_pivot: Decimal | int | str,
) -> Decision:
    """Evaluate Close-based stop-loss before take-profit for an open position."""

    price, fill, pivot = decimal(close), decimal(entry_fill_price), decimal(entry_pivot)
    if price <= fill * (1 - CANSLIM_BREAKOUT_V0.stop_loss_pct):
        return Decision("SELL", "STOP_LOSS", pivot)
    if price >= pivot * (1 + CANSLIM_BREAKOUT_V0.take_profit_pct):
        return Decision("SELL", "TAKE_PROFIT", pivot)
    return Decision(None, "HOLD", pivot)


# Registered strategy runner

def run(
    bars: Sequence[StrategyBar],
    *,
    initial_cash: Decimal | int | str,
    fee_rate: Decimal | int | str,
    slippage_rate: Decimal | int | str,
    start_date: date | None = None,
    end_date: date | None = None,
) -> BacktestResult:
    """Run CANSLIM v0 on aligned daily bars through the shared execution engine."""

    selected_bars = [bar for bar in bars if end_date is None or bar.trading_date <= end_date]
    if start_date is not None and (not selected_bars or start_date > selected_bars[-1].trading_date):
        raise ValueError("start_date must fall within the selected bars")
    highs = [bar.high for bar in selected_bars]
    lows = [bar.low for bar in selected_bars]
    volumes = [bar.volume for bar in selected_bars]
    index_closes = [bar.index_close for bar in selected_bars]

    def provide_signal(index: int, portfolio: Portfolio, entry_pivot: Decimal | None) -> FixedSignal | None:
        """Translate the current strategy decision into a pending intent."""

        bar = selected_bars[index]
        if start_date is not None and bar.trading_date < start_date:
            return None
        if portfolio.position is not None:
            if entry_pivot is None:
                raise RuntimeError("strategy position is missing its entry pivot")
            decision = evaluate_exit(bar.close, portfolio.position.entry_price, entry_pivot)
        else:
            indicators = calculate_snapshot(
                highs,
                lows,
                volumes,
                index_closes,
                index,
                market_window=CANSLIM_BREAKOUT_V0.sma_window,
                base_window=CANSLIM_BREAKOUT_V0.base_window,
                volume_window=CANSLIM_BREAKOUT_V0.volume_window,
            )
            decision = evaluate_entry(bar.close, bar.volume, bar.index_close, indicators)
        return None if decision.side is None else FixedSignal(decision.side, pivot=decision.pivot, reason=decision.reason)

    execution_bars = [Bar(bar.trading_date, bar.open, bar.close) for bar in selected_bars]
    return run_engine(
        execution_bars,
        provide_signal,
        initial_cash=initial_cash,
        fee_rate=fee_rate,
        slippage_rate=slippage_rate,
        risk_per_trade=CANSLIM_BREAKOUT_V0.risk_per_trade_pct,
        stop_fraction=CANSLIM_BREAKOUT_V0.stop_loss_pct,
        record_start=start_date,
    )
