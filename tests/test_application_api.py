import unittest
from unittest.mock import Mock
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from backtesting_api.api.app import create_app
from backtesting_api.application.run_backtest import BacktestService


class MemoryRepository:
    def __init__(self):
        self.runs = {}
        self.failed = set()

    def start_inline(self, payload, policy, data):
        run_id = uuid4()
        return run_id, "mock-input-hash", "mock-policy-hash"

    def get_input(self, run_id: UUID):
        return None

    def get_chart(self, run_id: UUID):
        return None

    def complete_run(self, run_id: UUID, result, response: dict):
        self.runs[run_id] = response

    def fail_run(self, run_id: UUID, error: Exception):
        self.failed.add(run_id)

    def get_run(self, run_id: UUID):
        return self.runs.get(run_id)

    def list_runs(self):
        return list(self.runs.values())



class ApplicationApiTest(unittest.TestCase):
    def setUp(self):
        self.repository = MemoryRepository()
        self.client = TestClient(create_app(BacktestService(self.repository)))
        self.payload = {
            "dataset_id": "fixture",
            "dataset_version": "1",
            "symbol": "HPG",
            "start_date": "2020-01-01",
            "end_date": "2020-12-31",
            "strategy_id": "canslim_breakout_v0",
            "initial_cash": "10000000",
            "fee_rate": "0.001",
            "slippage_rate": "0.002",
        }

    def test_legacy_result_can_still_be_listed_and_read(self):
        run_id = uuid4()
        result = {"metadata": {"run_id": str(run_id)}, "schema_version": 1}
        self.repository.runs[run_id] = result
        self.assertEqual(self.client.get(f"/api/backtests/{run_id}").json(), result)
        self.assertEqual(self.client.get("/api/backtests").json(), [result])

    def test_old_run_payload_and_missing_result_are_explicit(self):
        old = self.client.post("/api/backtests", json=self.payload)
        missing = self.client.get(f"/api/backtests/{uuid4()}")
        self.assertEqual((old.status_code, missing.status_code), (422, 404))
        locations = [item['loc'] for item in old.json()['detail']]
        self.assertIn(['body', 'dataset_version'], locations)
        self.assertIn(['body', 'strategy_id'], locations)

    def test_minimal_ui_is_served(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("<title>Backtest</title>", response.text)

    def test_chart_endpoint_uses_requested_run_and_reports_errors(self):
        run_id = uuid4()
        payload = {"metadata": {"run_id": str(run_id)}, "bars": []}
        self.repository.get_chart = Mock(return_value=payload)
        self.assertEqual(self.client.get(f"/api/backtests/{run_id}/chart").json(), payload)
        self.repository.get_chart.assert_called_once_with(run_id)
        self.repository.get_chart.return_value = None
        self.assertEqual(self.client.get(f"/api/backtests/{run_id}/chart").status_code, 404)
        self.repository.get_chart.side_effect = ValueError("private details")
        response = self.client.get(f"/api/backtests/{run_id}/chart")
        self.assertEqual(response.status_code, 409)
        self.assertNotIn("private", response.text)
        self.repository.get_chart.side_effect = RuntimeError("secret storage path")
        response = self.client.get(f"/api/backtests/{run_id}/chart")
        self.assertEqual(response.status_code, 500)
        self.assertNotIn("secret", response.text)
        self.assertEqual(self.client.get("/api/backtests/not-a-uuid/chart").status_code, 422)


if __name__ == "__main__":
    unittest.main()
