import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from uuid import UUID

from fastapi.testclient import TestClient

from backtesting_api.api.app import create_app
from backtesting_api.application.run_backtest import BacktestService
from backtesting_api.infrastructure.file_repository import FileRunRepository


class RunHistoryTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.repository = FileRunRepository(Path(temporary.name))
        self.client = TestClient(create_app(BacktestService(self.repository)))
        for index, (total_return, equity) in enumerate([
                ('-0.1', '90'), ('0', '100'), ('0.011', '101.1'),
                ('0.2', '120'), ('0.5', '150')], 1):
            run_id = UUID(int=index)
            self.repository.complete_run(run_id, None, {
                'metadata': {'run_id': str(run_id), 'money_unit': 'price_unit',
                             'config': {'symbol': 'TEST', 'start_date': '2026-03-01', 'end_date': '2026-03-31'}},
                'summary': {'total_return': total_return, 'final_equity': equity},
                'evaluations': [{'indicators': {'unused': '123'}}] * 100,
                'equity_history': [{'equity': equity}] * 100,
            })

    def test_server_filters_inclusive_percent_and_equity_without_full_list(self):
        with patch.object(self.repository, 'list_runs', side_effect=AssertionError('full history loaded')):
            response = self.client.get('/api/backtests/history', params={
                'min_total_return_pct': '1.1', 'max_total_return_pct': '20',
                'min_equity': '101.1', 'max_equity': '120'})
        self.assertEqual(response.status_code, 200, response.text)
        page = response.json()
        self.assertEqual([item['run_id'] for item in page['items']], [str(UUID(int=4)), str(UUID(int=3))])
        self.assertIsNone(page['next_cursor'])
        self.assertEqual(page['items'][1]['total_return'], '0.011')
        self.assertEqual(page['items'][0]['symbol'], 'TEST')
        self.assertEqual(page['items'][0]['start_date'], '2026-03-01')
        self.assertNotIn('evaluations', response.text)
        self.assertNotIn('equity_history', response.text)

    def test_pagination_reads_only_needed_runs_and_keeps_filter(self):
        with patch.object(self.repository, 'get_run', wraps=self.repository.get_run) as read:
            page = self.client.get('/api/backtests/history?limit=2&min_total_return_pct=0').json()
        self.assertEqual(read.call_count, 3)
        ids = [item['run_id'] for item in page['items']]
        self.assertEqual(page['next_cursor'], ids[-1])
        second = self.client.get('/api/backtests/history', params={
            'limit': 2, 'min_total_return_pct': 0, 'after': page['next_cursor']}).json()
        ids.extend(item['run_id'] for item in second['items'])
        self.assertEqual(ids, [str(UUID(int=i)) for i in (5, 4, 3, 2)])
        self.assertIsNone(second['next_cursor'])
        self.assertEqual(self.client.get('/api/backtests/history?min_equity=999').json(),
                         {'items': [], 'next_cursor': None})

    def test_invalid_filters_and_corrupt_result_are_rejected(self):
        for query in ('min_equity=2&max_equity=1', 'min_total_return_pct=2&max_total_return_pct=1',
                      'min_equity=NaN', 'min_total_return_pct=inf', 'limit=0', 'limit=101', 'after=bad'):
            self.assertEqual(self.client.get('/api/backtests/history?' + query).status_code, 422, query)
        path = self.repository.store / 'runs' / f'{UUID(int=5)}.json'
        document = json.loads(path.read_bytes())
        document['result']['summary']['final_equity'] = '0'
        path.write_text(json.dumps(document), encoding='utf-8')
        self.assertEqual(self.client.get('/api/backtests/history').status_code, 409)

    def test_inline_metadata_and_failed_runs(self):
        run_id, input_hash, policy_hash = self.repository.start_inline({}, None, SimpleNamespace(metadata={}))
        self.repository.complete_run(run_id, None, {
            'schema_version': 2,
            'metadata': {'run_id': str(run_id), 'symbol': 'VN30F1M', 'resolution': '5', 'money_unit': 'VND',
                         'input_hash': input_hash, 'policy_hash': policy_hash,
                         'report_range': {'start': '2026-03-15', 'end': '2026-09-15'}},
            'summary': {'total_return': '-0.2', 'final_equity': '80000000'}})
        (self.repository.store / 'runs' / f'{UUID(int=7)}.json').write_text(
            json.dumps({'schema_version': 2, 'status': 'failed'}), encoding='utf-8')
        page = self.client.get('/api/backtests/history?limit=1').json()
        self.assertEqual(page['items'][0]['run_id'], str(run_id))
        self.assertEqual(page['items'][0]['start_date'], '2026-03-15')
        self.assertEqual(page['items'][0]['end_date'], '2026-09-15')
        self.assertEqual(page['items'][0]['money_unit'], 'VND')
        input_path = self.repository.store / 'inputs' / f'{input_hash}.json'
        input_path.write_bytes(input_path.read_bytes() + b' ')
        self.assertEqual(self.client.get('/api/backtests/history').status_code, 409)


if __name__ == '__main__':
    unittest.main()
