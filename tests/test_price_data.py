"""Check the public auto-fetch contract with fixed clocks and provider responses."""
from datetime import datetime, time
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import URLError
from urllib.parse import parse_qs, urlparse
from uuid import UUID
from zoneinfo import ZoneInfo
from fastapi.testclient import TestClient
from backtesting_api.api.app import create_app
from backtesting_api.application.run_backtest import BacktestService
from backtesting_api.infrastructure.auto_fetch_data import AutoDataFetcher
from backtesting_api.infrastructure.file_repository import FileRunRepository


ZONE = ZoneInfo('Asia/Ho_Chi_Minh')


class PriceDataTest(unittest.TestCase):
    """Exercise real preparation with no network calls or candle-bearing requests."""
    def setUp(self):
        """Bind a controlled provider to the real fetcher, service and API."""
        temporary = tempfile.TemporaryDirectory(dir='.agents')
        self.addCleanup(temporary.cleanup)
        self.repository = FileRunRepository(Path(temporary.name))
        self.now = datetime(2026, 10, 8, 10, 12, tzinfo=ZONE)
        self.calls, self.error, self.invalid = [], False, False
        fetcher = AutoDataFetcher(clock=lambda: self.now, opener=self.source)
        self.service = BacktestService(self.repository, data_fetcher=fetcher)
        self.client = TestClient(create_app(self.service))
        self.payload = {'symbol': 'VN30F1M', 'entry': {'long': {'gt': [0, 1]}},
                        'exit': {'long': {'gt': [1, 0]}}}

    def source(self, request, timeout):
        """Return requested fixture rows, including an unfinished source candle."""
        self.calls.append(request.full_url)
        if self.error:
            raise URLError('controlled outage')
        params = parse_qs(urlparse(request.full_url).query)
        first, last = int(params['from'][0]), int(params['to'][0])
        policy = json.loads(Path('docs/data/vn30f1m/runtime-policy-v1.json').read_bytes())
        stamps = [int(datetime.combine(datetime(2026, 10, day).date(), time.fromisoformat(label), ZONE).timestamp())
                  for day in (7, 8) for label in policy['sessions']['trade_data']['required_times']]
        stamps = [stamp for stamp in stamps if first <= stamp <= last]
        raw = {'s': 'ok', 't': stamps, 'o': [100] * len(stamps), 'h': [99 if self.invalid else 101] * len(stamps),
               'l': [99] * len(stamps), 'c': [100] * len(stamps), 'v': [100] * len(stamps)}
        return io.BytesIO(json.dumps(raw).encode())

    def test_latest_window_closed_candles_and_actual_coverage(self):
        """The URL window and available source coverage retain distinct meanings."""
        checked = self.client.post('/api/backtests/validate', json=self.payload)
        self.assertEqual(checked.status_code, 200, checked.text)
        value = checked.json()
        self.assertEqual(value['payload'], self.payload)
        metadata = value['data_metadata']
        self.assertEqual(datetime.fromtimestamp(metadata['auto_fetch']['from'], ZONE),
                         datetime(2026, 4, 8, 10, 12, tzinfo=ZONE))
        self.assertEqual(metadata['available_range']['start'], '2026-10-07')
        self.assertEqual(metadata['available_range']['last_close'], '2026-10-08T10:10:00+07:00')
        self.assertIn('PARTIAL_REPORT_COVERAGE', value['warnings'])
        self.assertFalse((self.repository.store / 'runs').exists())
        created = self.client.post('/api/backtests', json=self.payload)
        self.assertEqual(created.status_code, 201, created.text)
        self.assertEqual(created.json()['summary']['total_pnl'], '0')
        self.assertIsNone(created.json()['summary']['win_rate'])

    def test_report_history_and_gap_observation_cutoff(self):
        """Fetch the indicator seed while excluding future session slots from missing data."""
        value = {**self.payload, 'from': '2026-10-08', 'to': '2026-10-08',
                 'entry': {'long': {'left': 'price', 'op': 'above', 'right': 'sma20'}}}
        response = self.client.post('/api/backtests/validate', json=value)
        self.assertEqual(response.status_code, 200, response.text)
        metadata = response.json()['data_metadata']
        self.assertEqual(metadata['auto_fetch']['warmup_bars_requested'], 20)
        self.assertLess(metadata['auto_fetch']['from'], int(datetime(2026, 10, 8, tzinfo=ZONE).timestamp()))
        self.assertFalse(any(datetime.fromisoformat(stamp) >= self.now
                             for stamps in metadata['data_gaps'].values() for stamp in stamps))
        self.assertEqual(len(self.calls), 2)

    def test_legacy_fields_bad_dates_and_manual_source_endpoint_are_rejected(self):
        """Reject every retired input mode before calling a provider or storing a run."""
        fields = ('trade_data', 'market_data', 'bars', 'raw', 'file', 'auto_fetch_data', 'accounting',
                  'initial_cash', 'execution', 'strategy', 'contract_map', 'price_limits', 'auctions')
        for endpoint in ('/api/backtests', '/api/backtests/validate'):
            for field in fields:
                with self.subTest(endpoint=endpoint, field=field):
                    response = self.client.post(endpoint, json={**self.payload, field: {}})
                    self.assertEqual(response.status_code, 422)
                    self.assertIn('LEGACY_OR_DATA_FIELD_NOT_ALLOWED', response.text)
            for dates in ({'from': '2026-10-01'}, {'to': '2026-10-01'},
                          {'from': '2026-10-02', 'to': '2026-10-01'},
                          {'from': '2026-02-30', 'to': '2026-03-01'},
                          {'from': '2099-01-01', 'to': '2099-01-02'}):
                self.assertEqual(self.client.post(endpoint, json={**self.payload, **dates}).status_code, 422)
        self.assertFalse(self.calls)
        self.assertEqual(self.client.get('/ui-data/trade_data').status_code, 404)

    def test_provider_failure_has_no_file_fallback_or_hidden_retry(self):
        """Both operations surface upstream errors without publishing success."""
        self.error = True
        for endpoint in ('/api/backtests', '/api/backtests/validate'):
            response = self.client.post(endpoint, json=self.payload)
            self.assertEqual(response.status_code, 503)
            self.assertIn('AUTO_FETCH_NETWORK_ERROR', response.text)
        self.assertEqual(len(self.calls), 2)
        self.assertFalse((self.repository.store / 'runs').exists())
        self.error, self.invalid = False, True
        invalid = self.client.post('/api/backtests', json=self.payload)
        self.assertEqual(invalid.status_code, 422)
        self.assertIn('AUTO_FETCH_INVALID_SOURCE', invalid.text)

    def test_replay_uses_only_pinned_sources_calendar_and_defaults(self):
        """A restarted service can reproduce events without a fetcher or compilation."""
        response = self.client.post('/api/backtests', json=self.payload)
        self.assertEqual(response.status_code, 201, response.text)
        restarted = BacktestService(FileRunRepository(self.repository.store))
        with patch.object(restarted, 'prepare_price', side_effect=AssertionError('provider/defaults reused')):
            replay = restarted.replay_price(UUID(response.json()['metadata']['run_id']))
        self.assertEqual(replay['summary'], response.json()['summary'])
        self.assertEqual(replay['pnl_history'], response.json()['pnl_history'])

    def test_missing_pinned_risk_source_emits_no_orphan_signal_or_order(self):
        """Missing entry protection data leaves evaluation unevaluable and intent unpublished."""
        from test_price_strategy import request, run, bars
        value = request(exit={}, risk={'stop_price': {'sub': [{'ref': 'market.price'}, 6]}})
        result = run(value, bars([('100', '101', '99', '100')] * 3))
        for collection in ('signals', 'orders', 'fills'):
            self.assertEqual(result[collection], [])
        self.assertTrue(all(row['status'] == 'UNEVALUABLE' for row in result['evaluations']))

    def test_known_market_gap_cannot_supply_stale_position_exit_data(self):
        """A source slot known missing cannot silently keep an exit condition evaluable."""
        from test_price_strategy import request, bars, POLICY
        from backtesting_api.api.price_schemas import PriceRunRequest
        from backtesting_api.application.inline_data import InlineData
        from backtesting_api.application.price_strategy import run_price_strategy
        trade = bars([('100', '101', '99', '100')] * 3)
        data = InlineData(trade, trade[:1], trade[0].trading_date.date(), trade[-1].trading_date.date(),
                          {'data_gaps': {'market_data': [trade[1].trading_date.isoformat()]}})
        spec = PriceRunRequest.model_validate(request(exit={'long': {'left': 'market.price', 'op': 'below', 'right': 0}})).compiled()
        with self.assertRaisesRegex(ValueError, 'MISSING_POSITION_MANAGEMENT_DATA'):
            run_price_strategy(data, spec, {'trade_data': {'resolution': '5'}, 'market_data': {'resolution': '5'}}, POLICY)
