"""Report dates, source coverage and indicator history are separate checks."""
from datetime import datetime
import io
import unittest
from unittest.mock import Mock

from fastapi.testclient import TestClient

from backtesting_api.api.app import create_app
from backtesting_api.application.inline_data import resolve_inline
from backtesting_api.application.inline_strategy import run_inline_strategy
from backtesting_api.application.run_backtest import BacktestService
from backtesting_api.infrastructure.auto_fetch_data import AutoDataFetcher
from test_application_api import MemoryRepository
from test_auto_fetch_data import automatic_payload, raw_source, ZONE
from test_inline_pipeline import normalized
from test_inline_strategy import sample


class ReportRangeTest(unittest.TestCase):
    def setUp(self):
        self.raw = raw_source([int(datetime(2026, 10, 9, 11, minute, tzinfo=ZONE).timestamp())
                               for minute in (0, 5)])
        self.opener = Mock(side_effect=lambda *args, **kwargs: io.BytesIO(self.raw))
        self.fetcher = AutoDataFetcher(
            clock=lambda: datetime(2026, 10, 14, 15, tzinfo=ZONE), opener=self.opener)
        self.repository = MemoryRepository()
        self.service = BacktestService(self.repository, inline_runner=run_inline_strategy,
                                       data_fetcher=self.fetcher)
        self.client = TestClient(create_app(self.service))

    def test_reversed_report_is_invalid_before_fetch_for_both_endpoints(self):
        p = automatic_payload()
        p['report'] = {'start_date': '2026-10-10', 'end_date': '2026-10-09'}
        for route in ('/api/backtests/validate', '/api/backtests'):
            response = self.client.post(route, json=p)
            self.assertEqual(response.status_code, 422, response.text)
            self.assertIn('INVALID_REPORT_RANGE', response.text)
        self.opener.assert_not_called()

    def test_missing_source_edges_keep_requested_report_for_both_endpoints(self):
        for start, end in (('2026-10-08', '2026-10-09'), ('2026-10-09', '2026-10-12')):
            p = automatic_payload()
            p['report'] = {'start_date': start, 'end_date': end}
            for route, status in (('/api/backtests/validate', 200), ('/api/backtests', 201)):
                with self.subTest(start=start, end=end, route=route):
                    response = self.client.post(route, json=p)
                    self.assertEqual(response.status_code, status, response.text)
                    metadata = response.json()['data' if status == 200 else 'metadata']
                    self.assertEqual(metadata['report_range'], {'start': start, 'end': end})
                    self.assertEqual(metadata['available_range'], {'start': '2026-10-09', 'end': '2026-10-09'})
        self.assertEqual(self.repository.failed, set())

    def test_supplied_data_and_direct_resolution_keep_partial_report(self):
        p = automatic_payload()
        p.pop('auto_fetch_data')
        sources, _ = self.fetcher.fetch()
        p.update(sources)
        p['report'] = {'start_date': '2026-10-08', 'end_date': '2026-10-09'}
        prepared = normalized(p)
        data = resolve_inline(prepared)
        self.assertEqual(data.metadata['report_range'], {'start': '2026-10-08', 'end': '2026-10-09'})
        self.assertEqual(data.metadata['available_range'], {'start': '2026-10-09', 'end': '2026-10-09'})
        response = self.client.post('/api/backtests/validate', json=p)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['data']['available_range'], data.metadata['available_range'])

    def test_empty_interval_inside_source_bounds_is_data_missing(self):
        self.raw = raw_source([int(datetime(2026, 10, day, 11, tzinfo=ZONE).timestamp())
                               for day in (7, 9)])
        p = automatic_payload()
        p.pop('auto_fetch_data')
        p.update(self.fetcher.fetch()[0])
        p['report'] = {'start_date': '2026-10-08', 'end_date': '2026-10-08'}
        response = self.client.post('/api/backtests/validate', json=p)
        self.assertEqual(response.status_code, 422, response.text)
        self.assertTrue(response.json()['detail'].startswith('REPORT_DATA_MISSING'))

    def test_contract_report_keeps_weekend_end_and_replays_with_missing_warmup(self):
        p = sample()
        p.pop('trade_data'); p.pop('market_data')
        p['auto_fetch_data'] = True
        p['report'] = {'start_date': '2026-10-09', 'end_date': '2026-10-10'}
        validated = self.client.post('/api/backtests/validate', json=p)
        self.assertEqual(validated.status_code, 200, validated.text)
        self.assertEqual(validated.json()['data']['report_range'],
                         {'start': '2026-10-09', 'end': '2026-10-10'})
        run = self.client.post('/api/backtests', json=p)
        self.assertEqual(run.status_code, 201, run.text)
        result = run.json()
        self.assertEqual(result['evaluation_status']['status'], 'UNEVALUABLE')
        self.assertEqual(result['signals'], [])
        self.opener.reset_mock()
        replay = self.client.post('/api/backtests', json=validated.json()['payload'])
        self.assertEqual(replay.status_code, 201, replay.text)
        self.assertEqual(replay.json()['summary'], result['summary'])
        self.assertEqual(replay.json()['metadata']['report_range'], result['metadata']['report_range'])
        self.opener.assert_not_called()

    def test_contract_report_missing_edge_days_records_gaps_and_runs_available_bars(self):
        for start, end, missing_day in (('2026-10-08', '2026-10-10', '2026-10-08'),
                                        ('2026-10-09', '2026-10-12', '2026-10-12')):
            p = sample()
            p.pop('trade_data'); p.pop('market_data')
            p['auto_fetch_data'] = True
            p['report'] = {'start_date': start, 'end_date': end}
            response = self.client.post('/api/backtests/validate', json=p)
            self.assertEqual(response.status_code, 200, response.text)
            metadata = response.json()['data']
            self.assertEqual(metadata['report_range'], {'start': start, 'end': end})
            self.assertEqual(metadata['available_range'], {'start': '2026-10-09', 'end': '2026-10-09'})
            self.assertTrue(any(stamp.startswith(missing_day) for stamp in metadata['data_gaps']['trade_data']))
            run = self.client.post('/api/backtests', json=p)
            self.assertEqual(run.status_code, 201, run.text)
            self.assertEqual(run.json()['signals'], [])
            self.assertEqual(run.json()['evaluation_status']['status'], 'UNEVALUABLE')

    def test_april_to_october_report_allows_saturday_end_without_changing_dates(self):
        self.raw = raw_source([int(datetime(2026, month, day, 11, tzinfo=ZONE).timestamp())
                               for month, day in ((4, 10), (10, 9))])
        p = sample()
        p.pop('trade_data'); p.pop('market_data')
        p['auto_fetch_data'] = True
        p['report'] = {'start_date': '2026-04-10', 'end_date': '2026-10-10'}
        response = self.client.post('/api/backtests/validate', json=p)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['data']['report_range'],
                         {'start': '2026-04-10', 'end': '2026-10-10'})
        self.assertTrue(response.json()['data']['data_gaps']['trade_data'])

    def test_contract_calendar_allows_holiday_start_but_not_weekend_only_report(self):
        p = sample()
        p.pop('trade_data'); p.pop('market_data')
        p['auto_fetch_data'] = True
        self.raw = raw_source([int(datetime(2026, 4, 28, 11, tzinfo=ZONE).timestamp())])
        p['report'] = {'start_date': '2026-04-27', 'end_date': '2026-04-28'}
        response = self.client.post('/api/backtests/validate', json=p)
        self.assertEqual(response.status_code, 200, response.text)
        p['report'] = {'start_date': '2026-10-10', 'end_date': '2026-10-11'}
        self.raw = raw_source([int(datetime(2026, 10, 9, 11, tzinfo=ZONE).timestamp())])
        response = self.client.post('/api/backtests/validate', json=p)
        self.assertEqual(response.status_code, 422, response.text)
        self.assertTrue(response.json()['detail'].startswith('REPORT_DATA_MISSING'))
