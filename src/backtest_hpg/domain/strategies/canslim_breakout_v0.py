from __future__ import annotations
from dataclasses import dataclass, replace
from bisect import bisect_right
from datetime import date
from decimal import Decimal
from typing import Sequence
from ...config import CANSLIM_BREAKOUT_V0
from ..engine import run_engine
from ..indicators import IndicatorSnapshot, calculate_snapshot
from ..market import Bar, StrategyBar, trading_day
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
    market_bars: Sequence[Bar] | None = None,
) -> BacktestResult:
    """Run daily baseline or intraday bars with independently timed market samples."""

    selected_bars = [bar for bar in bars if end_date is None or trading_day(bar.trading_date) <= end_date]
    if start_date is not None and (not selected_bars or start_date > trading_day(selected_bars[-1].trading_date)):
        raise ValueError("start_date must fall within the selected bars")
    highs = [bar.high for bar in selected_bars]
    lows = [bar.low for bar in selected_bars]
    volumes = [bar.volume for bar in selected_bars]
    index_closes = [bar.index_close for bar in selected_bars] if market_bars is None else [bar.close for bar in market_bars]
    market_times = [] if market_bars is None else [bar.closed_at for bar in market_bars]
    if any(current >= following for current, following in zip(market_times, market_times[1:])):
        raise ValueError("Market availability timestamps must be strictly increasing")
    evaluations = []

    def provide_signal(index: int, portfolio: Portfolio, entry_pivot: Decimal | None) -> FixedSignal | None:
        """Translate the current strategy decision into a pending intent."""

        bar = selected_bars[index]
        if start_date is not None and trading_day(bar.trading_date) < start_date:
            return None
        market_t = None if market_bars is None else bisect_right(market_times, bar.closed_at) - 1
        market_close = bar.index_close if market_bars is None else (market_bars[market_t].close if market_t >= 0 else None)
        indicators = None
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
                market_t=market_t,
            )
            decision = evaluate_entry(bar.close, bar.volume, market_close, indicators)
            if market_bars is not None and indicators is None:
                reason = "INSUFFICIENT_MARKET_HISTORY" if market_t + 1 < CANSLIM_BREAKOUT_V0.sma_window else "INSUFFICIENT_PRICE_VOLUME_HISTORY"
                decision = Decision(None, reason)
        if market_bars is not None:
            evaluations.append({
                "time": bar.closed_at, "side": decision.side, "reason": decision.reason,
                "status": "UNEVALUABLE" if decision.reason.startswith("INSUFFICIENT_") else "EVALUATED",
                "market_sample_count": market_t + 1,
                "market_available_at": market_times[market_t] if market_t >= 0 else None,
                "market_close": market_close, "indicators": indicators,
            })
        return None if decision.side is None else FixedSignal(decision.side, pivot=decision.pivot, reason=decision.reason)

    execution_bars = [Bar(bar.trading_date, bar.open, bar.close, bar.close_time) for bar in selected_bars]
    result = run_engine(
        execution_bars,
        provide_signal,
        initial_cash=initial_cash,
        fee_rate=fee_rate,
        slippage_rate=slippage_rate,
        risk_per_trade=CANSLIM_BREAKOUT_V0.risk_per_trade_pct,
        stop_fraction=CANSLIM_BREAKOUT_V0.stop_loss_pct,
        record_start=start_date,
    )
    return replace(result, evaluations=tuple(evaluations))
