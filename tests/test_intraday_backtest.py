"""Synthetic intraday fixtures test mechanics; they are not source acceptance."""

import io
import json
import os
import tempfile
import unittest
from dataclasses import replace
from datetime import date, datetime, timedelta
from decimal import Decimal as D
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import urlsplit

from fastapi.testclient import TestClient

from backtest_hpg.api.app import create_app
from backtest_hpg.application.run_backtest import BacktestService
from backtest_hpg.domain.engine import run_fixed_signals
from backtest_hpg.domain.market import Bar, StrategyBar
from backtest_hpg.domain.strategies.canslim_breakout_v0 import run
from backtest_hpg.domain.trading import FixedSignal
from backtest_hpg.infrastructure.file_repository import DATASET_ID, FileRunRepository, prepare_dataset
from backtest_hpg.infrastructure.market_snapshot import LOCAL_TZ
from backtest_hpg.infrastructure.snapshot_bundle import capture_bundle


class IntradayTest(unittest.TestCase):
    def test_close_signal_next_open_lunch_overnight_atc_and_final_pending(self):
        stamps = [datetime(2026, 3, 18, 11, 25, tzinfo=LOCAL_TZ),
                  datetime(2026, 3, 18, 13, 0, tzinfo=LOCAL_TZ),
                  datetime(2026, 3, 19, 9, 0, tzinfo=LOCAL_TZ),
                  datetime(2026, 3, 19, 14, 45, tzinfo=LOCAL_TZ)]
        bars = [Bar(t, D(100), D(100), t + timedelta(minutes=5)) for t in stamps]
        result = run_fixed_signals(bars, {
            stamps[0]: FixedSignal("BUY", quantity=1),
            stamps[1]: FixedSignal("SELL"), stamps[3]: FixedSignal("BUY", quantity=1),
        }, initial_cash=1000, fee_rate=0)
        self.assertEqual(result.signals[0].signal_date, stamps[0] + timedelta(minutes=5))
        self.assertEqual([f.fill_date for f in result.fills], stamps[1:3])
        self.assertEqual(result.orders[-1].status, "PENDING")
        self.assertEqual(result.equity_history[-1].trading_date.hour, 14)
        self.assertEqual(result.equity_history[-1].trading_date.minute, 50)
        with self.assertRaisesRegex(ValueError, "aware"):
            run_fixed_signals([replace(bars[0], close_time=None)], {}, initial_cash=1000, fee_rate=0)

    def test_independent_market_samples_availability_and_causality(self):
        start = datetime(2026, 3, 18, 9, tzinfo=LOCAL_TZ)
        futures = [StrategyBar(start + timedelta(minutes=5*i), D(100), D(101), D(99),
                               D(100), D(1000), close_time=start + timedelta(minutes=5*(i+1)))
                   for i in range(220)]
        one_market = [Bar(start, D(100), D(100), start + timedelta(minutes=5))]
        result = run(futures, market_bars=one_market, initial_cash=1000, fee_rate=0, slippage_rate=0)
        self.assertTrue(all(row["status"] == "UNEVALUABLE" for row in result.evaluations))
        self.assertEqual(result.evaluations[-1]["market_sample_count"], 1)
        market = [Bar(b.trading_date, D(100), D(100), b.close_time) for b in futures]
        futures[202] = replace(futures[202], high=D(103), close=D(102), volume=D(1500))
        market[202] = replace(market[202], close=D(101))
        result = run(futures, market_bars=market, initial_cash=1000, fee_rate=0, slippage_rate=0)
        cutoff = futures[205].closed_at
        prefix = run(futures[:206], market_bars=market[:206], initial_cash=1000, fee_rate=0, slippage_rate=0)
        self.assertEqual(prefix.equity_history, tuple(p for p in result.equity_history if p.trading_date <= cutoff))
        self.assertEqual(prefix.evaluations, result.evaluations[:206])
        self.assertEqual(prefix.fills, tuple(f for f in result.fills if f.fill_date <= cutoff))
        self.assertEqual(run(futures, market_bars=market, initial_cash=1000, fee_rate=0, slippage_rate=0), result)
        # A future market Close cannot affect an earlier decision.
        changed = market[:206] + [replace(b, close=D(10000)) for b in market[206:]]
        altered = run(futures, market_bars=changed, initial_cash=1000, fee_rate=0, slippage_rate=0)
        self.assertEqual(altered.evaluations[:206], result.evaluations[:206])
        self.assertTrue(all(row["market_available_at"] <= row["time"] for row in result.evaluations))


class IntradayApiStorageTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.store = self.root / "store"
        times = [f"{9+i//12:02}:{(i%12)*5:02}" for i in range(30)]
        times += [f"{13+i//12:02}:{(i%12)*5:02}" for i in range(18)] + ["14:45"]
        days = [date(2026, 3, 2) + timedelta(days=i) for i in range(5)] + [date(2026, 3, 9)]
        stamps = [int(datetime.fromisoformat(f"{day.isoformat()}T{label}:00+07:00").timestamp())
                  for day in days for label in times]
        local_paths = {}
        for symbol in ("VN30F1M", "VNINDEX"):
            payload = dict(s="ok", t=stamps, o=[100]*len(stamps), h=[101]*len(stamps),
                           l=[99]*len(stamps), c=[100]*len(stamps), v=[1000]*len(stamps))
            if symbol == "VN30F1M":
                payload["h"][200], payload["c"][200], payload["v"][200] = 103, 102, 1500
                payload["o"][201], payload["h"][201] = 103, 104
                payload["h"][202], payload["c"][202] = 126, 125
                payload["o"][203], payload["h"][203] = 126, 127
            else:
                payload["h"][200], payload["c"][200] = 102, 101
            path = self.root / f"{symbol}.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            local_paths[symbol] = path
        bundle = capture_bundle(self.root / "raw", local_paths)
        manifest = json.loads(prepare_dataset(bundle, self.store).read_bytes())
        self.assertIsNone(manifest["datasets"][0]["extracted_at"])
        self.policy_path = self.root / "policy.json"
        self.policy = dict(schema_version=1, timezone="Asia/Ho_Chi_Minh",
                           rollover_action="hold",
                           trading_dates=[day.isoformat() for day in days],
                           sessions={s: dict(required_times=times, optional_times=[]) for s in local_paths},
                           rollover=[dict(start=days[0].isoformat(), end=days[-1].isoformat(), contract="SYNTHETIC-2603")])
        self.policy_path.write_text(json.dumps(self.policy), encoding="utf-8")
        self.repository = FileRunRepository(self.store, self.policy_path)
        self.client = TestClient(create_app(BacktestService(self.repository)))
        self.payload = dict(dataset_id=DATASET_ID, dataset_version=manifest["dataset_version"], symbol="VN30F1M",
                            start_date="2026-03-06", end_date="2026-03-06", strategy_id="canslim_breakout_v0",
                            initial_cash="10000000", fee_rate="0.001", slippage_rate="0.002")

    def test_api_complete_result_reload_restart_chart_and_corrupt_result(self):
        created = self.client.post("/api/backtests", json=self.payload)
        self.assertEqual(created.status_code, 201, created.text)
        result = created.json()
        self.assertEqual(len(result["fills"]), 2)
        self.assertEqual(len(result["trades"]), 1)
        self.assertEqual(result["evaluation_status"]["status"], "PARTIALLY_EVALUABLE")
        self.assertEqual(result["evaluation_status"]["unevaluable_bars"], 3)
        self.assertTrue(all(f["fill_time"].endswith("+07:00") for f in result["fills"]))
        run_id = result["metadata"]["run_id"]
        restarted = TestClient(create_app(BacktestService(FileRunRepository(self.store, self.policy_path))))
        self.assertEqual(restarted.get(f"/api/backtests/{run_id}").json(), result)
        self.assertEqual(restarted.get("/api/backtests").json(), [result])
        chart = restarted.get(f"/api/backtests/{run_id}/chart").json()
        self.assertEqual(len(chart["bars"]), 49)
        repeat = restarted.post("/api/backtests", json=self.payload).json()
        for group in ("summary", "evaluation_status", "evaluations", "equity_history"):
            self.assertEqual(repeat[group], result[group])
        path = self.store / "runs" / f"{run_id}.json"
        stored = json.loads(path.read_bytes())
        stored["result"]["summary"]["final_equity"] = "999"
        path.write_text(json.dumps(stored), encoding="utf-8")
        self.assertEqual(restarted.get(f"/api/backtests/{run_id}").status_code, 409)
        self.assertNotIn(str(self.root), restarted.get(f"/api/backtests/{run_id}").text)

    def test_missing_policy_rollover_calendar_bar_and_broken_dataset_fail(self):
        self.policy_path.unlink()
        response = self.client.post("/api/backtests", json=self.payload)
        self.assertEqual(response.status_code, 422)
        self.assertIn("STATIC_SESSION_ROLLOVER_POLICY_REQUIRED", response.text)
        for key, value, code in [("rollover", [], "ROLLOVER_MAP_REQUIRED"),
                                 ("rollover", [dict(start="2026-03-02", end="2026-03-05", contract="SYNTHETIC")], "ROLLOVER_MAP_MISSING")]:
            self.policy_path.write_text(json.dumps({**self.policy, key: value}), encoding="utf-8")
            response = self.client.post("/api/backtests", json=self.payload)
            self.assertEqual(response.status_code, 422)
            self.assertIn(code, response.text)
        changed = json.loads(json.dumps(self.policy))
        changed["sessions"]["VN30F1M"]["required_times"].append("10:01")
        self.policy_path.write_text(json.dumps(changed), encoding="utf-8")
        self.assertIn("MISSING_EXPECTED_BAR", self.client.post("/api/backtests", json=self.payload).text)
        self.policy_path.write_text(json.dumps(self.policy), encoding="utf-8")
        parquet = next((self.store / "datasets").glob("*.parquet"))
        parquet.write_bytes(b"corrupt")
        response = self.client.post("/api/backtests", json=self.payload)
        self.assertEqual(response.status_code, 422)
        self.assertIn("DATASET_HASH_MISMATCH", response.text)
        self.assertEqual(self.client.get("/api/backtests").json(), [])

    def test_interrupted_publish_does_not_expose_success(self):
        real_replace = os.replace

        def interrupted_success(source, destination):
            if json.loads(Path(source).read_bytes()).get("status") == "succeeded":
                raise OSError("disk failure during result publication")
            return real_replace(source, destination)

        with patch("backtest_hpg.infrastructure.file_repository.os.replace", side_effect=interrupted_success):
            response = self.client.post("/api/backtests", json=self.payload)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(self.client.get("/api/backtests").json(), [])
        self.assertFalse(list((self.store / "runs").glob("*.tmp")))

    def test_all_notebook_code_cells_against_synthetic_api(self):
        notebook_path = Path(__file__).parents[1] / "notebooks" / "backtest-results.ipynb"
        notebook = json.loads(notebook_path.read_text(encoding="utf-8"))
        manifest = next((self.store / "datasets").glob("dataset-*.json"))

        def open_api(request, timeout=120):
            url = request if isinstance(request, str) else request.full_url
            route = urlsplit(url).path
            response = (self.client.get(route) if isinstance(request, str)
                        else self.client.request(request.get_method(), route, content=request.data,
                                                 headers={"Content-Type": "application/json"}))
            body = io.BytesIO(json.dumps(response.json()).encode())
            if response.status_code >= 400:
                raise HTTPError(url, response.status_code, "API error", {}, body)
            return body

        namespace = {}
        settings = {"BACKTEST_DATASET_MANIFEST": str(manifest), "BACKTEST_REPORT_START": "2026-03-06",
                    "BACKTEST_REPORT_END": "2026-03-06"}
        with patch.dict(os.environ, settings), patch("urllib.request.urlopen", side_effect=open_api), \
                patch("IPython.display.display") as display:
            for index, cell in enumerate(notebook["cells"]):
                if cell["cell_type"] == "code":
                    exec(compile("".join(cell["source"]), f"notebook-cell-{index}", "exec"), namespace)
        self.assertEqual(namespace["result"], namespace["reloaded_result"])
        self.assertEqual(len(namespace["result"]["fills"]), 2)
        self.assertGreater(display.call_count, 10)

    def test_reference_rollover_keeps_position_without_forced_sell(self):
        self.policy["rollover"] = [
            dict(start="2026-03-02", end="2026-03-06", contract="SYNTHETIC-OLD"),
            dict(start="2026-03-07", end="2026-03-09", contract="SYNTHETIC-NEW"),
        ]
        self.policy_path.write_text(json.dumps(self.policy), encoding="utf-8")
        # Remove the target trigger so the position spans the reference roll.
        raw_path = self.root / "VN30F1M.json"
        payload = json.loads(raw_path.read_bytes())
        payload["c"][202] = 100
        raw_path.write_text(json.dumps(payload), encoding="utf-8")
        bundle = capture_bundle(self.root / "raw", {s: self.root / f"{s}.json" for s in ("VN30F1M", "VNINDEX")})
        manifest = json.loads(prepare_dataset(bundle, self.store).read_bytes())
        response = self.client.post("/api/backtests", json={**self.payload,
            "end_date": "2026-03-09", "dataset_version": manifest["dataset_version"]})
        self.assertEqual(response.status_code, 201, response.text)
        result = response.json()
        self.assertEqual(len(result["fills"]), 1)
        self.assertEqual(result["fills"][0]["side"], "BUY")
        self.assertIsNotNone(result["open_position"])


if __name__ == "__main__":
    unittest.main()
