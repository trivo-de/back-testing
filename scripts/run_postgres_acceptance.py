"""Import a validated snapshot and verify PostgreSQL result round-tripping."""

import json
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid5
from backtest_hpg.application.contracts import RunConfig
from backtest_hpg.application.result_mapper import quantize_result
from backtest_hpg.application.run_backtest import BacktestService
from backtest_hpg.config import get_database_url
from backtest_hpg.infrastructure.database import PostgresRunRepository
import psycopg

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

# Snapshot persistence

def import_snapshot(dsn, metadata, hpg_bars, vnindex_bars):
    """Idempotently persist one versioned HPG/VNINDEX snapshot."""

    dataset_id = uuid5(NAMESPACE_URL, f"dataset:{metadata['dataset_id']}")
    version_id = uuid5(
        NAMESPACE_URL,
        f"dataset-version:{metadata['dataset_id']}:{metadata['dataset_version']}",
    )

    with psycopg.connect(dsn) as connection:
        connection.execute(
            """
            INSERT INTO datasets (id, name, description, created_at)
            VALUES (%s, %s, %s, now())
            ON CONFLICT (id) DO NOTHING
            """,
            (
                dataset_id,
                metadata["dataset_id"],
                "HPG and VNINDEX daily VNDIRECT snapshot",
            ),
        )

        connection.execute(
            """
            INSERT INTO dataset_versions (
                id, dataset_id, version, content_hash, source, timeframe,
                timezone, currency, price_unit, price_adjustment,
                volume_adjustment, corporate_action_policy,
                raw_artifact_uri, extracted_at, created_at
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, now()
            )
            ON CONFLICT (id) DO NOTHING
            """,
            (
                version_id,
                dataset_id,
                metadata["dataset_version"],
                metadata["content_hash"],
                metadata["source"],
                metadata["timeframe"],
                metadata["timezone"],
                metadata["currency"],
                metadata["price_unit"],
                metadata["price_adjustment"],
                metadata["volume_adjustment"],
                metadata["corporate_action_policy"],
                "data/dataset_manifest.json",
                metadata["extracted_at"],
            ),
        )

        stored = connection.execute(
            "SELECT content_hash FROM dataset_versions WHERE id = %s",
            (version_id,),
        ).fetchone()

        if stored is None or stored[0] != metadata["content_hash"]:
            raise RuntimeError("Dataset version/content hash mismatch")

        rows = [
            (
                version_id,
                bar["symbol"],
                bar["trading_date"],
                *(
                    quantize_result(Decimal(str(bar[field])))
                    for field in ("open", "high", "low", "close", "volume")
                ),
            )
            for bar in hpg_bars
        ]

        rows.extend(
            (
                version_id,
                bar["symbol"],
                bar["trading_date"],
                None,
                None,
                None,
                quantize_result(Decimal(str(bar["close"]))),
                None,
            )
            for bar in vnindex_bars
        )

        connection.cursor().executemany(
            """
            INSERT INTO market_bars (
                dataset_version_id, symbol, trading_date,
                open, high, low, close, volume
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT DO NOTHING
            """,
            rows,
        )

        counts = dict(
            connection.execute(
                """
                SELECT symbol, count(*)
                FROM market_bars
                WHERE dataset_version_id = %s
                GROUP BY symbol
                """,
                (version_id,),
            ).fetchall()
        )

        expected = {
            "HPG": len(hpg_bars),
            "VNINDEX": len(vnindex_bars),
        }

        if counts != expected:
            raise RuntimeError(
                f"Market bar counts mismatch: expected {expected}, got {counts}"
            )

    return counts


# End-to-end acceptance runner

def main():
    """Validate data, execute one run, then require an identical database reload."""

    dsn = get_database_url()
    notebook = json.loads((ROOT / "data" / "preprocessing.ipynb").read_text(encoding="utf-8"))
    namespace = {"__file__": str(ROOT / "data" / "preprocessing.ipynb"), "display": lambda value: None}
    for cell in notebook["cells"]:
        if cell["cell_type"] == "code":
            exec("".join(cell["source"]), namespace)

    metadata = namespace["metadata"]
    counts = import_snapshot(
        dsn,
        metadata,
        namespace["hpg_bars"],
        namespace["vnindex_bars"],
    )

    repository = PostgresRunRepository(dsn)
    response = BacktestService(repository).run(
        RunConfig(
            dataset_id=metadata["dataset_id"],
            dataset_version=metadata["dataset_version"],
            symbol="HPG",
            start_date=date(2020, 1, 1),
            end_date=date(2023, 12, 31),
            strategy_id="canslim_breakout_v0",
            initial_cash=Decimal("10000000"),
            fee_rate=Decimal("0.001"),
            slippage_rate=Decimal("0.002"),
        )
    )

    run_id = UUID(str(response["metadata"]["run_id"]))
    reloaded = repository.get_run(run_id)

    if reloaded != response:
        raise RuntimeError(
            "PostgreSQL reload differs from the created response"
        )

    print(
        json.dumps(
            {
                "dataset_bars": counts,
                "run_id": str(run_id),
                "status": "succeeded",
                "signals": len(response["signals"]),
                "fills": len(response["fills"]),
                "trades": len(response["trades"]),
                "final_equity": response["summary"]["final_equity"],
                "reload_equal": True,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
