import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from backtest_hpg.config import API, BACKTEST, CANSLIM_BREAKOUT_V0, DATABASE, RESULT, get_database_url


class ConfigTest(unittest.TestCase):
    def test_static_settings_are_grouped(self):
        self.assertEqual(DATABASE.url_environment_variable, "DATABASE_URL")
        self.assertEqual(API.home_path, "/")
        self.assertEqual(API.backtests_path, "/api/backtests")
        self.assertEqual(BACKTEST.supported_symbol, "HPG")
        self.assertEqual(str(RESULT.quantum), "0.000001")
        self.assertEqual(
            CANSLIM_BREAKOUT_V0.parameters()["RISK_PER_TRADE_PCT"],
            "0.02",
        )

    def test_environment_wins_and_dotenv_is_the_fallback(self):
        with TemporaryDirectory() as directory:
            env_file = Path(directory) / ".env"
            env_file.write_text('DATABASE_URL="postgresql://from-file"\n', encoding="utf-8")
            with patch.dict(os.environ, {}, clear=True):
                self.assertEqual(get_database_url(env_file), "postgresql://from-file")
            with patch.dict(os.environ, {"DATABASE_URL": "postgresql://from-environment"}, clear=True):
                self.assertEqual(get_database_url(env_file), "postgresql://from-environment")


if __name__ == "__main__":
    unittest.main()
