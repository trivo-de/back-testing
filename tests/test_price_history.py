"""Protect mixed-unit history and integrity-pinned price-only run artifacts."""
from copy import deepcopy
from datetime import datetime
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from uuid import UUID
from zoneinfo import ZoneInfo

from backtesting_api.infrastructure.file_repository import FileRunRepository, _json_bytes
from backtesting_api.application.run_backtest import BacktestService


ZONE = ZoneInfo('Asia/Ho_Chi_Minh')


class PriceHistoryRepositoryTest(unittest.TestCase):
    """Read every generation without rewriting prior results or changing units."""
    def setUp(self):
        """Keep generated run and input files inside a disposable local-only directory."""
        temporary = tempfile.TemporaryDirectory(dir='.agents')
        self.addCleanup(temporary.cleanup)
        self.repository = FileRunRepository(Path(temporary.name))
        self.policy = json.loads(Path('docs/data/vn30f1m/runtime-policy-v1.json').read_bytes())

    def point_input(self):
        """Build a fixed snapshot containing source facts, calendar and effective defaults."""
        opened = datetime(2026, 4, 1, 9, tzinfo=ZONE)
        expiry = datetime(2026, 4, 16, tzinfo=ZONE)
        source = {'symbol': 'VN30F1M', 'resolution': '5', 'timezone': ZONE.key, 'timestamp_unit': 's',
                  'bars': [{'time': int(opened.timestamp()), 'open': '100', 'high': '101', 'low': '99', 'close': '100'}],
                  'contract_map': [{'contract_code': 'VN30F2604', 'expiry_date': '2026-04-16',
                                    'expiry_unix': int(expiry.timestamp())}]}
        metadata = {'auto_fetch': {'from': int(opened.timestamp()), 'to': int(opened.timestamp()) + 300,
                                  'provider': 'fixed-test-source', 'fetched_at': opened.isoformat()}}
        payload = {'request': {'symbol': 'VN30F1M', 'from': '2026-04-01', 'to': '2026-04-01'},
                   'sources': {'trade_data': source},
                   'effective_config': {'default_profile_version': 'price-only-v1', 'allow_overnight': False}}
        return payload, SimpleNamespace(metadata=metadata)

    def point_run(self, *, realized='0', unrealized='0', total='0', drawdown='0', closed=0, win_rate=None):
        """Publish one schema-3 fixture using the same repository lifecycle as the service."""
        payload, data = self.point_input()
        run_id, input_hash, policy_hash = self.repository.start_inline(payload, self.policy, data)
        response = {'schema_version': 3, 'metadata': {
            'run_id': str(run_id), 'run_at': '2026-04-01T02:05:00+00:00', 'symbol': 'VN30F1M',
            'timezone': ZONE.key, 'resolution': '5', 'input_hash': input_hash, 'policy_hash': policy_hash,
            'report_range': {'start': '2026-04-01', 'end': '2026-04-01'},
            'effective_config': payload['effective_config'], 'default_profile_version': 'price-only-v1'},
            'summary': {'pnl_unit': 'point_quantity', 'realized_pnl': realized, 'unrealized_pnl': unrealized,
                        'total_pnl': total, 'max_drawdown': drawdown, 'closed_positions': closed,
                        'open_positions': int(unrealized != '0'), 'win_rate': win_rate}}
        self.repository.complete_run(run_id, None, response)
        return run_id, response

    def legacy_run(self, version):
        """Publish a legacy run while retaining its original monetary meanings."""
        if version == 1:
            run_id, hashes = UUID(int=1), {}
        else:
            run_id, input_hash, policy_hash = self.repository.start_inline({}, self.policy, SimpleNamespace(metadata={}))
            hashes = {'input_hash': input_hash, 'policy_hash': policy_hash}
        response = {'schema_version': version, 'metadata': {
            'run_id': str(run_id), 'money_unit': 'VND' if version == 2 else 'price_unit',
            'symbol': 'VN30F1M', 'resolution': '5', **hashes,
            'report_range': {'start': '2026-03-01', 'end': '2026-03-31'}},
            'summary': {'total_return': '0.12', 'final_equity': '112000000'}}
        self.repository.complete_run(run_id, None, response)
        return run_id, response

    def test_mixed_units_are_explicit_and_old_bytes_are_unchanged(self):
        """Expose both units without copying money values into point-valued fields."""
        old = [self.legacy_run(version) for version in (1, 2)]
        new_id, new = self.point_run(realized='6', unrealized='6', total='12', drawdown='6')
        before = {path: path.read_bytes() for path in self.repository.store.rglob('*.json')}
        rows = list(self.repository.iter_run_summaries())
        self.assertEqual(len(rows), 3)
        by_id = {row['run_id']: row for row in rows}
        point = by_id[str(new_id)]
        self.assertEqual(point['schema_version'], 3)
        self.assertEqual(point['pnl_unit'], 'point_quantity')
        self.assertIsNone(point['money_unit'])
        self.assertEqual((point['realized_pnl'], point['total_pnl'], point['max_drawdown']), ('6', '12', '6'))
        self.assertNotIn('total_return', point)
        self.assertNotIn('final_equity', point)
        for run_id, response in old:
            self.assertEqual(self.repository.get_run(run_id), response)
            item = by_id[str(run_id)]
            self.assertEqual(item['total_return'], '0.12')
            self.assertEqual(item['final_equity'], '112000000')
            self.assertIsNone(item['pnl_unit'])
            self.assertNotIn('total_pnl', item)
        self.assertEqual(self.repository.get_run(new_id), new)
        for path, raw in before.items():
            self.assertEqual(path.read_bytes(), raw)

    def test_cursor_is_stable_and_skips_incomplete_runs(self):
        """Paginate descending run IDs without exposing pending or failed attempts."""
        ids = [self.point_run()[0] for _ in range(3)]
        pending_payload, data = self.point_input()
        self.repository.start_inline(pending_payload, self.policy, data)
        failed_id, _, _ = self.repository.start_inline(pending_payload, self.policy, data)
        self.repository.fail_run(failed_id, ValueError('fixed failure'))
        rows = list(self.repository.iter_run_summaries())
        ordered = sorted(map(str, ids), reverse=True)
        self.assertEqual([row['run_id'] for row in rows], ordered)
        after = list(self.repository.iter_run_summaries(UUID(ordered[0])))
        self.assertEqual([row['run_id'] for row in after], ordered[1:])
        self.assertIsNone(self.repository.get_run(failed_id))

    def test_snapshot_chart_and_defaults_are_pinned_without_strategy_execution(self):
        """Read source candles and contract identity solely from the saved snapshot."""
        run_id, response = self.point_run()
        restarted = FileRunRepository(self.repository.store)
        document = restarted.get_input(run_id)
        self.assertEqual(document['schema_version'], 2)
        self.assertEqual(document['payload']['effective_config'], response['metadata']['effective_config'])
        self.assertFalse(document['payload']['effective_config']['allow_overnight'])
        with patch('backtesting_api.application.price_strategy.run_price_strategy', side_effect=AssertionError('reexecuted')):
            chart = restarted.get_chart(run_id)
        self.assertEqual(chart['metadata']['run_id'], str(run_id))
        self.assertEqual(chart['bars'][0]['close'], '100')
        self.assertEqual(chart['bars'][0]['contract_code'], 'VN30F2604')
        self.assertEqual(chart['market_bars'], [])

    def test_bad_policy_or_defaults_never_publish_a_success(self):
        """Reject a response that does not match the pending input's pinned configuration."""
        _, good = self.point_run()
        payload, data = self.point_input()
        for field, value, code in [('policy_hash', '0' * 64, 'POLICY_INTEGRITY_ERROR'),
                                   ('default_profile_version', 'other-profile', 'EFFECTIVE_CONFIG_MISMATCH'),
                                   ('effective_config', {'default_profile_version': 'other-profile'}, 'EFFECTIVE_CONFIG_MISMATCH')]:
            run_id, input_hash, policy_hash = self.repository.start_inline(payload, self.policy, data)
            response = deepcopy(good)
            response['metadata'].update(run_id=str(run_id), input_hash=input_hash, policy_hash=policy_hash)
            response['metadata'][field] = value
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, code):
                self.repository.complete_run(run_id, None, response)
            self.assertIsNone(self.repository.get_run(run_id))
            state = json.loads((self.repository.store / 'runs' / f'{run_id}.json').read_bytes())
            self.assertEqual(state['status'], 'running')

    def test_failed_atomic_publish_stays_pending_and_can_be_marked_failed(self):
        """A disk error cannot expose a successful result or replace its pinned input."""
        _, good = self.point_run()
        payload, data = self.point_input()
        run_id, input_hash, policy_hash = self.repository.start_inline(payload, self.policy, data)
        response = deepcopy(good)
        response['metadata'].update(run_id=str(run_id), input_hash=input_hash, policy_hash=policy_hash)
        with patch('backtesting_api.infrastructure.file_repository._publish_json', side_effect=OSError('disk unavailable')):
            with self.assertRaises(OSError):
                self.repository.complete_run(run_id, None, response)
        self.assertIsNone(self.repository.get_run(run_id))
        self.repository.fail_run(run_id, OSError('disk unavailable'))
        self.assertIsNone(self.repository.get_run(run_id))
        self.assertEqual(len(list(self.repository.iter_run_summaries())), 1)

    def test_input_and_completed_result_cannot_be_overwritten(self):
        """Retain the existing successful file and detect a tampered content-addressed input."""
        run_id, response = self.point_run()
        path = self.repository.store / 'runs' / f'{run_id}.json'
        original = path.read_bytes()
        with self.assertRaisesRegex(ValueError, 'RUN_INPUT_MISMATCH'):
            self.repository.complete_run(run_id, None, response)
        self.assertEqual(path.read_bytes(), original)
        input_path = self.repository.store / 'inputs' / (response['metadata']['input_hash'] + '.json')
        modified = input_path.read_bytes() + b' '
        input_path.write_bytes(modified)
        payload, data = self.point_input()
        with self.assertRaisesRegex(ValueError, 'INPUT_INTEGRITY_ERROR'):
            self.repository.start_inline(payload, self.policy, data)
        self.assertEqual(input_path.read_bytes(), modified)
        with self.assertRaisesRegex(ValueError, 'INPUT_INTEGRITY_ERROR'):
            self.repository.get_input(run_id)

    def test_no_trade_summary_and_invalid_point_summaries(self):
        """Keep no-trade ratios null and refuse nonfinite or inconsistent point metrics."""
        run_id, response = self.point_run()
        row = next(self.repository.iter_run_summaries())
        self.assertEqual((row['total_pnl'], row['closed_positions'], row['open_positions']), ('0', 0, 0))
        self.assertIsNone(row['win_rate'])
        path = self.repository.store / 'runs' / f'{run_id}.json'
        original = json.loads(path.read_bytes())
        for key, value in [('total_pnl', 'NaN'), ('total_pnl', '1'), ('max_drawdown', '-1'),
                           ('closed_positions', True), ('win_rate', '0.5'), ('pnl_unit', 'VND')]:
            changed = deepcopy(original)
            changed['result']['summary'][key] = value
            changed['result_hash'] = hashlib.sha256(_json_bytes(changed['result'])).hexdigest()
            path.write_bytes(_json_bytes(changed))
            with self.subTest(key=key, value=value), self.assertRaisesRegex(ValueError, 'RESULT_SUMMARY_INVALID'):
                list(self.repository.iter_run_summaries())
        path.write_bytes(_json_bytes(original))

    def test_rehashed_config_tampering_is_still_rejected(self):
        """A result hash cannot conceal disagreement with the separately pinned snapshot."""
        run_id, _ = self.point_run()
        path = self.repository.store / 'runs' / f'{run_id}.json'
        value = json.loads(path.read_bytes())
        value['result']['metadata']['effective_config']['allow_overnight'] = True
        value['result_hash'] = hashlib.sha256(_json_bytes(value['result'])).hexdigest()
        path.write_bytes(_json_bytes(value))
        with self.assertRaisesRegex(ValueError, 'EFFECTIVE_CONFIG_MISMATCH'):
            self.repository.get_run(run_id)

    def test_service_filters_mixed_units_without_comparing_money_and_points(self):
        """Apply each metric only to the generation that owns its unit."""
        old_ids = {str(self.legacy_run(version)[0]) for version in (1, 2)}
        point_id, _ = self.point_run(realized='6', total='6', drawdown='2', closed=2, win_rate='0.5')
        service = BacktestService(self.repository)
        self.assertEqual(len(service.history()['items']), 3)
        self.assertEqual({row['run_id'] for row in service.history(unit='legacy')['items']}, old_ids)
        points = service.history(unit='point_quantity', min_total_pnl=Decimal(6), max_total_pnl=Decimal(6),
                                 min_realized_pnl=Decimal(6), max_max_drawdown=Decimal(2),
                                 min_closed_positions=2, max_closed_positions=2)['items']
        self.assertEqual([row['run_id'] for row in points], [str(point_id)])
        self.assertEqual({row['run_id'] for row in service.history(min_equity=Decimal(1))['items']}, old_ids)
        self.assertEqual(service.history(min_total_pnl=Decimal(7))['items'], [])

    def test_service_metric_sort_paginates_equal_values_by_stable_run_id(self):
        """Sort only point summaries and preserve ties across cursor pages."""
        self.legacy_run(1)
        ids = [self.point_run(realized=value, total=value, closed=1, win_rate='1')[0]
               for value in ('3', '1', '3')]
        service = BacktestService(self.repository)
        first = service.history(sort_by='total_pnl', sort_order='desc', limit=1)
        expected = [*sorted((str(ids[0]), str(ids[2])), reverse=True), str(ids[1])]
        result = [first['items'][0]['run_id']]
        cursor = first['next_cursor']
        while cursor is not None:
            page = service.history(sort_by='total_pnl', sort_order='desc', limit=1, after=UUID(cursor))
            result.extend(item['run_id'] for item in page['items'])
            cursor = page['next_cursor']
        self.assertEqual(result, expected)
        ascending = service.history(sort_by='total_pnl', sort_order='asc')['items']
        self.assertEqual(ascending[0]['run_id'], str(ids[1]))
        self.assertEqual(len(ascending), 3)

    def test_service_default_history_streams_only_the_needed_mixed_summaries(self):
        """Default pagination never loads every full result document eagerly."""
        for _ in range(5):
            self.point_run()
        service = BacktestService(self.repository)
        with patch.object(self.repository, 'list_runs', side_effect=AssertionError('full list loaded')):
            with patch.object(self.repository, 'get_run', wraps=self.repository.get_run) as read:
                page = service.history(limit=2)
        self.assertEqual(len(page['items']), 2)
        self.assertEqual(read.call_count, 3)
        self.assertEqual(page['next_cursor'], page['items'][-1]['run_id'])
