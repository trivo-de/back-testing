import copy
import hashlib
import json
import os
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import pyarrow as pa
import pyarrow.parquet as pq

from .market_snapshot import LOCAL_TZ, validate_bars

DATASET_ID = "vndirect-vn30f1m-vnindex-5m-20260301-20260915"
PRICE_FIELDS = ("open", "high", "low", "close", "volume")
PARQUET_SCHEMA = pa.schema([("time", pa.int64()), *[(name, pa.string()) for name in PRICE_FIELDS]])
_SNAPSHOT_URLS = {
    symbol: "https://dchart-api.vndirect.com.vn/dchart/history?resolution=5"
    f"&symbol={symbol}&from=1772323200&to=1789516800"
    for symbol in ("VN30F1M", "VNINDEX")
}



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


# ============================== Historical dataset reader ==============================


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
                or metadata["source_url"] != _SNAPSHOT_URLS[metadata["symbol"]]):
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



class FileRunRepository:
    """Publish full results atomically; one local process is the supported writer."""

    def __init__(self, store: Path, policy_path: Path | None = None):
        self.store = store
        self.policy_path = policy_path

    # ============================== V1: payload JSON trực tiếp ==============================

    def start_inline(self, payload, policy, data):
        """Pin the complete request and policy without requiring a registered dataset."""
        document = {'schema_version': 1, 'payload': payload, 'policy': policy, 'data_metadata': data.metadata}
        raw = _json_bytes(document)
        input_hash = hashlib.sha256(raw).hexdigest()
        path = self.store / 'inputs' / f'{input_hash}.json'
        if not path.exists(): _publish_bytes(path, raw)
        if path.read_bytes() != raw: raise ValueError('INPUT_INTEGRITY_ERROR')
        run_id = uuid4()
        _publish_json(self.store / 'runs' / f'{run_id}.json', {
            'schema_version': 2, 'status': 'running', 'input_hash': input_hash})
        return run_id, input_hash, hashlib.sha256(_json_bytes(policy)).hexdigest()

    def _inline_input(self, input_hash):
        if not isinstance(input_hash, str) or len(input_hash) != 64 or any(c not in '0123456789abcdef' for c in input_hash):
            raise ValueError('INPUT_HASH_INVALID')
        path = self.store / 'inputs' / f'{input_hash}.json'
        try:
            raw = path.read_bytes()
        except FileNotFoundError:
            raise ValueError('INPUT_ARTIFACT_MISSING') from None
        if hashlib.sha256(raw).hexdigest() != input_hash: raise ValueError('INPUT_INTEGRITY_ERROR')
        document = json.loads(raw)
        if document.get('schema_version') != 1: raise ValueError('INPUT_SCHEMA_UNSUPPORTED')
        return document

    def get_input(self, run_id):
        response = self.get_run(run_id)
        if response is None: return None
        if response.get('schema_version') != 2: raise ValueError('INLINE_INPUT_NOT_AVAILABLE_FOR_LEGACY_RUN')
        return self._inline_input(response['metadata']['input_hash'])

    # ============================== Dùng chung: trạng thái và kết quả ==============================


    def complete_run(self, run_id: UUID, result, response: dict) -> None:
        if response["metadata"]["run_id"] != str(run_id):
            raise ValueError("RUN_ID_MISMATCH")
        version = response.get('schema_version', 1)
        extra = {}
        if version == 2:
            # v1: kết quả phải khớp input_hash đã ghim khi bắt đầu chạy.
            current = json.loads((self.store / 'runs' / f'{run_id}.json').read_bytes())
            if current.get('status') != 'running' or current.get('input_hash') != response['metadata']['input_hash']:
                raise ValueError('RUN_INPUT_MISMATCH')
            self._inline_input(current['input_hash'])
            extra['input_hash'] = current['input_hash']
        elif version != 1:
            raise ValueError('RESULT_SCHEMA_UNSUPPORTED')
        _publish_json(self.store / "runs" / f"{run_id}.json", {
            "schema_version": version, "status": "succeeded", "result": response, **extra,
            "result_hash": hashlib.sha256(_json_bytes(response)).hexdigest(),
        })

    def fail_run(self, run_id: UUID, error: Exception) -> None:
        path = self.store / 'runs' / f'{run_id}.json'
        current = json.loads(path.read_bytes())
        if current.get('schema_version') == 2:
            if current.get('status') != 'running': raise ValueError('RUN_ALREADY_FINALIZED')
            _publish_json(path, {**current, 'status': 'failed', 'error_type': type(error).__name__})
            return
        _publish_json(self.store / "runs" / f"{run_id}.json", {
            "schema_version": 1, "status": "failed", "error_type": type(error).__name__,
        })

    def get_run(self, run_id: UUID) -> dict | None:
        path = self.store / "runs" / f"{run_id}.json"
        if not path.exists():
            return None
        value = json.loads(path.read_bytes())
        if value.get("schema_version") not in (1, 2):
            raise ValueError("RESULT_SCHEMA_UNSUPPORTED")
        if value.get("status") not in ("running", "failed", "succeeded"):
            raise ValueError("RESULT_STATUS_INVALID")
        if value["status"] != "succeeded":
            return None
        response = value["result"]
        if (hashlib.sha256(_json_bytes(response)).hexdigest() != value["result_hash"]
                or response["metadata"]["run_id"] != str(run_id)):
            raise ValueError("RESULT_INTEGRITY_ERROR")
        if value['schema_version'] == 2:
            # Inline runs verify the stored payload without opening a dataset manifest.
            if response.get('schema_version') != 2 or response['metadata'].get('input_hash') != value.get('input_hash'):
                raise ValueError('RUN_INPUT_MISMATCH')
            document = self._inline_input(value['input_hash'])
            if hashlib.sha256(_json_bytes(document['policy'])).hexdigest() != response['metadata']['policy_hash']:
                raise ValueError('POLICY_INTEGRITY_ERROR')
        return response

    def list_runs(self) -> list[dict]:
        return [result for path in sorted((self.store / "runs").glob("*.json"), reverse=True)
                if (result := self.get_run(UUID(path.stem))) is not None]

    def get_chart(self, run_id: UUID) -> dict | None:
        response = self.get_run(run_id)
        if response is None:
            return None
        metadata = response["metadata"]
        if response.get('schema_version') == 2:
            # v1 dựng chart từ payload JSON và input_hash.
            from ..application.inline_data import resolve_inline
            document = self._inline_input(metadata['input_hash'])
            payload = copy.deepcopy(document['payload'])
            # Keep new requests strict on `time`; read the one historical artifact
            # that used `open_time` without mutating its integrity-pinned JSON.
            for source in (payload.get('trade_data'), payload.get('market_data')):
                if source:
                    for row in source['bars']:
                        if 'time' not in row and 'open_time' in row:
                            row['time'] = row['open_time']
            data = resolve_inline(payload, document['policy'])
            def chart_rows(rows):
                return [{'time': int(bar.trading_date.timestamp()), 'open': str(bar.open), 'high': str(bar.high),
                         'low': str(bar.low), 'close': str(bar.close),
                         'volume': str(bar.volume) if bar.volume is not None else None,
                         'close_time': bar.closed_at.isoformat(), 'available_at': bar.available_at.isoformat(),
                         'contract_code': bar.contract_code}
                        for bar in rows if data.start_date <= bar.trading_date.astimezone(ZoneInfo(metadata['timezone'])).date() <= data.end_date]
            return {'metadata': metadata, 'bars': chart_rows(data.bars), 'market_bars': chart_rows(data.market_bars)}
        # Legacy runs rebuild chart data from the manifest pinned in metadata.
        manifest_path = self.store / "datasets" / f"dataset-{metadata['dataset_version']}.json"
        _, rows = _read_dataset(manifest_path)
        start, end = map(date.fromisoformat, (metadata["config"]["start_date"], metadata["config"]["end_date"]))
        bars = [row for row in rows["VN30F1M"] if start <= datetime.fromtimestamp(row["time"], LOCAL_TZ).date() <= end]
        return {"metadata": metadata, "bars": bars}

