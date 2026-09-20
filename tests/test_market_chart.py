import copy
import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from backtest_hpg.api.app import create_app
from backtest_hpg.infrastructure.market_snapshot import validate_bars, read_snapshot


class MarketChartTest(unittest.TestCase):
    def setUp(self):
        self.payload = dict(s="ok", t=[1773626400, 1773626700],
                            o=[100, 102], h=[103, 104], l=[99, 101], c=[102, 103], v=[0, 20])

    def test_mapping_preserves_timestamp_price_zero_volume_and_rejects_bad_data(self):
        bars = validate_bars(self.payload)
        self.assertEqual(bars[0], dict(time=1773626400, open=100, high=103, low=99, close=102, volume=0))
        for key, value in [("t", [1, 1]), ("t", [2, 1]), ("t", [True, 2]),
                           ("v", [0]), ("v", [0, -1]), ("h", [99, 104]),
                           ("c", [float("nan"), 103]), ("o", [None, 102])]:
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                validate_bars({**self.payload, key: value})

    def test_decimal_validation_does_not_round_ohlc_into_validity(self):
        payload = dict(s="ok", t=[1], o=[Decimal("1")], h=[Decimal("1")],
                       l=[Decimal("1")], c=[Decimal("1.00000000000000000001")], v=[0])
        with self.assertRaisesRegex(ValueError, "Invalid OHLCV"):
            validate_bars(payload)

    def test_pages_assets_filters_and_missing_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            client = TestClient(create_app(snapshot_path=Path(directory) / "missing.json"))
            self.assertEqual(client.get("/").status_code, 200)
            for asset in ["market-chart.mjs", "market-data.mjs", "market-chart.css",
                          "vendor/lightweight-charts.standalone.production.mjs", "vendor/LICENSE", "vendor/NOTICE"]:
                response = client.get(f"/static/{asset}")
                self.assertEqual(response.status_code, 200)
                if asset.endswith('.mjs'):
                    self.assertTrue(response.headers["content-type"].startswith("text/javascript"))
            self.assertEqual(client.get("/api/market-chart").status_code, 503)
            self.assertEqual(client.get("/api/market-chart?start=2026-09-15&end=2026-03-16").status_code, 422)
            self.assertEqual(client.get("/api/market-chart?start=bad").status_code, 422)
            snapshot = {"metadata": {}, "bars": validate_bars(self.payload)}
            with patch("backtest_hpg.api.market_routes.read_snapshot", side_effect=lambda _: copy.deepcopy(snapshot)):
                self.assertEqual(len(client.get("/api/market-chart?start=2026-03-16&end=2026-03-16").json()["bars"]), 2)
                self.assertEqual(client.get("/api/market-chart?start=2026-03-17").json()["bars"], [])

    def test_corrupt_snapshot_is_rejected_without_path_disclosure(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "private.json"
            path.write_text(json.dumps(self.payload), encoding="utf-8")
            with self.assertRaises(ValueError):
                read_snapshot(path)
            response = TestClient(create_app(snapshot_path=path)).get("/api/market-chart")
            self.assertEqual(response.status_code, 409)
            self.assertNotIn(directory, response.text)


if __name__ == "__main__":
    unittest.main()
