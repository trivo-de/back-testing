"""The UI exposes strategy intent and automatic sources, never market-data uploads."""
from pathlib import Path
import unittest
from fastapi.testclient import TestClient
from backtesting_api.api.app import create_app


class InputUiTests(unittest.TestCase):
    """Check packaged controls against the approved public request boundary."""
    def test_form_only_edits_strategy_and_optional_report_dates(self):
        """Remove all upload/manual-source/accounting switches from the visible form."""
        client = TestClient(create_app(preview=True))
        page = client.get('/').text
        for identifier in ['payload-file', 'trade_data-file', 'market_data-file', 'trade_data-preset',
                           'market_data-preset', 'auto-fetch-data', 'input-accounting', 'sizing-fields']:
            self.assertNotIn('id="' + identifier + '"', page)
        self.assertNotIn('type="file"', page)
        for identifier in ['strategy-json', 'apply-strategy', 'order-fields', 'risk-fields',
                           'parameter-panel', 'parameter-search', 'parameter-detail', 'open-parameters', 'data-coverage']:
            self.assertIn('id="' + identifier + '"', page)
        self.assertIn('<dialog id="parameter-panel" aria-labelledby="parameter-title">', page)
        for group in ['parameters', 'aliases', 'operators']:
            self.assertIn('id="parameter-group-' + group + '"', page)
        self.assertIn('6 nghĩa là 6%', page)
        self.assertIn('Không giữ vị thế qua ngày', page)
        self.assertIn('hệ thống tự đóng hết lượng còn giữ', page)
        for identifier in ['fills', 'trades', 'position', 'audit', 'orders', 'equity']:
            self.assertIn(f'id="toggle-{identifier}" aria-controls="{identifier}" aria-expanded="true"', page)
        for name in ['unit', 'min_total_pnl', 'max_total_pnl', 'sort_by', 'sort_order']:
            self.assertIn('name="' + name + '"', page)

    def test_editor_chart_and_existing_theme_assets_are_packaged(self):
        """Keep the existing layout/theme while serving the new config-only editor."""
        client = TestClient(create_app(preview=True))
        for filename in ['backtest-input.mjs', 'backtest-input.css', 'backtest-data.mjs', 'backtest-chart.mjs', 'language.mjs']:
            self.assertEqual(client.get('/static/' + filename).status_code, 200)
        self.assertIn('text/javascript', client.get('/static/backtest-input.mjs').headers['content-type'])
        source = (Path(__file__).parents[1] / 'src/backtesting_api/web/backtest-input.mjs').read_text(encoding='utf-8')
        self.assertNotIn('/ui-data/', source)
        self.assertNotIn('FileReader', source)


if __name__ == '__main__':
    unittest.main()
