from __future__ import annotations
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal
from typing import Sequence
from ...config import CANSLIM_BREAKOUT_V0
from ..engine import BuyContext, DecisionContext, run_engine
from ..indicators import highest, lowest, sma
from ..market import Bar, StrategyBar, trading_day
from ..portfolio import decimal
from ..results import BacktestResult
from ..trading import Fill, FixedSignal, OrderResult


@dataclass(frozen=True)
class IndicatorSnapshot:
    """The feature set required by CANSLIM, not a shared engine contract."""

    market_sma200: Decimal
    pivot: Decimal
    base_low: Decimal
    depth: Decimal
    average_volume: Decimal


def calculate_snapshot(
    highs: Sequence[Decimal | int | str],
    lows: Sequence[Decimal | int | str],
    volumes: Sequence[Decimal | int | str],
    index_closes: Sequence[Decimal | int | str],
    t: int,
    *,
    market_window: int = CANSLIM_BREAKOUT_V0.sma_window,
    base_window: int = CANSLIM_BREAKOUT_V0.base_window,
    volume_window: int = CANSLIM_BREAKOUT_V0.volume_window,
    market_t: int | None = None,
) -> IndicatorSnapshot | None:
    """Compose independent formulas using only the approved CANSLIM windows."""
    if type(t) is not int or not (0 <= t < len(highs) == len(lows) == len(volumes)):
        raise ValueError("aligned series and a valid t are required")
    if market_t is None:
        if len(index_closes) != len(highs):
            raise ValueError("aligned market series required without market_t")
        market_t = t
    if type(market_t) is not int or not -1 <= market_t < len(index_closes):
        raise ValueError("Invalid market sample index")
    market_mean = sma(index_closes, market_window, market_t + 1)
    pivot = highest(highs, base_window, t)
    base_low = lowest(lows, base_window, t)
    average_volume = sma(volumes, volume_window, t)
    if any(value is None for value in (market_mean, pivot, base_low, average_volume)):
        return None
    if pivot <= 0:
        raise ValueError("pivot must be > 0")
    return IndicatorSnapshot(market_mean, pivot, base_low, (pivot - base_low) / pivot, average_volume)


def size_buy(context: BuyContext) -> int:
    """CANSLIM fixed fractional risk, evaluated only at the fill Open."""
    risk_quantity = int((context.cash * CANSLIM_BREAKOUT_V0.risk_per_trade_pct)
                        // (context.fill_price * CANSLIM_BREAKOUT_V0.stop_loss_pct))
    affordable_quantity = int(context.cash // (context.fill_price * (1 + context.fee_rate)))
    return min(risk_quantity, affordable_quantity)


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


class CanslimStrategy:
    """Per-run state; entry references change only after execution feedback."""

    def __init__(self, *, start_date: date | None = None, independent_market: bool = False):
        self.start_date = start_date
        self.independent_market = independent_market
        self.entry_pivot: Decimal | None = None
        self.stop_reference: Decimal | None = None
        self.evaluations: list[dict] = []

    def on_execution(self, signal: FixedSignal, order: OrderResult, fill: Fill | None) -> None:
        if order.status != "FILLED":
            return
        assert fill is not None
        if signal.side == "BUY":
            self.entry_pivot = dict(signal.details)["pivot"]
            self.stop_reference = fill.price * (1 - CANSLIM_BREAKOUT_V0.stop_loss_pct)
        else:
            self.entry_pivot = self.stop_reference = None

    def evaluate(self, context: DecisionContext) -> FixedSignal | None:
        """Evaluate only the completed prefixes supplied by the engine."""
        bar = context.bars[-1]
        if self.start_date is not None and trading_day(bar.trading_date) < self.start_date:
            return None
        market = context.support_bars
        market_close = (market[-1].close if market else None) if self.independent_market else bar.index_close
        indicators = None
        if context.portfolio.position is not None:
            if self.entry_pivot is None:
                raise RuntimeError("strategy position is missing its entry pivot")
            decision = evaluate_exit(bar.close, context.portfolio.position.entry_price, self.entry_pivot)
        else:
            # ponytail: materialize bounded prefixes; use field views if long-history profiling warrants it.
            indicators = calculate_snapshot(
                [b.high for b in context.bars],
                [b.low for b in context.bars],
                [b.volume for b in context.bars],
                [b.close for b in market] if self.independent_market else [b.index_close for b in context.bars],
                len(context.bars) - 1,
                market_t=len(market) - 1 if self.independent_market else None,
            )
            decision = evaluate_entry(bar.close, bar.volume, market_close, indicators)
            if self.independent_market and indicators is None:
                reason = "INSUFFICIENT_MARKET_HISTORY" if len(market) < CANSLIM_BREAKOUT_V0.sma_window else "INSUFFICIENT_PRICE_VOLUME_HISTORY"
                decision = Decision(None, reason)
        if self.independent_market:
            self.evaluations.append({
                "time": bar.closed_at, "side": decision.side, "reason": decision.reason,
                "status": "UNEVALUABLE" if decision.reason.startswith("INSUFFICIENT_") else "EVALUATED",
                "market_sample_count": len(market),
                "market_available_at": market[-1].closed_at if market else None,
                "market_close": market_close, "indicators": indicators,
            })
        if decision.side is None:
            return None
        return FixedSignal(decision.side, reason=decision.reason, details=(("pivot", decision.pivot),))


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
    """Create fresh CANSLIM state for daily or independent intraday market data."""
    selected_bars = [bar for bar in bars if end_date is None or trading_day(bar.trading_date) <= end_date]
    if start_date is not None and (not selected_bars or start_date > trading_day(selected_bars[-1].trading_date)):
        raise ValueError("start_date must fall within the selected bars")
    strategy = CanslimStrategy(start_date=start_date, independent_market=market_bars is not None)

    result = run_engine(
        selected_bars,
        strategy.evaluate,
        initial_cash=initial_cash,
        fee_rate=fee_rate,
        slippage_rate=slippage_rate,
        size_buy=size_buy,
        on_execution=strategy.on_execution,
        support_bars=() if market_bars is None else market_bars,
        record_start=start_date,
    )
    details = () if result.portfolio.position is None else (
        ("entry_pivot", strategy.entry_pivot), ("stop_reference", strategy.stop_reference),
    )
    return replace(result, evaluations=tuple(strategy.evaluations), position_details=details)
