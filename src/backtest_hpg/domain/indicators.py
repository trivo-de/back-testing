from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
from typing import Sequence
from ..config import CANSLIM_BREAKOUT_V0
from .portfolio import decimal

@dataclass(frozen=True)
class IndicatorSnapshot:
    """Indicator values available after the Close at one session index."""
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
) -> IndicatorSnapshot | None:
    """Calculate indicators at index ``t`` without reading any value after ``t``."""

    if not (0 <= t < len(highs) == len(lows) == len(volumes) == len(index_closes)):
        raise ValueError("aligned series and a valid t are required")
    if t < max(base_window, volume_window) or t + 1 < market_window:
        return None

    prior_highs = tuple(decimal(value) for value in highs[t - base_window : t])
    prior_lows = tuple(decimal(value) for value in lows[t - base_window : t])
    prior_volumes = tuple(decimal(value) for value in volumes[t - volume_window : t])
    market_values = tuple(decimal(value) for value in index_closes[t - market_window + 1 : t + 1])
    pivot = max(prior_highs)
    if pivot <= 0:
        raise ValueError("pivot must be > 0")
    base_low = min(prior_lows)
    return IndicatorSnapshot(
        sum(market_values) / market_window,
        pivot,
        base_low,
        (pivot - base_low) / pivot,
        sum(prior_volumes) / volume_window,
    )
