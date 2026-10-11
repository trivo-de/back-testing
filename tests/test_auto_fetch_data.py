"""Offline checks of source selection, upstream errors and snapshot replay."""
from datetime import datetime
from decimal import Decimal
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient
from pydantic import ValidationError
from backtesting_api.api.app import create_app
from backtesting_api.api.inline_schemas import InlineRunRequest
from backtesting_api.application.inline_strategy import run_inline_strategy
from backtesting_api.application.inline_data import resolve_inline
from backtesting_api.application.run_backtest import BacktestService
from backtesting_api.infrastructure.auto_fetch_data import AutoDataFetcher
from backtesting_api.infrastructure.file_repository import FileRunRepository
from test_inline_strategy import sample

ZONE = ZoneInfo('Asia/Ho_Chi_Minh')
NOW = datetime(2026, 10, 9, 11, 13, 55, tzinfo=ZONE)
TIMES = [int(NOW.replace(hour=11, minute=minute, second=0).timestamp()) for minute in (0, 5, 10)]


def automatic_payload():
    return {
        'auto_fetch_data': True, 'initial_cash': '10000',
        'accounting': {'model': 'normalized', 'fee_rate': '.001'},
        'execution': {'entry_fill_policy': 'next_open', 'slippage_rate': '0'},
        'strategy': {
            'entry': {'conditions': {'BUY': {'gt': [{'ref': 'trade_data.close'}, 0]}}, 'any': ['BUY']},
            'exit': {'bar_close': {'conditions': {'STOP': {'lt': [{'ref': 'trade_data.close'}, 0]}},
                                  'any': ['STOP'], 'priority': ['STOP'], 'quantity': 'remaining',
                                  'fill_policy': 'next_open'}},
            'sizing': {'type': 'fixed_fractional', 'risk_fraction': '.02', 'stop_loss_fraction': '.07'},
        },
    }


def raw_source(times=TIMES):
    # Decimal values are parsed from JSON numbers, without a float conversion.
    return json.dumps({'s': 'ok', 't': times, 'o': [1000.1] * len(times),
                       'h': [1001] * len(times), 'l': [999] * len(times),
                       'c': [1000.5] * len(times), 'v': [100] * len(times)}).encode()


class AutoFetchTest(unittest.TestCase):
    def setUp(self):
        self.raw = raw_source()
        self.opener = Mock(side_effect=lambda *args, **kwargs: io.BytesIO(self.raw))
        self.fetcher = AutoDataFetcher(clock=lambda: NOW, opener=self.opener)
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.repository = FileRunRepository(Path(temporary.name))
        self.service = BacktestService(self.repository, inline_runner=run_inline_strategy, data_fetcher=self.fetcher)
        self.client = TestClient(create_app(self.service))

    def test_exact_calendar_range_shared_by_both_sources_and_closed_bars_only(self):
        sources, meta = self.fetcher.fetch()
        self.assertEqual(meta['from'], int(NOW.replace(month=4).timestamp()))
        self.assertEqual(meta['to'], int(NOW.timestamp()))
        for name, symbol in [('trade_data', 'VN30F1M'), ('market_data', 'VNINDEX')]:
            source = sources[name]
            self.assertEqual([bar['time'] for bar in source['bars']], TIMES[:2])
            self.assertEqual(Decimal(source['bars'][0]['open']), Decimal('1000.1'))
            self.assertEqual(meta['sources'][name]['raw_hash'], hashlib.sha256(self.raw).hexdigest())
            self.assertEqual(meta['sources'][name]['excluded_unclosed_count'], 1)
            self.assertEqual(source['symbol'], symbol)
        for call in self.opener.call_args_list:
            request = call.args[0]
            self.assertEqual(request.get_header('Accept'), '*/*')
            self.assertEqual(request.get_header('User-agent'), 'backtest-hpg/0.1')
            query = parse_qs(urlsplit(request.full_url).query)
            self.assertEqual(query['from'], [str(meta['from'])])
            self.assertEqual(query['to'], [str(meta['to'])])
            self.assertEqual(query['resolution'], ['5'])

    def test_calendar_month_end_clamps_and_closed_atc_is_kept(self):
        end = datetime(2026, 8, 31, 15, 0, tzinfo=ZONE)
        atc = int(end.replace(hour=14, minute=45).timestamp())
        self.fetcher.clock = lambda: end
        self.raw = raw_source([atc])
        sources, meta = self.fetcher.fetch()
        self.assertEqual(datetime.fromtimestamp(meta['from'], ZONE), end.replace(month=2, day=28))
        self.assertEqual(sources['trade_data']['bars'][0]['time'], atc)

    def test_invalid_upstream_snapshots_are_not_repaired(self):
        invalid = [b'not json', b'{"s":"no_data"}',
                   raw_source([TIMES[1], TIMES[0]]), raw_source([TIMES[0] + 1]),
                   raw_source([int(NOW.timestamp()) + 300])]
        bad = json.loads(self.raw); bad['h'][0] = 900
        invalid.append(json.dumps(bad).encode())
        bad = json.loads(self.raw); bad['v'].pop()
        invalid.append(json.dumps(bad).encode())
        for raw in invalid:
            with self.subTest(raw=raw):
                self.raw = raw
                response = self.client.post('/api/backtests/validate', json=automatic_payload())
                self.assertEqual(response.status_code, 422)
                self.assertIn('AUTO_FETCH_INVALID_SOURCE:trade_data', response.json()['detail'])
        self.raw = raw_source([TIMES[-1]])
        response = self.client.post('/api/backtests', json=automatic_payload())
        self.assertEqual(response.status_code, 422)
        self.assertIn('AUTO_FETCH_NO_CLOSED_BARS', response.json()['detail'])
        self.assertEqual(self.repository.list_runs(), [])

    def test_http_and_network_failures_have_upstream_errors(self):
        for error, code in [(HTTPError('url', 500, 'error', {}, None), 'AUTO_FETCH_HTTP_ERROR:trade_data:500'),
                            (URLError('offline'), 'AUTO_FETCH_NETWORK_ERROR:trade_data')]:
            self.opener.side_effect = error
            for route in ('/api/backtests/validate', '/api/backtests'):
                response = self.client.post(route, json=automatic_payload())
                self.assertEqual(response.status_code, 503)
                self.assertEqual(response.json()['detail'], code)
        self.service.data_fetcher = None
        response = self.client.post('/api/backtests', json=automatic_payload())
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()['detail'], 'AUTO_FETCH_UNAVAILABLE')

    def test_auto_data_has_priority_and_boolean_is_strict(self):
        auto = automatic_payload()
        InlineRunRequest.model_validate(auto)
        for value in ('true', 1, None):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                InlineRunRequest.model_validate({**auto, 'auto_fetch_data': value})
        for name in ('trade_data', 'market_data'):
            mixed = {**auto, name: sample()[name]}
            request = InlineRunRequest.model_validate(mixed)
            self.assertIsNone(request.trade_data)
            self.assertIsNone(request.market_data)
        with self.assertRaisesRegex(ValidationError, 'MISSING_REQUIRED_DATA: trade_data'):
            InlineRunRequest.model_validate({**auto, 'auto_fetch_data': False})
        manual = sample(); manual.pop('market_data')
        with self.assertRaisesRegex(ValidationError, 'MISSING_REQUIRED_DATA: market_data'):
            InlineRunRequest.model_validate(manual)

    def test_http_ignores_even_invalid_manual_sources_only_when_auto_is_true(self):
        for supplied in (json.loads(self.raw), {'bars': []}, 'invalid', []):
            p = {**automatic_payload(), 'trade_data': supplied, 'market_data': supplied}
            with self.subTest(supplied=supplied):
                validation = self.client.post('/api/backtests/validate', json=p)
                self.assertEqual(validation.status_code, 200, validation.text)
                prepared = validation.json()['payload']
                for name, symbol in (('trade_data', 'VN30F1M'), ('market_data', 'VNINDEX')):
                    self.assertEqual(prepared[name]['symbol'], symbol)
                    self.assertEqual([b['time'] for b in prepared[name]['bars']], TIMES[:2])
                run = self.client.post('/api/backtests', json=p)
                self.assertEqual(run.status_code, 201, run.text)
                self.assertEqual(run.json()['metadata']['input_origin'], 'auto_fetch')
        self.opener.reset_mock()
        p['auto_fetch_data'] = False
        for route in ('/api/backtests/validate', '/api/backtests'):
            self.assertEqual(self.client.post(route, json=p).status_code, 422)
        p.pop('auto_fetch_data')
        self.assertEqual(self.client.post('/api/backtests', json=p).status_code, 422)
        self.opener.assert_not_called()

    def test_service_overwrites_manual_sources_and_fetch_failure_never_uses_them(self):
        p = automatic_payload()
        p['trade_data'] = p['market_data'] = 'invalid'
        data, _ = self.service.validate_inline(p)
        self.assertEqual(data.metadata['input_origin'], 'auto_fetch')
        self.assertEqual(p['trade_data']['symbol'], 'VN30F1M')
        self.assertEqual(p['market_data']['symbol'], 'VNINDEX')
        manual = {**automatic_payload(), 'trade_data': json.loads(self.raw),
                  'market_data': json.loads(self.raw)}
        self.opener.side_effect = HTTPError('url', 500, 'error', {}, None)
        for route in ('/api/backtests/validate', '/api/backtests'):
            response = self.client.post(route, json=manual)
            self.assertEqual(response.status_code, 503, response.text)
            self.assertEqual(response.json()['detail'], 'AUTO_FETCH_HTTP_ERROR:trade_data:500')
        self.assertEqual(list(self.repository.store.iterdir()), [])

    def test_second_source_failure_does_not_start_a_run(self):
        self.opener.side_effect = [io.BytesIO(self.raw), HTTPError('url', 500, 'error', {}, None)]
        response = self.client.post('/api/backtests', json=automatic_payload())
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()['detail'], 'AUTO_FETCH_HTTP_ERROR:market_data:500')
        self.assertEqual(list(self.repository.store.iterdir()), [])

    def test_main_connects_fetcher_and_openapi_lists_optional_sources(self):
        from backtesting_api.main import build_service
        self.assertIsInstance(build_service().data_fetcher, AutoDataFetcher)
        schema = self.client.get('/openapi.json').json()['components']['schemas']['InlineRunRequest']
        for name in ('auto_fetch_data', 'trade_data', 'market_data'):
            self.assertNotIn(name, schema['required'])
        self.assertIs(schema['properties']['auto_fetch_data']['default'], False)

    def test_validate_returns_replayable_sources_and_run_pins_provenance(self):
        response = self.client.post('/api/backtests/validate', json=automatic_payload())
        self.assertEqual(response.status_code, 200, response.text)
        prepared = response.json()['payload']
        self.assertFalse(prepared['auto_fetch_data'])
        InlineRunRequest.model_validate(prepared)
        self.assertEqual(response.json()['data']['input_origin'], 'auto_fetch')
        self.assertEqual(self.repository.list_runs(), [])
        automatic = self.client.post('/api/backtests', json=automatic_payload())
        self.assertEqual(automatic.status_code, 201, automatic.text)
        result = automatic.json()
        self.assertIsNotNone(datetime.fromisoformat(result['metadata']['run_at']).tzinfo)
        stored = self.client.get('/api/backtests/' + result['metadata']['run_id']).json()
        self.assertEqual(stored['metadata']['run_at'], result['metadata']['run_at'])
        history = self.client.get('/api/backtests/history').json()['items'][0]
        self.assertEqual(datetime.fromisoformat(history['run_at']), datetime.fromisoformat(result['metadata']['run_at']))
        document = self.client.get('/api/backtests/' + result['metadata']['run_id'] + '/input').json()
        self.assertEqual(document['payload'], prepared)
        self.assertEqual(document['data_metadata']['auto_fetch'], result['metadata']['auto_fetch'])
        chart = self.client.get('/api/backtests/' + result['metadata']['run_id'] + '/chart')
        self.assertEqual(chart.status_code, 200, chart.text)
        self.assertEqual(len(chart.json()['bars']), 2)
        self.opener.reset_mock()
        replay = self.client.post('/api/backtests', json=document['payload'])
        self.assertEqual(replay.status_code, 201, replay.text)
        self.opener.assert_not_called()
        for field in ('summary', 'signals', 'fills', 'equity_history'):
            actual, repeated = result[field], replay.json()[field]
            if isinstance(actual, list):
                actual = [{k: v for k, v in row.items() if not k.endswith('_id')} for row in actual]
                repeated = [{k: v for k, v in row.items() if not k.endswith('_id')} for row in repeated]
            self.assertEqual(actual, repeated)
        self.assertEqual(result['fills'][0]['fill_time'], NOW.replace(minute=5, second=0).isoformat())

    def test_explicit_report_must_fit_and_contract_calendar_covers_october(self):
        invalid = automatic_payload()
        invalid['report'] = {'start_date': '2026-04-09', 'end_date': '2026-10-09'}
        response = self.client.post('/api/backtests', json=invalid)
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()['detail'], 'INVALID_REPORT_RANGE')
        contract = sample()
        contract.pop('trade_data'); contract.pop('market_data'); contract['auto_fetch_data'] = True
        response = self.client.post('/api/backtests/validate', json=contract)
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()['data']
        self.assertEqual(data['input_origin'], 'auto_fetch')
        self.assertTrue(data['data_gaps']['trade_data'])
        prepared = response.json()['payload']
        self.assertEqual(len(prepared['trade_data']['bars']), 2)
        policy = json.loads(self.service.inline_policy_path.read_bytes())
        resolved = resolve_inline(prepared, policy)
        self.assertEqual({bar.contract_code for bar in resolved.bars}, {'VN30F2610'})
        policy['calendar_range']['end'] = '2026-10-08'
        with self.assertRaisesRegex(ValueError, 'REPORT_OUTSIDE_STATIC_CALENDAR'):
            resolve_inline(prepared, policy)

    def test_2026_calendar_keeps_holidays_and_excludes_weekends(self):
        for name in ('runtime-policy.json', 'runtime-policy-v1.json'):
            policy = json.loads((Path('docs/data/vn30f1m') / name).read_bytes())
            days = policy['trading_dates']
            self.assertEqual(days, sorted(set(days)))
            self.assertEqual(policy['calendar_range'], {'start': '2026-03-01', 'end': '2026-12-31'})
            self.assertEqual(days[-1], '2026-12-31')
            for day in ('2026-09-18', '2026-10-09', '2026-12-31'):
                self.assertIn(day, days)
            for day in ('2026-04-27', '2026-04-30', '2026-05-01',
                        '2026-08-31', '2026-09-01', '2026-09-02', '2026-08-22'):
                self.assertNotIn(day, days)
            self.assertTrue(all(datetime.fromisoformat(day).weekday() < 5 for day in days))


if __name__ == '__main__':
    unittest.main()
