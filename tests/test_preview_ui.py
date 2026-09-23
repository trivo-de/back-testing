"""Preview styling is opt-in; API and old UI retain their contracts."""
import unittest

from fastapi.testclient import TestClient

from backtest_hpg.api.app import create_app
from backtest_hpg.application.run_backtest import BacktestService
from test_application_api import MemoryRepository


class PreviewUiTests(unittest.TestCase):
    def test_preview_isolated_from_legacy_and_reuses_api(self):
        service = BacktestService(MemoryRepository())
        legacy = TestClient(create_app(service))
        preview = TestClient(create_app(service, preview=True))
        for route in ('/', '/market-chart'):
            self.assertNotIn('preview.css', legacy.get(route).text)
            page = preview.get(route)
            self.assertEqual(page.status_code, 200)
            self.assertIn('preview.css', page.text)
            self.assertNotIn('Runway · UI preview', page.text)
        original_theme = legacy.get('/static/theme.mjs').text
        themed = preview.get('/static/theme.mjs?v=20260918')
        self.assertIn('localStorage', original_theme)
        self.assertIn("'backtest-preview-theme'", themed.text)
        self.assertNotIn("'backtest-theme'", themed.text)
        self.assertIn('text/javascript', themed.headers['content-type'])
        self.assertIn('#f9a600', preview.get('/static/preview.css').text)
        self.assertEqual(preview.get('/api/backtests').json(), legacy.get('/api/backtests').json())
        self.assertEqual(preview.post('/api/backtests', json={}).status_code, 422)
        self.assertEqual(legacy.get('/static/theme.mjs').text, original_theme)


if __name__ == '__main__':
    unittest.main()
