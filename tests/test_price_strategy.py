"""Verify the price-only B slice with fixed sources and independently calculated fills."""
from copy import deepcopy
from datetime import date, datetime, timedelta
from decimal import Decimal as D
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from uuid import UUID
from zoneinfo import ZoneInfo
from fastapi.testclient import TestClient
from pydantic import ValidationError
from backtesting_api.api.app import create_app
from backtesting_api.api.price_schemas import PriceRunRequest
from backtesting_api.application.inline_data import InlineData, InputBar
from backtesting_api.application.price_strategy import run_price_strategy
from backtesting_api.application.run_backtest import BacktestService, _warmup_bars
from backtesting_api.domain.expressions import MissingValue, evaluate_expression
from backtesting_api.domain.price_portfolio import PriceBook
from backtesting_api.infrastructure.file_repository import FileRunRepository


ZONE = ZoneInfo('Asia/Ho_Chi_Minh')
POLICY = json.loads(Path('docs/data/vn30f1m/runtime-policy-v1.json').read_bytes())


def request(**updates):
    """Create a minimal price-only strategy whose conditions remain controllable."""
    value = {'symbol': 'VN30F1M', 'entry': {'long': {'left': 'price', 'op': 'above', 'right': 0}},
             'exit': {'long': {'left': 'price', 'op': 'above', 'right': 110}}}
    value.update(updates)
    return value


def bars(prices, start=None):
    """Build explicit synthetic candles with Open/Close availability five minutes apart."""
    start = start or datetime(2026, 4, 1, 9, tzinfo=ZONE)
    result = []
    for index, prices_for_bar in enumerate(prices):
        opened = start + timedelta(minutes=5 * index)
        o, h, l, c = map(D, prices_for_bar)
        result.append(InputBar(opened, o, h, l, c, D(1), close_time=opened + timedelta(minutes=5),
                               available_at=opened + timedelta(minutes=5)))
    return tuple(result)


def run(value, rows, market=()):
    """Run the same compiled request as the API against fixed source facts."""
    data = InlineData(rows, market, rows[0].trading_date.date(), rows[-1].trading_date.date(), {'data_gaps': {}})
    sources = {'trade_data': {'resolution': '5'}, 'market_data': {'resolution': '5'} if market else None}
    return run_price_strategy(data, PriceRunRequest.model_validate(value).compiled(), sources, POLICY)


class PriceTermsTest(unittest.TestCase):
    """Guard alias ownership, short condition parsing and causal crossing samples."""
    def test_aliases_ranges_and_precise_history(self):
        """Use fixed alias periods, inclusive bounds and enough prior crossing samples."""
        p = request(entry={'long': {'all': [
            {'left': 'market.price', 'op': 'cross_up', 'right': {'ref': 'market.sma20', 'shift': 2}},
            {'ref': 'market.mfi14', 'min': 55, 'max': 80}]}}, warmup_bars=150)
        spec = PriceRunRequest.model_validate(p).compiled()
        self.assertEqual(spec['indicators']['market_sma20']['source'], 'market_data.close')
        self.assertEqual(spec['indicators']['market_mfi14']['source'], 'market_data')
        self.assertEqual(spec['required_history'], 150)
        spec['warmup_bars'] = 0
        self.assertEqual(_warmup_bars(spec), 23)
        self.assertEqual(spec['entry']['LONG']['order'], {'type': 'IMMEDIATE'})

    def test_rejects_unknown_fields_refs_shifts_and_boolean_quantities(self):
        """Reject malformed client intent before fetching or evaluating source data."""
        invalid = [request(quantity=True), request(quantity='2'), request(from_='bad'),
                   request(entry={'long': {'left': 'sma21', 'op': 'above', 'right': 0}}),
                   request(entry={'long': {'gt': [{'ref': 'trade_data.close', 'shift': -1}, 0]}}),
                   request(entry={'long': {'all': []}}),
                   request(entry={'long': {'ref': 'price', 'min': 80, 'max': 55}}),
                   request(entry={'long': {'left': 'position.entry_price', 'op': 'above', 'right': 0}}),
                   request(exit={'allow_overnight': True}), request(trade_data={}),
                   request(entry={'long': True}), request(risk={'sl': True}),
                   request(order={'type': 'IMMEDIATE', 'limit_price': 100}),
                   request(entry={'long': {'gt': [1, 0]}, 'signal_windows': [[1, 2]]})]
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(ValidationError):
                PriceRunRequest.model_validate(value)

    def test_bounds_limit_work_before_expansion(self):
        """Reject deeply nested and oversized trees instead of recursing unchecked."""
        node = {'left': 'price', 'op': 'above', 'right': 0}
        for _ in range(34):
            node = {'all': [node]}
        for condition in (node, {'all': [{'gt': [1, 0]}] * 4097}):
            with self.assertRaises(ValidationError):
                PriceRunRequest.model_validate(request(entry={'long': condition}))

    def test_crossing_equality_missing_sample_and_state_rejection(self):
        """Compare previous source samples, including equality at the prior sample."""
        expression = {'cross_up': [{'ref': 'x'}, {'ref': 'y'}]}
        self.assertTrue(evaluate_expression(expression, {'x': [D(1), D(3)], 'y': [D(1), D(2)]}))
        self.assertFalse(evaluate_expression(expression, {'x': [D(1), D(2)], 'y': [D(1), D(2)]}))
        self.assertTrue(evaluate_expression({'cross_down': expression['cross_up']}, {'x': [D(2), D(0)], 'y': [D(2), D(1)]}))
        with self.assertRaises(MissingValue):
            evaluate_expression(expression, {'x': [D(3)], 'y': [D(1), D(2)]})
        with self.assertRaises(MissingValue):
            evaluate_expression(expression, {'x': D(3), 'y': D(2)})
        with self.assertRaises(ValueError):
            evaluate_expression({'cross_up': [{'ref': 'day.net_pnl'}, 0]}, {'day.net_pnl': D(1)})

    def test_delayed_market_cross_uses_two_distinct_available_samples(self):
        """A delayed market candle cannot affect earlier decisions or act as two samples."""
        trade = bars([('100', '101', '99', '100')] * 4)
        market = bars([('99', '101', '98', '99'), ('101', '102', '100', '101')])
        market = (market[0], type(market[1])(**{**market[1].__dict__, 'available_at': trade[2].closed_at}))
        p = request(entry={'long': {'left': 'market.price', 'op': 'cross_up', 'right': 100}})
        result = run(p, trade, market)
        self.assertEqual(result['fills'][0]['fill_time'], trade[2].closed_at)
        self.assertEqual(result['evaluations'][0]['status'], 'UNEVALUABLE')


class PriceBookTest(unittest.TestCase):
    """Reconcile the new book with the independent part-A arithmetic oracle."""
    def test_long_partial_and_short_exact_values(self):
        """Keep realized legs out of the remaining position's mark."""
        book = PriceBook()
        book.open('p1', 'LONG', '100', 3)
        self.assertEqual(book.close('106', 1), D(6))
        self.assertEqual(book.mark('103'), {'realized_pnl': D(6), 'unrealized_pnl': D(6), 'total_pnl': D(12)})
        with self.assertRaises(ValueError):
            book.close('103', 3)
        self.assertEqual(book.position.remaining_quantity, 2)
        book.close('103', 2)
        book.open('p2', 'SHORT', '100', 2)
        self.assertEqual(book.close('97', 2), D(6))
        self.assertEqual(book.realized_pnl, D(18))


class PriceRuntimeTest(unittest.TestCase):
    """Check order lifetimes, execution times, partial exits and no future leakage."""
    def test_immediate_open_and_close_both_directions(self):
        """All four actions fill at their decision Close instead of next Open."""
        rows = bars([('100', '101', '99', '100'), ('90', '115', '89', '112')])
        for side in ('long', 'short'):
            p = request(entry={side: {'gt': [1, 0]}}, exit={side: {'gt': [{'ref': 'position.held_bars'}, 1]}})
            result = run(p, rows)
            self.assertEqual([f['price'] for f in result['fills']], [D(100), D(112)])
            self.assertEqual([f['fill_time'] for f in result['fills']], [b.closed_at for b in rows])
            self.assertEqual([f['side'] for f in result['fills']], ['BUY', 'SELL'] if side == 'long' else ['SELL', 'BUY'])
            self.assertEqual(result['summary']['total_pnl'], D(12) if side == 'long' else D(-12))

    def test_lo_matches_third_bar_and_never_fourth(self):
        """Keep the original limit through exactly three observed execution bars."""
        p = request(order={'type': 'LO', 'limit_price': 98}, entry={'long': {'lt': [{'ref': 'day.entry_fill_count'}, 1]}})
        rows = bars([('100', '101', '99', '100')] * 3 + [('100', '101', '98', '100')])
        result = run(p, rows)
        self.assertEqual(result['orders'][0]['execution_bars'], 3)
        self.assertEqual(result['fills'][0]['price'], D(98))
        self.assertEqual(result['fills'][0]['fill_phase'], 'intrabar_assumed')
        never = run(p, bars([('100', '101', '99', '100')] * 4 + [('97', '100', '96', '100')]))
        self.assertEqual(never['orders'][0]['status'], 'EXPIRED')
        self.assertEqual(never['orders'][0]['reason'], 'MAX_EXECUTION_BARS')
        self.assertFalse(any(f['order_id'] == 'o1' for f in never['fills']))

    def test_lo_better_open_buy_sell_and_end_report(self):
        """Respect both directions and expire an order with no execution candle left."""
        rows = bars([('100', '101', '99', '100'), ('97', '101', '96', '100')])
        for side, limit, expected in [('long', 98, D(97)), ('short', 96, D(97))]:
            p = request(entry={side: {'gt': [1, 0]}}, exit={side: {'gt': [0, 1]}}, order={'type': 'LO', 'limit_price': limit})
            result = run(p, rows)
            self.assertEqual(result['fills'][0]['price'], expected)
            self.assertEqual(result['fills'][0]['fill_phase'], 'open')
            self.assertEqual(run(p, rows[:1])['orders'][0]['reason'], 'END_OF_REPORT')

    def test_all_part_a_lo_price_cases_match_the_engine(self):
        """Run all six independent BUY/SELL price examples through the new engine."""
        fixture = json.loads(Path('tests/fixtures/price-only-cases.json').read_bytes())
        for case in fixture['lo_cases']:
            side = 'long' if case['side'] == 'BUY' else 'short'
            p = request(entry={side: {'gt': [1, 0]}}, exit={side: {'gt': [0, 1]}},
                        order={'type': 'LO', 'limit_price': float(case['limit'])})
            result = run(p, bars([('100', '101', '99', '100'), tuple(case['bar'])]))
            with self.subTest(case=case['id']):
                if case['expected_price'] is None:
                    self.assertFalse(result['fills'])
                else:
                    self.assertEqual(result['fills'][0]['price'], D(case['expected_price']))

    def test_market_gap_prevents_stale_entry_and_resets_crossing_history(self):
        """A known unavailable market slot cannot be treated as a passed condition."""
        trade = bars([('100', '101', '99', '100')] * 3)
        market = bars([('101', '102', '100', '101')])
        p = request(entry={'long': {'gt': [{'ref': 'market_data.close'}, 100]}}, warmup_bars=2)
        data = InlineData(trade, market, date(2026, 4, 1), date(2026, 4, 1),
                          {'data_gaps': {'market_data': [trade[1].trading_date.isoformat()]}})
        spec = PriceRunRequest.model_validate(p).compiled()
        result = run_price_strategy(data, spec, {'trade_data': {'resolution': '5'}, 'market_data': {'resolution': '5'}}, POLICY)
        self.assertFalse(result['fills'])
        self.assertEqual(result['evaluations'][-1]['status'], 'UNEVALUABLE')
        self.assertIn('DATA_GAP', result['evaluations'][-1]['reason'])
        from dataclasses import replace
        fresh = bars([('99', '100', '98', '99'), ('101', '102', '100', '101')])
        fresh = (fresh[0], replace(fresh[1], data_gap_before=True))
        p = request(entry={'long': {'left': 'market.price', 'op': 'cross_up', 'right': 100}})
        self.assertFalse(run(p, trade, fresh)['fills'])

    def test_missing_volume_is_unevaluable_without_invented_values(self):
        """MFI waits for actual volume samples, leaving a flat strategy unevaluable."""
        rows = bars([('100', '101', '99', '100')] * 16)
        from dataclasses import replace
        rows = tuple(replace(bar, volume=None) for bar in rows)
        p = request(entry={'long': {'left': 'mfi14', 'op': 'above', 'right': 0}})
        result = run(p, rows)
        self.assertFalse(result['fills'])
        self.assertEqual(result['evaluations'][-1]['status'], 'UNEVALUABLE')

    def test_lunch_does_not_count_and_day_boundary_expires(self):
        """Do not synthesize lunch candles or let the next day's Open match an order."""
        first = bars([('100', '101', '99', '100')], datetime(2026, 4, 1, 11, 20, tzinfo=ZONE))
        after = bars([('100', '101', '99', '100'), ('97', '101', '96', '100')], datetime(2026, 4, 1, 13, tzinfo=ZONE))
        p = request(order={'type': 'LO', 'limit_price': 98})
        result = run(p, first + after)
        self.assertEqual(result['orders'][0]['execution_bars'], 2)
        tomorrow = bars([('97', '101', '96', '100')], datetime(2026, 4, 2, 9, tzinfo=ZONE))
        result = run(p, first + tomorrow)
        self.assertEqual(result['orders'][0]['reason'], 'END_OF_DAY')
        self.assertFalse(any(f['order_id'] == 'o1' for f in result['fills']))

    def test_partial_close_and_close_only_protection(self):
        """Ignore wicks for protection and use the actual overflowing Close."""
        rows = bars([('100', '101', '90', '100'), ('100', '115', '93', '103'), ('103', '104', '89', '90')])
        p = request(quantity=3, risk={'sl': 6, 'tp': 12}, exit={'long': {
            'condition': {'gt': [{'ref': 'position.held_bars'}, 1]}, 'quantity': 1}})
        result = run(p, rows)
        self.assertEqual([f['quantity'] for f in result['fills']], [3, 1, 2])
        self.assertEqual(result['fills'][-1]['price'], D(90))
        self.assertEqual(result['trades'][-1]['reason'], 'STOP_LOSS')
        self.assertEqual(result['summary']['total_pnl'], D(-17))
        waiting = request(entry={'long': {'condition': {'gt': [1, 0]}, 'order': {'type': 'IMMEDIATE'}}},
                          exit={'long': {'condition': {'gt': [1, 0]}, 'order': {'type': 'LO', 'limit_price': 110}}},
                          risk={'sl': 6})
        protected = run(waiting, rows)
        self.assertEqual(protected['orders'][1]['status'], 'CANCELED')
        self.assertEqual(protected['orders'][1]['reason'], 'POSITION_CHANGED')
        self.assertEqual(protected['trades'][-1]['reason'], 'STOP_LOSS')

    def test_no_reentry_conflict_and_no_open_at_end_of_day(self):
        """A same-Close exit cannot reopen; the final session Close cannot open a new position."""
        rows = bars([('100', '101', '99', '100')] * 3)
        result = run(request(exit={'long': {'gt': [1, 0]}}), rows)
        self.assertEqual(len(result['fills']), 3)
        conflict = request(entry={'long': {'gt': [1, 0]}, 'short': {'gt': [1, 0]}}, risk={'sl': 6})
        self.assertEqual(run(conflict, rows)['evaluations'][0]['reason'], 'SIGNAL_CONFLICT')
        final = run(request(), bars([('100', '101', '99', '100')], datetime(2026, 4, 1, 14, 25, tzinfo=ZONE)))
        self.assertFalse(final['fills'])
        self.assertEqual(final['evaluations'][-1]['reason'], 'END_OF_DAY')

    def test_full_and_truncated_source_have_identical_prefix_events(self):
        """Changing future candles cannot change fills or marks already decided."""
        rows = bars([('100', '101', '99', '100'), ('102', '106', '101', '105'), ('99', '113', '98', '112')])
        p = request()
        full, prefix = run(p, rows), run(p, rows[:2])
        self.assertEqual(full['fills'][:1], prefix['fills'])
        self.assertEqual(full['pnl_history'][:3], prefix['pnl_history'])
        self.assertEqual(full['evaluations'][:2], prefix['evaluations'])
        self.assertEqual(full['signals'][:1], prefix['signals'])


class PriceApiTest(unittest.TestCase):
    """Exercise validation, source snapshots and schema-3 persistence through FastAPI."""
    def setUp(self):
        """Use a fixed fetcher and a disposable local-only repository."""
        self.temporary = tempfile.TemporaryDirectory(dir='.agents')
        self.addCleanup(self.temporary.cleanup)
        self.repository = FileRunRepository(Path(self.temporary.name))
        rows = bars([('100', '101', '99', '100'), ('102', '113', '101', '112')])
        self.sources = {'trade_data': {'symbol': 'VN30F1M', 'resolution': '5', 'bars': [
            {'time': int(b.trading_date.timestamp()), **{key: str(getattr(b, key)) for key in ('open', 'high', 'low', 'close')}} for b in rows]}}
        self.metadata = {'from': int(rows[0].trading_date.timestamp()), 'to': int(rows[-1].closed_at.timestamp()),
                         'provider': 'fixed-test-source', 'fetched_at': rows[-1].closed_at.isoformat()}
        self.fetcher = Mock()
        self.fetcher.fetch.side_effect = lambda: (deepcopy(self.sources), deepcopy(self.metadata))
        self.fetcher.fetch_by_range.side_effect = lambda *a, **k: (deepcopy(self.sources), deepcopy(self.metadata))
        self.service = BacktestService(self.repository, data_fetcher=self.fetcher)
        self.client = TestClient(create_app(self.service))

    def test_post_validate_get_restart_and_replay_use_identical_pinned_sources(self):
        """Return config-only validation and preserve exact results after reopening the store."""
        value = request()
        checked = self.client.post('/api/backtests/validate', json=value)
        self.assertEqual(checked.status_code, 200, checked.text)
        self.assertEqual(checked.json()['payload'], value)
        with patch('backtesting_api.application.inline_strategy.ContractAccounting', side_effect=AssertionError('old accounting')):
            created = self.client.post('/api/backtests', json=value)
        self.assertEqual(created.status_code, 201, created.text)
        result = created.json()
        self.assertEqual(result['summary']['total_pnl'], '12')
        self.assertNotIn('initial_cash', result['metadata'])
        run_id = UUID(result['metadata']['run_id'])
        restarted = FileRunRepository(self.repository.store)
        self.assertEqual(restarted.get_run(run_id), result)
        snapshot = restarted.get_input(run_id)
        self.assertEqual(snapshot['schema_version'], 2)
        self.assertEqual(snapshot['payload']['request'], value)
        self.assertEqual(self.client.get(f'/api/backtests/{run_id}/chart').status_code, 200)
        self.assertEqual(self.client.get('/api/backtests/history').status_code, 200)
        p = snapshot['payload']
        from backtesting_api.application.price_strategy import resolve_price_data
        from backtesting_api.application.inline_results import exact_json
        data = resolve_price_data(p['sources'], p['request'], snapshot['policy'], snapshot['data_metadata']['auto_fetch'])
        replay = exact_json(run_price_strategy(data, p['effective_config'], p['sources'], snapshot['policy']))
        self.assertEqual(replay['fills'], result['fills'])
        self.assertEqual(replay['summary'], result['summary'])
        source_path = self.repository.store / 'inputs' / (result['metadata']['input_hash'] + '.json')
        source_path.write_bytes(source_path.read_bytes() + b' ')
        self.assertEqual(self.client.get(f'/api/backtests/{run_id}').status_code, 409)

    def test_report_range_uses_alias_and_cross_history_for_fetching(self):
        """Fetch both dates and the full crossing lookback without receiving candles."""
        value = request(**{'from': '2026-04-01', 'to': '2026-04-01'},
                        entry={'long': {'left': 'price', 'op': 'cross_up', 'right': 'sma20'}})
        response = self.client.post('/api/backtests/validate', json=value)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.fetcher.fetch_by_range.call_args.kwargs['warmup_bars'], 21)

    def test_validation_rejects_invalid_protection_and_missing_calendar(self):
        """Validation and running share capability checks and fail before creating a run."""
        for endpoint in ('/api/backtests', '/api/backtests/validate'):
            response = self.client.post(endpoint, json=request(risk={'trailing': 6, 'trailing_after_tp1': 6}))
            self.assertEqual(response.status_code, 422)
            self.assertIn('INVALID_RISK', response.text)
        self.assertFalse((self.repository.store / 'runs').exists())
        with patch('backtesting_api.application.price_strategy._session_gaps', side_effect=ValueError('CALENDAR_REQUIRED')):
            self.assertEqual(self.client.post('/api/backtests/validate', json=request()).status_code, 422)
