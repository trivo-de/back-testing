"""Capture approved raw inputs offline; this does not authorize a strategy run."""

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

from ..config import INTRADAY_SNAPSHOT_URLS
from .market_snapshot import LOCAL_TZ, validate_bars


def capture_bundle(directory: Path, local_paths: dict[str, Path] | None = None) -> Path:
    """Validate both inputs before publication; retain unknown extraction time."""
    snapshots = []
    for symbol, url in INTRADAY_SNAPSHOT_URLS.items():
        if local_paths is None:
            request = Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
            with urlopen(request, timeout=120) as response:
                raw = response.read()
            extracted_at = datetime.now(timezone.utc).isoformat()
        else:
            raw = local_paths[symbol].read_bytes()
            extracted_at = None
        bars = validate_bars(json.loads(raw))
        content_hash = hashlib.sha256(raw).hexdigest()
        snapshots.append((raw, {
            "dataset_id": f"vndirect-{symbol.lower()}-5m-20260301-20260915",
            "dataset_version": content_hash, "content_hash": content_hash,
            "symbol": symbol, "timeframe": "5m", "source_url": url,
            "extracted_at": extracted_at, "imported_at": datetime.now(timezone.utc).isoformat(),
            "timezone": "Asia/Ho_Chi_Minh",
            "count": len(bars),
            "start": datetime.fromtimestamp(bars[0]["time"], LOCAL_TZ).isoformat(),
            "end": datetime.fromtimestamp(bars[-1]["time"], LOCAL_TZ).isoformat(),
            "raw_path": f"{symbol.lower()}-{content_hash}.json",
            "timestamp_semantics": "unconfirmed", "volume_unit": "unconfirmed",
        }))
    version = hashlib.sha256("".join(m["content_hash"] for _, m in snapshots).encode()).hexdigest()
    directory.mkdir(parents=True, exist_ok=True)
    manifest_path = directory / f"bundle-{version}.json"
    if manifest_path.exists():
        read_bundle(manifest_path)
        return manifest_path
    for raw, metadata in snapshots:
        path = directory / metadata["raw_path"]
        try:
            with path.open("xb") as file:
                file.write(raw)
        except FileExistsError:
            if path.read_bytes() != raw:
                raise ValueError("Existing raw artifact has different bytes")
    manifest = {
        "schema_version": 1, "validator_version": "ohlcv-v1",
        "bundle_version": version, "mode": "raw_capture_not_backtest_ready",
        "datasets": [metadata for _, metadata in snapshots],
    }
    temporary = manifest_path.with_suffix(".tmp")
    try:
        temporary.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporary, manifest_path)
    finally:
        temporary.unlink(missing_ok=True)
    read_bundle(manifest_path)
    return manifest_path


def read_bundle(path: Path) -> dict:
    """Check manifest version and integrity without filling or aligning input."""
    manifest = json.loads(path.read_bytes())
    if manifest.get("schema_version") != 1:
        raise ValueError("Unsupported bundle schema")
    if [m["symbol"] for m in manifest["datasets"]] != list(INTRADAY_SNAPSHOT_URLS):
        raise ValueError("Bundle must contain both approved symbols")
    version = hashlib.sha256("".join(m["content_hash"] for m in manifest["datasets"]).encode()).hexdigest()
    if manifest.get("bundle_version") != version:
        raise ValueError("Bundle version mismatch")
    for metadata in manifest["datasets"]:
        if (metadata["dataset_version"] != metadata["content_hash"]
                or metadata["timeframe"] != "5m"
                or metadata["source_url"] != INTRADAY_SNAPSHOT_URLS[metadata["symbol"]]
                or metadata["timezone"] != "Asia/Ho_Chi_Minh"):
            raise ValueError("Snapshot identity mismatch")
        filename = metadata["raw_path"]
        if Path(filename).name != filename:
            raise ValueError("Raw path must be a local filename")
        raw = (path.parent / filename).read_bytes()
        if hashlib.sha256(raw).hexdigest() != metadata["content_hash"]:
            raise ValueError("Raw snapshot hash mismatch")
        bars = validate_bars(json.loads(raw))
        if len(bars) != metadata["count"]:
            raise ValueError("Raw snapshot count mismatch")
        for field, index in (("start", 0), ("end", -1)):
            if datetime.fromtimestamp(bars[index]["time"], LOCAL_TZ).isoformat() != metadata[field]:
                raise ValueError("Raw snapshot range mismatch")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=Path("data/intraday-bundles"))
    parser.add_argument("--vn30f1m", type=Path)
    parser.add_argument("--vnindex", type=Path)
    args = parser.parse_args()
    if bool(args.vn30f1m) != bool(args.vnindex):
        parser.error("Both --vn30f1m and --vnindex are required for offline import")
    paths = None if args.vn30f1m is None else {"VN30F1M": args.vn30f1m, "VNINDEX": args.vnindex}
    print(capture_bundle(args.directory, paths))
