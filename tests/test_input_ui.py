"""Input snapshots are fixed UI resources; the backtest request stays unchanged."""
import json
from pathlib import Path
import unittest
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fastapi.testclient import TestClient

from backtesting_api.api.app import create_app
from backtesting_api.api.inline_schemas import InlineRunRequest


class InputUiTests(unittest.TestCase):
    def test_preset_files_are_exact_and_not_part_of_the_backtest_schema(self):
        paths = {
            'trade_data': 'trade/vn30f1m-5m-20260316-20260915.json',
            'market_data': 'market/VNINDEX_5&from=1772323200&to=1789516800.json',
        }
        example = Path(__file__).resolve().parents[1] / 'src/backtesting_api/web/canslim-v1-example.json'
        request = json.loads(example.read_text(encoding='utf-8'))
        with TemporaryDirectory(dir='.agents') as directory:
            data = Path(directory)
            # Only the data directory is redirected; packaged UI assets stay real.
            with patch('backtesting_api.api.app.Path', side_effect=lambda value: data if value == 'data' else Path(value)):
                client = TestClient(create_app())
                for source, filename in paths.items():
                    self.assertEqual(client.get(f'/ui-data/{source}').status_code, 404)
                    bars = request[source]['bars']
                    parsed = {'s': 'ok', **{key: [bar[field] for bar in bars] for key, field in zip(
                        ('t', 'o', 'h', 'l', 'c', 'v'), ('time', 'open', 'high', 'low', 'close', 'volume'))}}
                    file = data / filename
                    file.parent.mkdir(parents=True, exist_ok=True)
                    file.write_text(json.dumps(parsed), encoding='utf-8')
                    response = client.get(f'/ui-data/{source}')
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.content, file.read_bytes())
                    # Exercise the existing raw-data normalizer, not a new input contract.
                    request[source]['bars'] = parsed
                    validated = InlineRunRequest.model_validate(request)
                    self.assertEqual(len(getattr(validated, source).bars), len(parsed['t']))
                self.assertEqual(client.get('/ui-data/anything').status_code, 404)
                self.assertFalse(any(path.startswith('/ui-data') for path in client.get('/openapi.json').json()['paths']))

    def test_form_resources_are_packaged_and_do_not_contain_a_full_payload_editor(self):
        client = TestClient(create_app(preview=True))
        page = client.get('/').text
        self.assertNotIn('id="payload-json"', page)
        self.assertIn('id="load-example"', page)
        self.assertIn('id="trade_data-preset"', page)
        self.assertIn('id="market_data-file"', page)
        for filename in ['backtest-input.mjs', 'backtest-input.css']:
            self.assertEqual(client.get('/static/' + filename).status_code, 200)
        self.assertIn('text/javascript', client.get('/static/backtest-input.mjs').headers['content-type'])


if __name__ == '__main__':
    unittest.main()
