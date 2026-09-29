"""Synthetic U05/U06 integration checks; the fixture runner is not a production strategy."""
from copy import deepcopy
from datetime import date, datetime, timedelta
from decimal import Decimal as D
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from uuid import UUID
from zoneinfo import ZoneInfo
from fastapi.testclient import TestClient
from backtest_hpg.api.app import create_app
from backtest_hpg.api.inline_schemas import InlineRunRequest
from backtest_hpg.application.inline_data import resolve_inline
from backtest_hpg.application.run_backtest import BacktestService
from backtest_hpg.domain.contract_accounting import ContractAccounting
from backtest_hpg.domain.engine import run_engine
from backtest_hpg.domain.execution import Bracket, ContractExecution
from backtest_hpg.domain.trading import FixedSignal
from backtest_hpg.infrastructure.file_repository import FileRunRepository, _json_bytes
from test_inline_strategy import sample


ZONE = ZoneInfo('Asia/Ho_Chi_Minh')


def candle(stamp, opened='1000', high='1001', low='999', close='1000'):
    return {'time': int(stamp.timestamp()), 'open': opened, 'high': high, 'low': low, 'close': close}


def payload():
    p = sample()
    start = datetime(2026, 3, 25, 9, tzinfo=ZONE)
    p['trade_data'] = {'resolution': '5', 'symbol': 'ARBITRARY_LABEL', 'bars': [
        candle(start), candle(start + timedelta(minutes=5), high='1013', low='999', close='1012'),
        candle(start + timedelta(minutes=10), opened='1012', high='1013', low='1011', close='1012')]}
    p.pop('market_data')
    p['strategy']['indicators'] = {}
    p['strategy'].pop('warmup_bars')
    p['strategy']['entry']['conditions'] = {'LONG': {'gt': [{'ref': 'trade_data.close'}, 0]}}
    p['strategy']['entry']['any'] = ['LONG']
    p['strategy']['exit']['targets'].pop('SHORT')
    return p


def normalized(p):
    return InlineRunRequest.model_validate(p).model_dump(mode='json', by_alias=True, exclude_none=True)


def fixture_runner(data, p):
    first = next(b.trading_date for b in data.bars if b.trading_date.date() >= data.start_date)
    accounting = ContractAccounting(**{key: value for key, value in p['accounting'].items() if key != 'model'})
    return run_engine(data.bars, lambda c: FixedSignal('LONG', 3) if c.bars[-1].trading_date == first else None,
                      initial_cash=p['initial_cash'], fee_rate=0, slippage_rate=0,
                      support_bars=data.market_bars, record_start=data.start_date, trade_start=data.start_date,
                      execution=lambda cash: ContractExecution(cash, accounting,
                          bracket=Bracket(D(6), ((D(6), 1), (D(12), None)))))


class InlinePipelineTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.store = Path(temporary.name)
        self.repository = FileRunRepository(self.store, self.store / 'unused-v0-policy.json')
        self.service = BacktestService(self.repository, inline_runner=fixture_runner)
        self.client = TestClient(create_app(self.service))

    def test_json_engine_storage_reload_and_same_bar_exit_links(self):
        response = self.client.post('/api/backtests', json=payload())
        self.assertEqual(response.status_code, 201, response.text)
        result = response.json()
        self.assertEqual(result['schema_version'], 2)
        self.assertEqual([f['fill_price'] for f in result['fills']], ['1000', '1006', '1012'])
        self.assertEqual(len({f['order_id'] for f in result['fills']}), 3)
        self.assertEqual(len({f['position_id'] for f in result['fills']}), 1)
        self.assertEqual([t['exit_fill_id'] for t in result['trades']], [f['fill_id'] for f in result['fills'][1:]])
        self.assertEqual(result['summary']['realized_pnl'], '2917245')
        self.assertEqual(result['fills'][0]['pit'], '25500')
        self.assertNotIn('pivot', result['signals'][0])
        self.assertIsNone(result['open_position'])
        self.assertIn('required_margin', result['equity_history'][0])
        run_id = result['metadata']['run_id']
        fresh = TestClient(create_app(BacktestService(FileRunRepository(self.store, self.store / 'unused'))))
        self.assertEqual(fresh.get('/api/backtests/' + run_id).json(), result)
        self.assertEqual(fresh.get('/api/backtests').json(), [result])
        document = fresh.get(f'/api/backtests/{run_id}/input').json()
        self.assertEqual(document['payload'], normalized(payload()))
        self.assertEqual(hashlib.sha256(_json_bytes(document)).hexdigest(), result['metadata']['input_hash'])
        chart = fresh.get(f'/api/backtests/{run_id}/chart').json()
        self.assertEqual(len(chart['bars']), 3)
        self.assertIsNone(chart['bars'][0]['volume'])
        repeated = self.client.post('/api/backtests', json=payload()).json()
        self.assertEqual(repeated['summary'], result['summary'])
        self.assertEqual(repeated['equity_history'], result['equity_history'])
        self.assertEqual(repeated['metadata']['input_hash'], result['metadata']['input_hash'])

    def test_corrupt_input_result_and_schema_are_not_silently_accepted(self):
        result = self.client.post('/api/backtests', json=payload()).json()
        run_id = result['metadata']['run_id']
        input_path = self.store / 'inputs' / (result['metadata']['input_hash'] + '.json')
        raw = input_path.read_bytes()
        input_path.write_bytes(raw + b' ')
        self.assertEqual(self.client.get('/api/backtests/' + run_id).status_code, 409)
        self.assertEqual(self.client.get(f'/api/backtests/{run_id}/input').status_code, 409)
        input_path.write_bytes(raw)
        path = self.store / 'runs' / (run_id + '.json')
        original = json.loads(path.read_bytes())
        for mutate in (lambda v: v.update(schema_version=99),
                       lambda v: v['result']['summary'].update(final_equity='0'),
                       lambda v: v.update(input_hash='../wrong')):
            value = deepcopy(original)
            mutate(value)
            path.write_bytes(_json_bytes(value))
            self.assertEqual(self.client.get('/api/backtests/' + run_id).status_code, 409)
        path.write_bytes(_json_bytes(original))
        self.assertEqual(self.client.get('/api/backtests/' + run_id).status_code, 200)

    def test_failed_run_and_atomic_write_failure_never_publish_success(self):
        def broken(data, p): raise ValueError('FIXTURE_FAILURE')
        self.service.inline_runner = broken
        self.assertEqual(self.client.post('/api/backtests', json=payload()).status_code, 422)
        records = [json.loads(p.read_bytes()) for p in (self.store / 'runs').glob('*.json')]
        self.assertEqual([v['status'] for v in records], ['failed'])
        self.assertIn('input_hash', records[0])
        self.assertEqual(self.client.get('/api/backtests').json(), [])
        self.service.inline_runner = fixture_runner
        with patch('backtest_hpg.infrastructure.file_repository.os.replace', side_effect=OSError('disk unavailable')):
            self.assertEqual(self.client.post('/api/backtests', json=payload()).status_code, 503)
        self.assertFalse(list(self.store.rglob('*.tmp')))

    def test_no_production_runner_rejects_without_starting_or_falling_back(self):
        self.service.inline_runner = None
        response = self.client.post('/api/backtests', json=payload())
        self.assertEqual(response.status_code, 422)
        self.assertIn('INLINE_STRATEGY_RUNTIME_NOT_IMPLEMENTED', response.json()['detail'])
        self.assertFalse((self.store / 'runs').exists())

    def test_legacy_v1_file_and_v2_file_share_read_routes(self):
        legacy = json.loads((Path(__file__).parent / 'fixtures/v0-baseline.json').read_bytes())['cases'][0]['response']
        run_id = UUID(legacy['metadata']['run_id'])
        self.repository.complete_run(run_id, None, legacy)
        self.assertEqual(self.client.get('/api/backtests/' + str(run_id)).json(), legacy)
        created = self.client.post('/api/backtests', json=payload())
        self.assertEqual(created.status_code, 201, created.text)
        self.assertEqual(len(self.client.get('/api/backtests').json()), 2)

    def test_short_open_position_rejection_pending_and_combined_backend(self):
        def short_runner(data, p):
            return run_engine(data.bars, lambda c: FixedSignal('SHORT', 2) if len(c.bars) == 1 else
                              (FixedSignal('CLOSE') if len(c.bars) == len(data.bars) else None),
                              initial_cash=p['initial_cash'], fee_rate=0, slippage_rate=0,
                              execution=lambda cash: ContractExecution(cash, ContractAccounting(**{
                                  key: value for key, value in p['accounting'].items() if key != 'model'})))
        self.service.inline_runner = short_runner
        result = self.client.post('/api/backtests', json=payload()).json()
        self.assertEqual(result['open_position']['direction'], 'SHORT')
        self.assertEqual(result['open_position']['quantity'], 2)
        self.assertEqual(result['orders'][-1]['status'], 'pending')
        self.assertEqual(result['orders'][-1]['position_id'], result['open_position']['position_id'])
        self.assertEqual(result['equity_history'][-1]['unrealized_pnl'], '-2400000')
        p = payload()
        p['initial_cash'] = '1'
        rejected = self.client.post('/api/backtests', json=p)
        self.assertEqual(rejected.status_code, 422)  # Fixture cannot close a rejected entry.
        from test_application_api import MemoryRepository
        old = MemoryRepository()
        old_id = UUID(int=123)
        old.runs[old_id] = {'metadata': {'run_id': str(old_id)}, 'legacy': True}
        mixed = TestClient(create_app(BacktestService(old, inline_repository=self.repository)))
        self.assertEqual(mixed.get('/api/backtests/' + str(old_id)).json(), old.runs[old_id])
        self.assertEqual(len(mixed.get('/api/backtests').json()), 2)

    def test_shared_entrypoint_selects_backend_explicitly(self):
        from backtest_hpg.main import build_service, app
        from backtest_hpg.intraday_main import app as alias
        self.assertIs(app, alias)
        with patch.dict('os.environ', {'BACKTEST_LEGACY_BACKEND': 'file'}):
            service = build_service()
            self.assertIs(service.repository, service.inline_repository)
        with patch.dict('os.environ', {'BACKTEST_LEGACY_BACKEND': 'postgres'}), \
                patch('backtest_hpg.main.get_database_url', return_value='fixture'), \
                patch('backtest_hpg.main.PostgresRunRepository') as factory:
            service = build_service()
            factory.assert_called_once_with('fixture')
            self.assertIsNot(service.repository, service.inline_repository)
        with patch.dict('os.environ', {'BACKTEST_LEGACY_BACKEND': 'wrong'}), self.assertRaises(ValueError):
            build_service()


class InlineDataTest(unittest.TestCase):
    def test_seconds_milliseconds_daily_optional_volume_and_delayed_market(self):
        p = normalized(payload())
        data = resolve_inline(p)
        self.assertIsNone(data.bars[0].volume)
        self.assertEqual(data.bars[0].closed_at - data.bars[0].trading_date, timedelta(minutes=5))
        millis = deepcopy(p)
        millis['trade_data']['timestamp_unit'] = 'ms'
        for row in millis['trade_data']['bars']: row['time'] *= 1000
        self.assertEqual(resolve_inline(millis), data)
        p['market_data'] = {'resolution': '5', 'timestamp_unit': 's', 'timezone': 'Asia/Ho_Chi_Minh',
                            'bars': [dict(p['trade_data']['bars'][0], available_at=p['trade_data']['bars'][0]['time'] + 600)]}
        data = resolve_inline(p)
        seen = []
        run_engine(data.bars, lambda c: seen.append(len(c.support_bars)), initial_cash=1000, fee_rate=0,
                   slippage_rate=0, support_bars=data.market_bars)
        self.assertEqual(seen, [0, 1, 1])
        p['market_data']['resolution'] = 'D'
        p['market_data']['bars'][0]['close_time'] = p['market_data']['bars'][0]['time'] + 300
        self.assertEqual(resolve_inline(p).market_bars[0].available_at, data.market_bars[0].available_at)

    def test_report_history_never_trades_and_future_values_cannot_leak(self):
        p = payload()
        original = p['trade_data']['bars']
        p['trade_data']['bars'] = [dict(original[0], time=original[0]['time'] - 86400), *original,
                                  dict(original[-1], time=original[-1]['time'] + 86400)]
        p['report'] = {'start_date': '2026-03-25', 'end_date': '2026-03-25'}
        data = resolve_inline(normalized(p))
        self.assertEqual(len(data.bars), 4)
        self.assertEqual(data.metadata['warmup_bars']['trade_data'], 1)
        result = run_engine(data.bars, lambda c: FixedSignal('BUY', 1) if c.portfolio.position is None else None,
                            initial_cash=10000, fee_rate=0, slippage_rate=0,
                            record_start=data.start_date, trade_start=data.start_date)
        self.assertEqual(result.fills[0].fill_date, data.bars[2].trading_date)
        self.assertEqual(len(result.equity_history), 3)
        p['trade_data']['bars'][-1].update(open='9999', high='9999', low='9999', close='9999')
        self.assertEqual(resolve_inline(normalized(p)), data)
        delayed = normalized(payload())
        delayed['trade_data']['bars'][0]['available_at'] = delayed['trade_data']['bars'][0]['time'] + 301
        delayed_data = resolve_inline(delayed)
        with self.assertRaisesRegex(ValueError, 'PRIMARY_AVAILABILITY_DELAY_UNSUPPORTED'):
            run_engine(delayed_data.bars, lambda c: None, initial_cash=1000, fee_rate=0, slippage_rate=0)

    def test_contract_rollover_gap_flags_and_calendar_failures(self):
        p = payload()
        p['trade_data']['contract_map'] = sample()['trade_data']['contract_map']
        p['trade_data']['bars'] = [candle(datetime(2026, 3, 19, 14, 25, tzinfo=ZONE)),
                                  candle(datetime(2026, 3, 20, 9, tzinfo=ZONE)),
                                  candle(datetime(2026, 3, 20, 9, 10, tzinfo=ZONE))]
        policy = json.loads(Path('docs/data/vn30f1m/runtime-policy-v1.json').read_bytes())
        data = resolve_inline(normalized(p), policy)
        self.assertEqual([b.contract_code for b in data.bars], ['VN30F2603', 'VN30F2604', 'VN30F2604'])
        self.assertTrue(data.bars[-1].data_gap_before)
        self.assertIn('2026-03-20T09:05:00+07:00', data.metadata['data_gaps']['trade_data'])
        for change in (lambda q: q['trade_data']['contract_map'].pop(2),
                       lambda q: q['trade_data'].update(contract_map=q['trade_data']['contract_map'][:2]),
                       lambda q: q['trade_data']['bars'][0].update(time=int(datetime(2026, 3, 19, 12, tzinfo=ZONE).timestamp()))):
            q = deepcopy(p)
            change(q)
            with self.assertRaises(ValueError): resolve_inline(normalized(q), policy)
