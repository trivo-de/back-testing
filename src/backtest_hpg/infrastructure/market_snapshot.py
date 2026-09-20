"""Read the approved immutable VN30F1M snapshot without trading assumptions."""

import hashlib
import json
import math
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from ..config import VN30F1M_CONTENT_HASH as CONTENT_HASH, VN30F1M_DATASET_ID as DATASET_ID

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


def read_snapshot(path: Path) -> dict:
    """Verify bytes against the approved hash before exposing any candles."""
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != CONTENT_HASH:
        raise ValueError("Snapshot hash differs from the approved VN30F1M dataset")
    bars = validate_bars(json.loads(raw))
    start = datetime.fromtimestamp(bars[0]["time"], LOCAL_TZ).isoformat()
    end = datetime.fromtimestamp(bars[-1]["time"], LOCAL_TZ).isoformat()
    if len(bars) != 6174 or start != "2026-03-16T09:00:00+07:00" or end != "2026-09-15T14:45:00+07:00":
        raise ValueError("Snapshot count or range differs from the approved contract")
    return {
        "metadata": {
            "dataset_id": DATASET_ID, "dataset_version": CONTENT_HASH,
            "content_hash": CONTENT_HASH, "symbol": "VN30F1M", "timeframe": "5m",
            "timezone": "Asia/Ho_Chi_Minh", "price_unit": "source price",
            "volume_unit": "unknown", "timestamp_semantics": "unconfirmed",
            "start": start, "end": end, "total_bars": len(bars),
            "mode": "market_snapshot", "extracted_at": None,
        },
        "bars": bars,
    }
