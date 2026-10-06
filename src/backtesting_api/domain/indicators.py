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


def ema_series(series, window):
    """Seed with SMA(window); emit one value per input, including warm-up None values."""
    _window(series, window, len(series))
    values = [decimal(value) for value in series]
    result = [None] * len(values)
    if len(values) < window: return result
    value = sum(values[:window]) / window
    result[window - 1] = value
    alpha = Decimal(2) / (window + 1)
    for index in range(window, len(values)):
        value = values[index] * alpha + value * (1 - alpha)
        result[index] = value
    return result


def ema(series, window, end_exclusive):
    """Return the EMA at the requested completed prefix."""
    _window(series, window, end_exclusive)
    values = ema_series(series[:end_exclusive], window)
    return values[-1] if values else None


def bb(series, window, end_exclusive, stddev_multiplier=2):
    """Bollinger bands with population variance (ddof=0)."""
    values = _window(series, window, end_exclusive)
    multiplier = decimal(stddev_multiplier)
    if multiplier <= 0: raise ValueError('stddev_multiplier must be positive')
    if values is None: return None
    middle = sum(values) / window
    sigma = (sum((value - middle) ** 2 for value in values) / window).sqrt()
    return {'middle': middle, 'upper': middle + multiplier * sigma, 'lower': middle - multiplier * sigma}


def macd_series(series, fast_period=12, slow_period=26, signal_period=9):
    """Return line, signal and the explicitly approved line-based histogram."""
    if fast_period >= slow_period: raise ValueError('fast_period must be less than slow_period')
    fast, slow = ema_series(series, fast_period), ema_series(series, slow_period)
    line = [a - b if a is not None and b is not None else None for a, b in zip(fast, slow)]
    valid = [value for value in line if value is not None]
    signal = [None] * (len(line) - len(valid)) + ema_series(valid, signal_period)
    return {'line': line, 'signal': signal, 'histogram': line.copy()}


def macd(series, end_exclusive, fast_period=12, slow_period=26, signal_period=9):
    """Return MACD outputs at the requested completed prefix."""
    _window(series, fast_period, end_exclusive)
    values = macd_series(series[:end_exclusive], fast_period, slow_period, signal_period)
    return {name: rows[-1] if rows else None for name, rows in values.items()}


def mfi(bars, window, end_exclusive):
    """Use window price changes (window+1 bars); unchanged prices contribute no flow."""
    _window([], window, 0)
    if type(end_exclusive) is not int or not 0 <= end_exclusive <= len(bars):
        raise ValueError('end_exclusive must be within the series')
    if end_exclusive <= window: return None
    rows = bars[end_exclusive - window - 1:end_exclusive]
    typical = [(decimal(b.high) + decimal(b.low) + decimal(b.close)) / 3 for b in rows]
    positive = negative = Decimal(0)
    for index, bar in enumerate(rows[1:], 1):
        volume = decimal(bar.volume)
        if volume < 0: raise ValueError('volume must be nonnegative')
        flow = typical[index] * volume
        if typical[index] > typical[index - 1]: positive += flow
        elif typical[index] < typical[index - 1]: negative += flow
    if positive == negative == 0: return Decimal(50)
    if negative == 0: return Decimal(100)
    return 100 - 100 / (1 + positive / negative)
