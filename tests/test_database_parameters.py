"""Kiểm tra JSON truyền vào PostgreSQL và đọc lại, không kết nối cơ sở dữ liệu thật."""

from datetime import date
from decimal import Decimal
import unittest
from unittest.mock import MagicMock, patch

from backtest_hpg.application.contracts import RunConfig
from backtest_hpg.infrastructure.database import PostgresRunRepository


class DatabaseParametersTest(unittest.TestCase):
    def test_requested_and_resolved_parameters_survive_sql_mapping(self):
        config = RunConfig("fixture", "1", "HPG", date(2025, 1, 1), date(2025, 1, 1),
                           "canslim_breakout_v0", Decimal(10000), Decimal("0.001"), Decimal(0),
                           strategy_version="1", strategy_params={"volume_multiplier": "2.0000001"})
        connection = MagicMock()
        connection.__enter__.return_value = connection
        cursor = connection.execute.return_value
        version = dict(id=1, dataset_name="fixture", version="1", content_hash="hash")
        row = dict(trading_date=config.start_date, open=100, high=101, low=99, close=100,
                   volume=1000, index_close=100)
        cursor.fetchone.return_value = version
        cursor.fetchall.return_value = [row]
        repository = PostgresRunRepository("unused")
        with patch("backtest_hpg.infrastructure.database.psycopg.connect", return_value=connection):
            run_id, _ = repository.start_run(config)
            insert = connection.execute.call_args_list[1].args[1]
            saved_config, saved_params = insert[-2].obj, insert[-1].obj
            self.assertEqual(saved_config["strategy_params"], config.strategy_params)
            self.assertEqual(saved_params["volume_multiplier"], "2.0000001")
            self.assertEqual(saved_params["sma_window"], 200)
            header = dict(dataset_name="fixture", dataset_version="1", content_hash="hash",
                          engine_version="0.2.0", strategy_id=config.strategy_id,
                          start_date=config.start_date, end_date=config.end_date,
                          initial_cash=config.initial_cash, config=saved_config, strategy_parameters=saved_params)
            cursor.fetchone.side_effect = [header, None]
            cursor.fetchall.side_effect = [[], [], [], [], [dict(trading_date=config.start_date,
                cash=Decimal(10000), quantity=0, market_value=Decimal(0), equity=Decimal(10000), unrealized_pnl=Decimal(0))]]
            response = repository.get_run(run_id)
            self.assertEqual(response["metadata"]["config"]["strategy_params"], config.strategy_params)
            self.assertEqual(response["metadata"]["config"]["strategy_version"], "1")
            self.assertEqual(response["metadata"]["strategy_parameters"], saved_params)


if __name__ == "__main__":
    unittest.main()
