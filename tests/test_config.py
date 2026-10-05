import unittest

from backtest_hpg.config import API, BACKTEST, CANSLIM_BREAKOUT_V0, RESULT


class ConfigTest(unittest.TestCase):
    def test_static_settings_are_grouped(self):
        self.assertEqual(API.home_path, "/")
        self.assertEqual(API.backtests_path, "/api/backtests")
        self.assertEqual(BACKTEST.supported_symbol, "HPG")
        self.assertEqual(str(RESULT.quantum), "0.000001")
        self.assertEqual(
            CANSLIM_BREAKOUT_V0.parameters()["RISK_PER_TRADE_PCT"],
            "0.02",
        )


if __name__ == "__main__":
    unittest.main()
