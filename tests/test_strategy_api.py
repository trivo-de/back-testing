"""Các chiến lược thử chỉ kiểm tra hợp đồng API, không đăng ký vào sản phẩm."""

from dataclasses import replace
from decimal import Decimal
import unittest
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient
from pydantic import BaseModel, ConfigDict, Field, model_validator

from backtest_hpg.api.app import create_app
from backtest_hpg.application.run_backtest import BacktestService
from backtest_hpg.domain.engine import run_engine
from backtest_hpg.domain.strategies import StrategyDefinition, strategies
from backtest_hpg.domain.strategies.canslim_breakout_v0 import Parameters, run
from backtest_hpg.domain.trading import FixedSignal
from test_application_api import MemoryRepository
from test_strategy_backtest import strategy_bars


class Entry(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    quantity: int = Field(gt=0)
    after_bars: int = Field(gt=0)


class FixtureParameters(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    entry: Entry
    enabled: bool = True
    exit_after: int = Field(gt=0)

    @model_validator(mode="after")
    def entry_before_exit(self):
        if self.exit_after <= self.entry.after_bars:
            raise ValueError("exit_after phải lớn hơn entry.after_bars")
        return self


def fixture_runner(bars, *, params, initial_cash, fee_rate, slippage_rate, start_date, end_date,
                   flat_dates=frozenset()):
    def evaluate(context):
        if params.enabled and len(context.bars) == params.entry.after_bars:
            return FixedSignal("BUY", params.entry.quantity)
        if context.portfolio.position and len(context.bars) == params.exit_after:
            return FixedSignal("SELL")
        return None
    return run_engine([bar for bar in bars if start_date <= bar.trading_date <= end_date],
                      evaluate, initial_cash=initial_cash, fee_rate=fee_rate,
                      slippage_rate=slippage_rate, flat_dates=flat_dates)


class StrategyApiTest(unittest.TestCase):
    def setUp(self):
        self.repository = MemoryRepository()
        bars = tuple(strategy_bars())
        self.repository.dataset = replace(self.repository.dataset, bars=bars)
        self.repository.start_run = Mock(wraps=self.repository.start_run)
        self.client = TestClient(create_app(BacktestService(self.repository)))
        self.payload = dict(dataset_id="fixture", dataset_version="1", symbol="HPG",
                            start_date=bars[0].trading_date.isoformat(), end_date=bars[-1].trading_date.isoformat(),
                            strategy_id="canslim_breakout_v0", strategy_version="1", strategy_params={},
                            initial_cash="10000", fee_rate="0.001", slippage_rate="0.002")

    def post(self, **changes):
        response = self.client.post("/api/backtests", json={**self.payload, **changes})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_parameters_reach_entry_exit_sizing_and_do_not_leak_between_runs(self):
        baseline = self.post()
        self.assertEqual(baseline["fills"][0]["quantity"], 27)
        self.assertEqual(self.post(strategy_params={"volume_multiplier": "2"})["fills"], [])
        smaller = self.post(strategy_params={"risk_per_trade_pct": "0.01"})
        self.assertEqual(smaller["fills"][0]["quantity"], 13)
        holding = self.post(strategy_params={"take_profit_pct": "0.5"})
        self.assertEqual(len(holding["fills"]), 1)
        self.assertIsNotNone(holding["open_position"])
        self.assertEqual(smaller["metadata"]["config"]["strategy_params"], {"risk_per_trade_pct": "0.01"})
        self.assertEqual(smaller["metadata"]["strategy_parameters"]["risk_per_trade_pct"], "0.01")
        self.assertEqual(smaller["metadata"]["strategy_parameters"]["sma_window"], 200)
        self.assertEqual(self.client.get("/api/backtests/" + smaller["metadata"]["run_id"]).json(), smaller)
        repeated = self.post()
        for key in ("summary", "equity_history"):
            self.assertEqual(baseline[key], repeated[key])

    def test_invalid_parameters_and_version_fail_before_repository(self):
        for params in ({"unknown": 1}, {"sma_window": True}, {"base_window": 2.5},
                       {"volume_window": 0}, {"sma_window": "5"}, {"risk_per_trade_pct": True},
                       {"stop_loss_pct": "NaN"}, {"volume_multiplier": "Infinity"}, {"stop_loss_pct": 1}):
            with self.subTest(params=params):
                response = self.client.post("/api/backtests", json={**self.payload, "strategy_params": params})
                self.assertEqual(response.status_code, 422, response.text)
                self.assertEqual(response.json()["detail"][0]["loc"][:2], ["body", "strategy_params"])
        response = self.client.post("/api/backtests", json={**self.payload, "strategy_version": "unknown"})
        self.assertEqual(response.status_code, 422)
        definition = strategies["canslim_breakout_v0"]
        for changed in (replace(definition, required_capabilities=frozenset({"short"})),
                        replace(definition, data_requirements=lambda params: {"previous_daily": {}})):
            with patch.dict(strategies, {"canslim_breakout_v0": changed}):
                self.assertEqual(self.client.post("/api/backtests", json=self.payload).status_code, 422)
        self.repository.start_run.assert_not_called()

    def test_disjoint_nested_schema_and_primary_only_strategy_use_same_api(self):
        definition = StrategyDefinition("1", FixtureParameters, fixture_runner,
                                        lambda params: {"primary": {}}, frozenset({"long", "next_open"}))
        with patch.dict(strategies, {"fixture": definition}):
            schema = self.client.get("/api/strategies/fixture?version=1").json()
            self.assertIn("entry", schema["parameter_schema"]["required"])
            self.assertIsNone(schema["data_requirements"])
            bars = tuple(replace(bar, index_close=None) for bar in strategy_bars()[:5])
            self.repository.dataset = replace(self.repository.dataset, bars=bars)
            params = {"entry": {"quantity": 3, "after_bars": 1}, "exit_after": 3}
            result = self.post(strategy_id="fixture", symbol="VN30F1M", strategy_params=params)
            self.assertEqual([fill["quantity"] for fill in result["fills"]], [3, 3])
            self.assertIsNone(result["signals"][0]["pivot"])
            self.assertEqual(result["metadata"]["strategy_parameters"], {**params, "enabled": True})
            self.assertEqual(self.post(strategy_id="fixture", strategy_params={**params, "enabled": False})["fills"], [])
            self.repository.start_run.reset_mock()
            for invalid in ({}, {**params, "sma_window": 3}, {**params, "exit_after": 1},
                            {**params, "entry": {**params["entry"], "extra": 1}}):
                response = self.client.post("/api/backtests", json={**self.payload, "strategy_id": "fixture",
                                                                  "strategy_params": invalid})
                self.assertEqual(response.status_code, 422, response.text)
            self.repository.start_run.assert_not_called()
        self.assertNotIn("fixture", [row["strategy_id"] for row in self.client.get("/api/strategies").json()])
        schema = self.client.get("/api/strategies/canslim_breakout_v0?version=1").json()
        self.assertEqual(schema["default_params"]["risk_per_trade_pct"], "0.02")
        self.assertEqual(schema["data_requirements"]["market"]["history_bars_including_t"], 200)
        self.assertEqual(self.client.get("/api/strategies/canslim_breakout_v0?version=missing").status_code, 404)

    def test_custom_windows_stop_reference_and_causality(self):
        bars = strategy_bars()
        bars[4:7] = [replace(bars[200+i], trading_date=bars[4+i].trading_date) for i in range(3)]
        self.repository.dataset = replace(self.repository.dataset, bars=tuple(bars[:7]))
        self.assertEqual(self.post()["fills"], [])
        params = dict(sma_window=3, base_window=3, volume_window=3, stop_loss_pct="0.1")
        result = self.post(strategy_params=params)
        self.assertEqual(result["fills"][0]["fill_time"], bars[5].trading_date.isoformat())
        typed = Parameters(**params)
        full = run(bars[:7], params=typed, initial_cash=10000, fee_rate="0.001", slippage_rate="0.002")
        truncated = run(bars[:6], params=typed, initial_cash=10000, fee_rate="0.001", slippage_rate="0.002")
        self.assertEqual(dict(truncated.position_details)["stop_reference"], truncated.fills[0].price * Decimal("0.9"))
        self.assertEqual(full.equity_history[:6], truncated.equity_history)
        self.assertEqual(tuple(fill for fill in full.fills if fill.fill_date <= bars[5].trading_date), truncated.fills)


if __name__ == "__main__":
    unittest.main()
