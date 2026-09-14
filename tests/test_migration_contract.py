from pathlib import Path
import unittest


class MigrationContractTest(unittest.TestCase):
    def test_initial_migration_contains_documented_tables_and_transaction(self):
        sql = Path("migrations/001_initial.sql").read_text(encoding="utf-8").lower()
        tables = (
            "schema_migrations", "datasets", "dataset_versions", "market_bars", "backtest_runs",
            "signals", "orders", "fills", "trades", "equity_snapshots", "open_positions",
        )
        self.assertTrue(sql.startswith("begin;"))
        self.assertTrue(sql.rstrip().endswith("commit;"))
        for table in tables:
            self.assertIn(f"create table {table}", sql)


if __name__ == "__main__":
    unittest.main()
