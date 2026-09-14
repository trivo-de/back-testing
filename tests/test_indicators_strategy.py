from decimal import Decimal
import unittest

from backtest_hpg.domain.indicators import calculate_snapshot
from backtest_hpg.domain.strategies.canslim_breakout_v0 import evaluate_entry, evaluate_exit


D = Decimal


class IndicatorsStrategyTest(unittest.TestCase):
    def setUp(self):
        self.highs = [D(100)] * 201
        self.lows = [D(80)] * 201
        self.volumes = [D(1000)] * 200 + [D(1500)]
        self.index = [D(100)] * 200 + [D(101)]

    def test_entry_boundaries_and_no_future_data(self):
        snapshot = calculate_snapshot(self.highs, self.lows, self.volumes, self.index, 200)
        self.assertIsNotNone(snapshot)
        self.assertEqual(evaluate_entry(105, 1500, 101, snapshot).side, "BUY")
        self.assertIsNone(evaluate_entry(100, 1500, 101, snapshot).side)
        self.assertIsNone(evaluate_entry(105.01, 1500, 101, snapshot).side)
        self.assertIsNone(evaluate_entry(101, 1499, 101, snapshot).side)
        with_future = calculate_snapshot(self.highs + [D(999)], self.lows + [D(1)], self.volumes + [D(999999)], self.index + [D(999)], 200)
        self.assertEqual(snapshot, with_future)

    def test_market_equality_warm_up_and_exit_boundaries(self):
        snapshot = calculate_snapshot(self.highs, self.lows, self.volumes, [D(100)] * 201, 200)
        self.assertIsNone(evaluate_entry(101, 1500, 100, snapshot).side)
        self.assertEqual(evaluate_entry(101, 1500, 101, None).reason, "WARM_UP")
        self.assertIsNone(calculate_snapshot(self.highs[:199], self.lows[:199], self.volumes[:199], self.index[:199], 198))
        depth_boundary = calculate_snapshot(self.highs, [D(65)] * 201, self.volumes, self.index, 200)
        too_deep = calculate_snapshot(self.highs, [D("64.99")] * 201, self.volumes, self.index, 200)
        self.assertEqual(evaluate_entry(101, 1500, 101, depth_boundary).side, "BUY")
        self.assertIsNone(evaluate_entry(101, 1500, 101, too_deep).side)
        self.assertEqual(evaluate_exit(93, 100, 100).reason, "STOP_LOSS")
        self.assertEqual(evaluate_exit(120, 100, 100).reason, "TAKE_PROFIT")
        self.assertEqual(evaluate_exit(119.99, 100, 100).reason, "HOLD")


if __name__ == "__main__":
    unittest.main()
