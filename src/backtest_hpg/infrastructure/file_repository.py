"""Single-process intraday storage with immutable Parquet inputs and atomic JSON."""

import argparse
import hashlib
import json
import os
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import pyarrow as pa
import pyarrow.parquet as pq

from ..application.contracts import RunConfig
from ..config import INTRADAY_SNAPSHOT_URLS
from ..domain.market import Bar, DatasetSnapshot, StrategyBar, trading_day
from .market_snapshot import LOCAL_TZ, validate_bars
from .snapshot_bundle import read_bundle

DATASET_ID = "vndirect-vn30f1m-vnindex-5m-20260301-20260915"
PRICE_FIELDS = ("open", "high", "low", "close", "volume")
PARQUET_SCHEMA = pa.schema([("time", pa.int64()), *[(name, pa.string()) for name in PRICE_FIELDS]])


def _json_bytes(value: dict) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def _publish_bytes(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f".{uuid4().hex}.tmp")
    try:
        with temporary.open("xb") as file:
            file.write(raw)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _publish_json(path: Path, value: dict) -> None:
    _publish_bytes(path, _json_bytes(value))


def _read_parquet(path: Path):
    try:
        return pq.read_table(path)
    except pa.ArrowException:
        raise ValueError("PARQUET_STORAGE_INVALID") from None


def _raw_rows(raw: bytes) -> list[dict]:
    payload = json.loads(raw, parse_float=Decimal)
    validate_bars(payload)
    return [dict(time=values[0], **dict(zip(PRICE_FIELDS, map(str, values[1:]))))
            for values in zip(*(payload[key] for key in ("t", "o", "h", "l", "c", "v")))]


def prepare_dataset(bundle_path: Path, store: Path) -> Path:
    """Derive lossless string-price Parquet and pin it to the untouched raw bytes."""
    bundle = read_bundle(bundle_path)
    directory = store / "datasets"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"dataset-{bundle['bundle_version']}.json"
    if path.exists():
        _read_dataset(path)
        return path
    datasets = []
    for metadata in bundle["datasets"]:
        raw = (bundle_path.parent / metadata["raw_path"]).read_bytes()
        raw_path = directory / metadata["raw_path"]
        if raw_path.exists():
            if raw_path.read_bytes() != raw:
                raise ValueError("Raw artifact integrity mismatch")
        else:
            with raw_path.open("xb") as file:
                file.write(raw)
        parquet_path = raw_path.with_suffix(".parquet")
        rows = _raw_rows(raw)
        if not parquet_path.exists():
            temporary = parquet_path.with_suffix(f".{uuid4().hex}.tmp")
            try:
                pq.write_table(pa.Table.from_pylist(rows, schema=PARQUET_SCHEMA), temporary)
                os.replace(temporary, parquet_path)
            finally:
                temporary.unlink(missing_ok=True)
        table = _read_parquet(parquet_path)
        if table.schema != PARQUET_SCHEMA or table.to_pylist() != rows:
            raise ValueError("Parquet differs from raw source")
        datasets.append({**metadata, "parquet_path": parquet_path.name,
                         "parquet_hash": hashlib.sha256(parquet_path.read_bytes()).hexdigest()})
    manifest = {
        "schema_version": 1, "dataset_id": DATASET_ID,
        "dataset_version": bundle["bundle_version"], "content_hash": bundle["bundle_version"],
        "source_timeframe": "5m", "strategy_timeframe": "5m", "execution_timeframe": "5m",
        "timezone": "Asia/Ho_Chi_Minh", "window_unit": "5-minute bars",
        "datasets": datasets, "validator_version": "intraday-v1",
        "assumptions": {
            "timestamp_label": "Open", "close_and_available_delay_minutes": 5,
            "atc_1445": "retained; same 5-minute timing in normalized simulation",
            "market_alignment": "latest completed VNINDEX bar; SMA uses distinct market samples",
            "volume": "per-bar volume; raw units; no conversion",
            "price_unit": "index points", "quantity_unit": "normalized units",
            "session_gap": "fail missing expected bars; retain pending/position across scheduled breaks",
            "rollover": "hold positions and pending orders; theoretical reference map; no price adjustment",
        },
    }
    _publish_json(path, manifest)
    _read_dataset(path)
    return path


def _read_dataset(path: Path) -> tuple[dict, dict[str, list[dict]]]:
    manifest = json.loads(path.read_bytes())
    if manifest.get("schema_version") != 1 or manifest.get("dataset_id") != DATASET_ID:
        raise ValueError("DATASET_SCHEMA_UNSUPPORTED")
    metadata_list = manifest["datasets"]
    if [m["symbol"] for m in metadata_list] != ["VN30F1M", "VNINDEX"]:
        raise ValueError("DATASET_SYMBOLS_INVALID")
    version = hashlib.sha256("".join(m["content_hash"] for m in metadata_list).encode()).hexdigest()
    if manifest["dataset_version"] != version or manifest["content_hash"] != version:
        raise ValueError("DATASET_VERSION_MISMATCH")
    rows = {}
    for metadata in metadata_list:
        if (metadata["dataset_version"] != metadata["content_hash"]
                or metadata["timeframe"] != "5m" or metadata["timezone"] != "Asia/Ho_Chi_Minh"
                or metadata["source_url"] != INTRADAY_SNAPSHOT_URLS[metadata["symbol"]]):
            raise ValueError("DATASET_IDENTITY_MISMATCH")
        for name in ("raw_path", "parquet_path"):
            if Path(metadata[name]).name != metadata[name]:
                raise ValueError("DATASET_PATH_INVALID")
        raw = (path.parent / metadata["raw_path"]).read_bytes()
        parquet_path = path.parent / metadata["parquet_path"]
        if (hashlib.sha256(raw).hexdigest() != metadata["content_hash"]
                or hashlib.sha256(parquet_path.read_bytes()).hexdigest() != metadata["parquet_hash"]):
            raise ValueError("DATASET_HASH_MISMATCH")
        table = _read_parquet(parquet_path)
        values = table.to_pylist()
        if table.schema != PARQUET_SCHEMA or values != _raw_rows(raw) or len(values) != metadata["count"]:
            raise ValueError("DATASET_PARQUET_MISMATCH")
        for label, index in (("start", 0), ("end", -1)):
            if datetime.fromtimestamp(values[index]["time"], LOCAL_TZ).isoformat() != metadata[label]:
                raise ValueError("DATASET_RANGE_MISMATCH")
        rows[metadata["symbol"]] = values
    return manifest, rows


def validate_policy(policy: dict, rows: dict[str, list[dict]], config: RunConfig) -> None:
    """Require a static calendar and complete roll map; never infer them from prices."""
    if policy.get("schema_version") != 1 or policy.get("timezone") != "Asia/Ho_Chi_Minh":
        raise ValueError("POLICY_SCHEMA_INVALID")
    if policy.get("rollover_action") != "hold":
        raise ValueError("ROLLOVER_ACTION_MUST_BE_HOLD")
    days = [date.fromisoformat(value) for value in policy.get("trading_dates", [])]
    if not days or any(a >= b for a, b in zip(days, days[1:])):
        raise ValueError("TRADING_CALENDAR_REQUIRED")
    calendar_range = policy.get("calendar_range", {"start": days[0].isoformat(), "end": days[-1].isoformat()})
    calendar_start, calendar_end = map(date.fromisoformat, (calendar_range["start"], calendar_range["end"]))
    if config.start_date < calendar_start or config.end_date > calendar_end:
        raise ValueError("REPORT_OUTSIDE_STATIC_CALENDAR")
    selected = {symbol: [row for row in values if datetime.fromtimestamp(row["time"], LOCAL_TZ).date() <= config.end_date]
                for symbol, values in rows.items()}
    futures = selected["VN30F1M"]
    if not futures:
        raise ValueError("REPORT_DATA_MISSING")
    first_day = min(config.start_date, datetime.fromtimestamp(futures[0]["time"], LOCAL_TZ).date())
    expected_days = [day for day in days if first_day <= day <= config.end_date]
    if not expected_days:
        raise ValueError("REPORT_CALENDAR_EMPTY")
    for symbol, values in selected.items():
        session = policy.get("sessions", {}).get(symbol, {})
        required = session.get("required_times", [])
        optional = session.get("optional_times", [])
        if not required or len(set(required + optional)) != len(required + optional):
            raise ValueError(f"SESSION_LABELS_REQUIRED:{symbol}")
        for label in required + optional:
            if time.fromisoformat(label).strftime("%H:%M") != label:
                raise ValueError(f"SESSION_LABEL_INVALID:{symbol}")
        observed = {}
        for row in values:
            stamp = datetime.fromtimestamp(row["time"], LOCAL_TZ)
            if stamp.second or stamp.strftime("%H:%M") not in required + optional or stamp.date() not in days:
                raise ValueError(f"UNEXPECTED_BAR:{symbol}:{stamp.isoformat()}")
            observed.setdefault(stamp.date(), set()).add(stamp.strftime("%H:%M"))
        for day in expected_days:
            missing = set(required) - observed.get(day, set())
            if missing:
                raise ValueError(f"MISSING_EXPECTED_BAR:{symbol}:{day.isoformat()}:{','.join(sorted(missing))}")
    rolls = policy.get("rollover", [])
    if not rolls:
        raise ValueError("ROLLOVER_MAP_REQUIRED")
    parsed = []
    for segment in rolls:
        start, end = map(date.fromisoformat, (segment["start"], segment["end"]))
        if start > end or not isinstance(segment.get("contract"), str) or not segment["contract"].strip():
            raise ValueError("ROLLOVER_MAP_INVALID")
        parsed.append((start, end))
    if any(a[1] >= b[0] for a, b in zip(parsed, parsed[1:])):
        raise ValueError("ROLLOVER_MAP_OVERLAP_OR_ORDER")
    for day in expected_days:
        if not any(start <= day <= end for start, end in parsed):
            raise ValueError(f"ROLLOVER_MAP_MISSING:{day.isoformat()}")


class FileRunRepository:
    """Publish full results atomically; one local process is the supported writer."""

    def __init__(self, store: Path, policy_path: Path):
        self.store, self.policy_path = store, policy_path

    def start_run(self, config: RunConfig) -> tuple[UUID, DatasetSnapshot]:
        if config.symbol != "VN30F1M" or config.dataset_id != DATASET_ID:
            raise ValueError("INTRADAY_DATASET_NOT_FOUND")
        if len(config.dataset_version) != 64 or any(c not in "0123456789abcdef" for c in config.dataset_version):
            raise ValueError("DATASET_VERSION_INVALID")
        path = self.store / "datasets" / f"dataset-{config.dataset_version}.json"
        if not path.exists():
            raise ValueError("INTRADAY_DATASET_NOT_IMPORTED")
        metadata, rows = _read_dataset(path)
        if not self.policy_path.exists():
            raise ValueError("STATIC_SESSION_ROLLOVER_POLICY_REQUIRED")
        policy_raw = self.policy_path.read_bytes()
        policy = json.loads(policy_raw)
        validate_policy(policy, rows, config)
        policy_hash = hashlib.sha256(policy_raw).hexdigest()
        policy_copy = self.store / "policies" / f"{policy_hash}.json"
        if not policy_copy.exists():
            _publish_bytes(policy_copy, policy_raw)
        if policy_copy.read_bytes() != policy_raw:
            raise ValueError("POLICY_INTEGRITY_ERROR")
        bars = []
        market = []
        for symbol, values in rows.items():
            for row in values:
                opened = datetime.fromtimestamp(row["time"], LOCAL_TZ)
                closed = opened + timedelta(minutes=5)
                if symbol == "VN30F1M":
                    bars.append(StrategyBar(opened, *(Decimal(row[k]) for k in PRICE_FIELDS), close_time=closed))
                else:
                    market.append(Bar(opened, Decimal(row["open"]), Decimal(row["close"]), closed))
        warmup = {
            "VN30F1M": [bar for bar in bars if trading_day(bar.trading_date) < config.start_date],
            "VNINDEX": [bar for bar in market if trading_day(bar.trading_date) < config.start_date],
        }
        metadata = {**metadata, "policy_hash": policy_hash,
                    "dataset_manifest_hash": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "rollover_source": policy.get("rollover_source", {"status": "synthetic test policy"}),
                    "assumptions": {**metadata["assumptions"],
                                    "rollover": "hold positions/pending; theoretical reference map; no forced exit or price adjustment"},
                    "report_range": {"start": config.start_date.isoformat(), "end": config.end_date.isoformat()},
                    "warmup_bars": {symbol: len(values) for symbol, values in warmup.items()},
                    "warmup_range": {symbol: {
                        "start": values[0].trading_date.isoformat() if values else None,
                        "end": values[-1].closed_at.isoformat() if values else None,
                    } for symbol, values in warmup.items()}}
        run_id = uuid4()
        _publish_json(self.store / "runs" / f"{run_id}.json", {"schema_version": 1, "status": "running"})
        return run_id, DatasetSnapshot(metadata, tuple(bars), tuple(market))

    def complete_run(self, run_id: UUID, result, response: dict) -> None:
        if response["metadata"]["run_id"] != str(run_id):
            raise ValueError("RUN_ID_MISMATCH")
        _publish_json(self.store / "runs" / f"{run_id}.json", {
            "schema_version": 1, "status": "succeeded", "result": response,
            "result_hash": hashlib.sha256(_json_bytes(response)).hexdigest(),
        })

    def fail_run(self, run_id: UUID, error: Exception) -> None:
        _publish_json(self.store / "runs" / f"{run_id}.json", {
            "schema_version": 1, "status": "failed", "error_type": type(error).__name__,
        })

    def get_run(self, run_id: UUID) -> dict | None:
        path = self.store / "runs" / f"{run_id}.json"
        if not path.exists():
            return None
        value = json.loads(path.read_bytes())
        if value.get("schema_version") != 1:
            raise ValueError("RESULT_SCHEMA_UNSUPPORTED")
        if value.get("status") not in ("running", "failed", "succeeded"):
            raise ValueError("RESULT_STATUS_INVALID")
        if value["status"] != "succeeded":
            return None
        response = value["result"]
        if (hashlib.sha256(_json_bytes(response)).hexdigest() != value["result_hash"]
                or response["metadata"]["run_id"] != str(run_id)):
            raise ValueError("RESULT_INTEGRITY_ERROR")
        return response

    def list_runs(self) -> list[dict]:
        return [result for path in sorted((self.store / "runs").glob("*.json"), reverse=True)
                if (result := self.get_run(UUID(path.stem))) is not None]

    def get_chart(self, run_id: UUID) -> dict | None:
        response = self.get_run(run_id)
        if response is None:
            return None
        metadata = response["metadata"]
        manifest_path = self.store / "datasets" / f"dataset-{metadata['dataset_version']}.json"
        _, rows = _read_dataset(manifest_path)
        start, end = map(date.fromisoformat, (metadata["config"]["start_date"], metadata["config"]["end_date"]))
        bars = [row for row in rows["VN30F1M"] if start <= datetime.fromtimestamp(row["time"], LOCAL_TZ).date() <= end]
        return {"metadata": metadata, "bars": bars}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Prepare validated intraday Parquet datasets")
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--store", type=Path, default=Path("data/backtest-store"))
    args = parser.parse_args()
    print(prepare_dataset(args.bundle, args.store))
