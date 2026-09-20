from dataclasses import fields, is_dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any
from uuid import UUID, uuid5
from ..config import BACKTEST, RESULT
from ..domain.results import BacktestResult
from .contracts import RunConfig


# Precision boundary
def quantize_result(value):
    """Recursively round Decimal values using the configured result precision."""

    if isinstance(value, Decimal):
        return value.quantize(RESULT.quantum, rounding=ROUND_HALF_UP)
    if is_dataclass(value):
        return {field.name: quantize_result(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, dict):
        return {key: quantize_result(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [quantize_result(item) for item in value]
    return value


def serialize_result(value):
    """Convert rounded Decimal values into strings."""

    value = quantize_result(value)
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, (date, UUID)):
        return value.isoformat() if isinstance(value, date) else str(value)
    if isinstance(value, dict):
        return {key: serialize_result(item) for key, item in value.items()}
    if isinstance(value, list):
        return [serialize_result(item) for item in value]
    return value


# Result mapping
def result_to_dict(
    run_id: UUID,
    metadata: dict[str, Any],
    config: RunConfig,
    result: BacktestResult,
    *,
    strategy_parameters: dict,
) -> dict[str, Any]:

    signals = []
    orders = []
    fills = []
    order_ids: dict[tuple[date, str], UUID] = {}

    for sequence, (signal, order) in enumerate(zip(result.signals, result.orders), 1):
        key = (signal.signal_date, signal.side)
        signal_id = uuid5(run_id, f"signal:{sequence}")
        order_id = uuid5(run_id, f"order:{sequence}")
        order_ids[key] = order_id
        signals.append({"signal_id": signal_id, "sequence_no": sequence, "signal_time": signal.signal_date, "side": signal.side, "reason": signal.reason, "pivot": signal.pivot})
        orders.append({"order_id": order_id, "signal_id": signal_id, "created_time": signal.signal_date, "side": order.side, "status": "unfilled" if order.status == "PENDING" else order.status.lower(), "rejection_reason": order.reason})

    fill_ids: dict[tuple[date, str], UUID] = {}
    for sequence, fill in enumerate(result.fills, 1):
        key = (fill.signal_date, fill.side)
        fill_id = uuid5(run_id, f"fill:{sequence}")
        fill_ids[(fill.fill_date, fill.side)] = fill_id
        fills.append({"fill_id": fill_id, "order_id": order_ids[key], "signal_time": fill.signal_date, "fill_time": fill.fill_date, "side": fill.side, "fill_price": fill.price, "quantity": fill.quantity, "fee": fill.fee})

    trades = []
    for sequence, trade in enumerate(result.trades, 1):
        exit_fill = next(fill for fill in result.fills if fill.side == "SELL" and fill.fill_date == trade.exit_date)
        close_reason = next(signal.reason for signal in result.signals if signal.side == "SELL" and signal.signal_date == exit_fill.signal_date)
        trades.append({"trade_id": uuid5(run_id, f"trade:{sequence}"), "entry_fill_id": fill_ids[(trade.entry_date, "BUY")], "exit_fill_id": fill_ids[(trade.exit_date, "SELL")], "entry_date": trade.entry_date, "exit_date": trade.exit_date, "quantity": trade.quantity, "entry_price": trade.entry_price, "exit_price": trade.exit_price, "fees": trade.fees, "net_pnl": trade.net_pnl, "close_reason": close_reason})

    last_snapshot = result.equity_history[-1].snapshot
    open_position = None
    if result.portfolio.position is not None:
        position = result.portfolio.position
        entry_fill = next(fill for fill in reversed(result.fills) if fill.side == "BUY")
        stop_loss_pct = Decimal(strategy_parameters["STOP_LOSS_PCT"])
        open_position = {"entry_fill_id": fill_ids[(entry_fill.fill_date, "BUY")], "quantity": position.quantity, "entry_price": position.entry_price, "entry_pivot": position.entry_pivot, "stop_reference": position.entry_price * (1 - stop_loss_pct), "market_value": last_snapshot.market_value, "unrealized_pnl": last_snapshot.unrealized_pnl}

    response = {
        "metadata": {**metadata, "run_id": run_id, "engine_version": BACKTEST.engine_version, "label": BACKTEST.result_label, "config": config, "strategy_parameters": strategy_parameters},
        "signals": signals,
        "orders": orders,
        "fills": fills,
        "trades": trades,
        "open_position": open_position,
        "equity_history": [{"trading_date": point.trading_date, **point.snapshot.__dict__} for point in result.equity_history],
        "summary": result.summary.__dict__,
    }
    if config.symbol == "VN30F1M":
        unevaluable = sum(row["status"] == "UNEVALUABLE" for row in result.evaluations)
        response["evaluations"] = result.evaluations
        response["evaluation_status"] = {
            "status": "UNEVALUABLE" if unevaluable == len(result.evaluations) else ("PARTIALLY_EVALUABLE" if unevaluable else "EVALUABLE"),
            "evaluated_bars": len(result.evaluations) - unevaluable,
            "unevaluable_bars": unevaluable,
        }
    return serialize_result(response)
