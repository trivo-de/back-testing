"""Independent rolling formulas; callers choose windows and availability."""

from decimal import Decimal, InvalidOperation
from typing import Sequence
from .portfolio import decimal


def _window(series: Sequence[Decimal | int | str], window: int, end_exclusive: int) -> tuple[Decimal, ...] | None:
    if type(window) is not int or window <= 0:
        raise ValueError("window must be a positive integer")
    if type(end_exclusive) is not int or not 0 <= end_exclusive <= len(series):
        raise ValueError("end_exclusive must be an integer within the series")
    try:
        values = tuple(decimal(value) for value in series[max(0, end_exclusive - window):end_exclusive])
    except (InvalidOperation, TypeError, ValueError) as error:
        raise ValueError("indicator samples must be finite numbers") from error
    return values if end_exclusive >= window else None


def sma(series: Sequence[Decimal | int | str], window: int, end_exclusive: int) -> Decimal | None:
    """Mean of [end-window:end], or None during warm-up."""
    values = _window(series, window, end_exclusive)
    return None if values is None else sum(values) / window


def highest(series: Sequence[Decimal | int | str], window: int, end_exclusive: int) -> Decimal | None:
    """Highest value in [end-window:end], or None during warm-up."""
    values = _window(series, window, end_exclusive)
    return None if values is None else max(values)


def lowest(series: Sequence[Decimal | int | str], window: int, end_exclusive: int) -> Decimal | None:
    """Lowest value in [end-window:end], or None during warm-up."""
    values = _window(series, window, end_exclusive)
    return None if values is None else min(values)
