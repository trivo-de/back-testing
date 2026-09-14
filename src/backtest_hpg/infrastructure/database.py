from __future__ import annotations
from decimal import Decimal
from typing import Any, Sequence
from uuid import UUID, uuid4
import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from ..application.contracts import RunConfig
from ..application.result_mapper import serialize_result
from ..config import BACKTEST
from ..domain.market import DatasetSnapshot, StrategyBar
from ..domain.results import BacktestResult
from ..domain.strategies import get_strategy_parameters


class PostgresRunRepository:
    """Implement the application repository port with short PostgreSQL transactions."""

    def __init__(self, dsn: str):
        """Store the runtime connection string without opening a connection."""

        self.dsn = dsn

    # Run creation and dataset loading
    def start_run(self, config: RunConfig) -> tuple[UUID, DatasetSnapshot]:
        """Create a running record and load its aligned immutable market snapshot."""

        run_id = uuid4()
        strategy_parameters = get_strategy_parameters(config.strategy_id)
        with psycopg.connect(self.dsn, row_factory=dict_row) as connection:
            version = connection.execute(
                """SELECT dv.*, d.name AS dataset_name
                   FROM dataset_versions dv JOIN datasets d ON d.id = dv.dataset_id
                   WHERE d.name = %s AND dv.version = %s""",
                (config.dataset_id, config.dataset_version),
            ).fetchone()
            if version is None:
                raise ValueError("dataset version not found")
            connection.execute(
                """INSERT INTO backtest_runs
                   (id, dataset_version_id, strategy_id, engine_version, start_date, end_date,
                    initial_cash, config, strategy_parameters, status, created_at, started_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'pending',now(),NULL)""",
                (
                    run_id, version["id"], config.strategy_id, BACKTEST.engine_version,
                    config.start_date, config.end_date, serialize_result(config.initial_cash),
                    Jsonb({"symbol": config.symbol, "fee_rate": serialize_result(config.fee_rate), "slippage_rate": serialize_result(config.slippage_rate)}),
                    Jsonb(strategy_parameters),
                ),
            )
            connection.execute("UPDATE backtest_runs SET status='running', started_at=now() WHERE id=%s", (run_id,))
            rows = connection.execute(
                """SELECT h.trading_date, h.open, h.high, h.low, h.close, h.volume,
                          i.close AS index_close
                   FROM market_bars h
                   LEFT JOIN market_bars i
                     ON i.dataset_version_id = h.dataset_version_id
                    AND i.symbol = 'VNINDEX' AND i.trading_date = h.trading_date
                   WHERE h.dataset_version_id = %s AND h.symbol = 'HPG'
                   ORDER BY h.trading_date""",
                (version["id"],),
            ).fetchall()
            if not rows or any(any(row[field] is None for field in ("open", "high", "low", "close", "volume", "index_close")) for row in rows):
                raise ValueError("dataset has missing HPG OHLCV or aligned VNINDEX Close")

        metadata = {
            "dataset_id": version["dataset_name"],
            "dataset_version": version["version"],
            "content_hash": version["content_hash"],
        }
        bars = tuple(StrategyBar(row["trading_date"], row["open"], row["high"], row["low"], row["close"], row["volume"], row["index_close"]) for row in rows)
        return run_id, DatasetSnapshot(metadata, bars)

    # Successful result persistence
    def complete_run(self, run_id: UUID, result: BacktestResult, response: dict[str, Any]) -> None:
        """Persist the full audit trail and mark the run succeeded in one transaction."""

        signals, orders, fills, trades = response["signals"], response["orders"], response["fills"], response["trades"]
        fill_by_order = {fill["order_id"]: fill for fill in fills}
        with psycopg.connect(self.dsn) as connection:
            connection.cursor().executemany(
                "INSERT INTO signals (id,run_id,sequence_no,signal_time,side,reason,pivot,details) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                [(row["signal_id"], run_id, row["sequence_no"], row["signal_time"], row["side"], row["reason"], row["pivot"], Jsonb({})) for row in signals],
            )
            connection.cursor().executemany(
                """INSERT INTO orders
                   (id,run_id,signal_id,created_time,side,status,quantity,rejection_reason,sizing_details)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                [(row["order_id"], run_id, row["signal_id"], row["created_time"], row["side"], row["status"], fill_by_order.get(row["order_id"], {}).get("quantity"), row["rejection_reason"], Jsonb({})) for row in orders],
            )
            connection.cursor().executemany(
                "INSERT INTO fills (id,run_id,order_id,fill_time,side,quantity,fill_price,fee) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                [(row["fill_id"], run_id, row["order_id"], row["fill_time"], row["side"], row["quantity"], row["fill_price"], row["fee"]) for row in fills],
            )
            connection.cursor().executemany(
                """INSERT INTO trades
                   (id,run_id,entry_fill_id,exit_fill_id,quantity,entry_value,exit_value,total_fees,net_realized_pnl,close_reason)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                [(row["trade_id"], run_id, row["entry_fill_id"], row["exit_fill_id"], row["quantity"], Decimal(row["entry_price"]) * row["quantity"], Decimal(row["exit_price"]) * row["quantity"], row["fees"], row["net_pnl"], row["close_reason"]) for row in trades],
            )
            connection.cursor().executemany(
                """INSERT INTO equity_snapshots
                   (run_id,trading_date,cash,quantity,market_value,equity,unrealized_pnl)
                   VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                [(run_id, row["trading_date"], row["cash"], row["quantity"], row["market_value"], row["equity"], row["unrealized_pnl"]) for row in response["equity_history"]],
            )
            if response["open_position"] is not None:
                row = response["open_position"]
                connection.execute(
                    """INSERT INTO open_positions
                       (run_id,entry_fill_id,quantity,entry_pivot,stop_reference,market_value,unrealized_pnl)
                       VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                    (run_id, row["entry_fill_id"], row["quantity"], row["entry_pivot"], row["stop_reference"], row["market_value"], row["unrealized_pnl"]),
                )
            updated = connection.execute(
                "UPDATE backtest_runs SET status='succeeded', completed_at=now() WHERE id=%s AND status='running' RETURNING id",
                (run_id,),
            ).fetchone()
            if updated is None:
                raise RuntimeError("run is not in running state")

    def fail_run(self, run_id: UUID, error: Exception) -> None:
        """Persist failure metadata unless the run already succeeded."""

        with psycopg.connect(self.dsn) as connection:
            connection.execute(
                """UPDATE backtest_runs SET status='failed', error_code=%s, error_detail=%s,
                   completed_at=now() WHERE id=%s AND status <> 'succeeded'""",
                (type(error).__name__, Jsonb({"message": str(error)}), run_id),
            )

    # Result queries
    def get_run(self, run_id: UUID) -> dict[str, Any] | None:
        """Rebuild the serialized response for one successful run."""

        with psycopg.connect(self.dsn, row_factory=dict_row) as connection:
            header = connection.execute(
                """SELECT r.*, d.name AS dataset_name, dv.version AS dataset_version, dv.content_hash
                   FROM backtest_runs r JOIN dataset_versions dv ON dv.id=r.dataset_version_id
                   JOIN datasets d ON d.id=dv.dataset_id
                   WHERE r.id=%s AND r.status='succeeded'""",
                (run_id,),
            ).fetchone()
            if header is None:
                return None
            signals = connection.execute("SELECT id AS signal_id,sequence_no,signal_time,side,reason,pivot FROM signals WHERE run_id=%s ORDER BY sequence_no", (run_id,)).fetchall()
            orders = connection.execute("""SELECT o.id AS order_id,o.signal_id,o.created_time,o.side,o.status,o.rejection_reason
                                           FROM orders o JOIN signals s ON s.id=o.signal_id WHERE o.run_id=%s ORDER BY s.sequence_no""", (run_id,)).fetchall()
            fills = connection.execute("""SELECT f.id AS fill_id,f.order_id,s.signal_time,f.fill_time,f.side,f.fill_price,f.quantity,f.fee
                                          FROM fills f JOIN orders o ON o.id=f.order_id JOIN signals s ON s.id=o.signal_id
                                          WHERE f.run_id=%s ORDER BY s.sequence_no""", (run_id,)).fetchall()
            trades = connection.execute("""SELECT t.id AS trade_id,t.entry_fill_id,t.exit_fill_id,ef.fill_time AS entry_date,
                                            xf.fill_time AS exit_date,t.quantity,ef.fill_price AS entry_price,xf.fill_price AS exit_price,
                                            t.total_fees AS fees,t.net_realized_pnl AS net_pnl,t.close_reason
                                            FROM trades t JOIN fills ef ON ef.id=t.entry_fill_id JOIN fills xf ON xf.id=t.exit_fill_id
                                            WHERE t.run_id=%s ORDER BY ef.fill_time""", (run_id,)).fetchall()
            equity = connection.execute("SELECT trading_date,cash,quantity,market_value,equity,unrealized_pnl FROM equity_snapshots WHERE run_id=%s ORDER BY trading_date", (run_id,)).fetchall()
            position = connection.execute("""SELECT p.entry_fill_id,p.quantity,f.fill_price AS entry_price,p.entry_pivot,p.stop_reference,
                                              p.market_value,p.unrealized_pnl FROM open_positions p JOIN fills f ON f.id=p.entry_fill_id
                                              WHERE p.run_id=%s""", (run_id,)).fetchone()

        final = equity[-1]
        realized = sum((row["net_pnl"] for row in trades), Decimal(0))
        response = {
            "metadata": {
                "run_id": run_id, "dataset_id": header["dataset_name"], "dataset_version": header["dataset_version"],
                "content_hash": header["content_hash"], "engine_version": header["engine_version"], "label": BACKTEST.result_label,
                "config": {
                    "dataset_id": header["dataset_name"], "dataset_version": header["dataset_version"], "symbol": header["config"]["symbol"],
                    "start_date": header["start_date"], "end_date": header["end_date"], "strategy_id": header["strategy_id"],
                    "initial_cash": header["initial_cash"], "fee_rate": Decimal(header["config"]["fee_rate"]),
                    "slippage_rate": Decimal(header["config"]["slippage_rate"]),
                },
                "strategy_parameters": header["strategy_parameters"],
            },
            "signals": list(signals), "orders": list(orders), "fills": list(fills), "trades": list(trades),
            "open_position": dict(position) if position else None, "equity_history": list(equity),
            "summary": {
                "initial_cash": header["initial_cash"], "final_equity": final["equity"], "realized_pnl": realized,
                "unrealized_pnl": final["unrealized_pnl"], "total_return": (final["equity"] - header["initial_cash"]) / header["initial_cash"],
            },
        }
        return serialize_result(response)

    def list_runs(self) -> Sequence[dict[str, Any]]:
        """Return successful runs from newest to oldest."""

        with psycopg.connect(self.dsn) as connection:
            run_ids = [row[0] for row in connection.execute("SELECT id FROM backtest_runs WHERE status='succeeded' ORDER BY created_at DESC").fetchall()]

        return [run for run_id in run_ids if (run := self.get_run(run_id)) is not None]
