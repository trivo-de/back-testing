import unittest

from backtesting_api.config import API, BACKTEST


class ConfigTest(unittest.TestCase):
    def test_static_settings_are_grouped(self):
        self.assertEqual(API.home_path, "/")
        self.assertEqual(API.backtests_path, "/api/backtests")
        self.assertEqual(BACKTEST.engine_version, "0.2.0")



if __name__ == "__main__":
    unittest.main()
