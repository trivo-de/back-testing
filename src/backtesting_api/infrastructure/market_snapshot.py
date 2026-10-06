"""Validate and normalize raw OHLCV without trading assumptions."""

import math
from datetime import timedelta, timezone
from decimal import Decimal

LOCAL_TZ = timezone(timedelta(hours=7))


def validate_bars(payload: dict) -> list[dict]:
    """Reject invalid arrays, ordering and OHLCV; never repair market data."""
    fields = ("t", "o", "h", "l", "c", "v")
    if not isinstance(payload, dict) or payload.get("s") != "ok":
        raise ValueError("Invalid snapshot status")
    if any(not isinstance(payload.get(key), list) for key in fields):
        raise ValueError("Missing OHLCV arrays")
    if not payload["t"] or len({len(payload[key]) for key in fields}) != 1:
        raise ValueError("Empty or unequal OHLCV arrays")
    bars = []
    previous = -1
    for timestamp, open_, high, low, close, volume in zip(*(payload[key] for key in fields)):
        if type(timestamp) is not int or timestamp <= previous:
            raise ValueError("Timestamps must be strictly increasing Unix seconds")
        values = (open_, high, low, close, volume)
        if any(type(value) not in (int, float, Decimal)
               or (not value.is_finite() if isinstance(value, Decimal)
                   else type(value) is float and not math.isfinite(value)) for value in values):
            raise ValueError("OHLCV must be finite numbers")
        if min(open_, high, low, close) <= 0 or volume < 0 or not low <= min(open_, close) <= max(open_, close) <= high:
            raise ValueError("Invalid OHLCV range")
        bars.append(dict(time=timestamp, open=open_, high=high, low=low, close=close, volume=volume))
        previous = timestamp
    return bars


def parse_raw_bars(raw_payload: dict) -> list[dict]:
    """Parse raw columnar OHLCV payload ('s', 't', 'o', 'h', 'l', 'c', 'v') into standard bar dicts."""
    payload = dict(raw_payload)
    if "s" not in payload:
        payload["s"] = "ok"
    cleaned = {}
    for key, val in payload.items():
        if key in ("o", "h", "l", "c", "v") and isinstance(val, list):
            converted = []
            for item in val:
                if isinstance(item, str):
                    try:
                        converted.append(Decimal(item))
                    except Exception:
                        converted.append(item)
                else:
                    converted.append(item)
            cleaned[key] = converted
        else:
            cleaned[key] = val
    bars = validate_bars(cleaned)
    return [
        {
            "time": bar["time"],
            "open": str(bar["open"]),
            "high": str(bar["high"]),
            "low": str(bar["low"]),
            "close": str(bar["close"]),
            "volume": str(bar["volume"]),
        }
        for bar in bars
    ]


def normalize_raw_source(source: dict) -> dict:
    """Normalize source dictionary with raw columnar data into standard bars format."""
    if not isinstance(source, dict):
        return source
    data = dict(source)
    if isinstance(data.get("bars"), dict):
        data["bars"] = parse_raw_bars(data["bars"])
        return data

    if isinstance(data.get("raw"), dict):
        data["bars"] = parse_raw_bars(data.pop("raw"))
        data.setdefault("resolution", "5")
        data.setdefault("timezone", "Asia/Ho_Chi_Minh")
        data.setdefault("timestamp_unit", "s")
        return data

    raw_keys = ("t", "o", "h", "l", "c", "v")
    if any(key in data for key in raw_keys) or ("bars" not in data and "s" in data):
        raw_dict = {key: data.pop(key) for key in ("s", "t", "o", "h", "l", "c", "v") if key in data}
        data["bars"] = parse_raw_bars(raw_dict)
        data.setdefault("resolution", "5")
        data.setdefault("timezone", "Asia/Ho_Chi_Minh")
        data.setdefault("timestamp_unit", "s")
        return data

    return data
