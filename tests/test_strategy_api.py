"""The strategy catalog is optional metadata, not a run selector."""

import unittest

from fastapi.testclient import TestClient

from backtest_hpg.api.app import create_app
from backtest_hpg.application.run_backtest import BacktestService
from test_application_api import MemoryRepository


class StrategyCatalogTest(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(create_app(BacktestService(MemoryRepository())))

    def test_catalog_can_be_read_but_old_selector_payload_is_rejected(self):
        catalog = self.client.get('/api/strategies')
        self.assertEqual(catalog.status_code, 200)
        self.assertIn('canslim_breakout_v0', [item['strategy_id'] for item in catalog.json()])
        schema = self.client.get('/api/strategies/canslim_breakout_v0?version=1')
        self.assertEqual(schema.status_code, 200)
        response = self.client.post('/api/backtests', json={
            'dataset_id': 'fixture', 'dataset_version': '1',
            'strategy_id': 'canslim_breakout_v0',
        })
        self.assertEqual(response.status_code, 422)
        locations = [item['loc'] for item in response.json()['detail']]
        self.assertIn(['body', 'strategy_id'], locations)


if __name__ == '__main__':
    unittest.main()
