"""Verify scheduled daily liquidation without synthetic prices or future candles."""
from copy import deepcopy
from datetime import datetime
from decimal import Decimal as D
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock
from uuid import UUID
from fastapi.testclient import TestClient
from backtesting_api.api.app import create_app
from backtesting_api.api.price_schemas import PriceRunRequest
from backtesting_api.application.inline_data import InlineData
from backtesting_api.application.price_strategy import run_price_strategy
from backtesting_api.application.run_backtest import BacktestService
from backtesting_api.application.strategy_parameters import strategy_parameters
from backtesting_api.infrastructure.file_repository import FileRunRepository
from test_price_strategy import POLICY, ZONE, bars, request, run


class PriceEndOfDayTest(unittest.TestCase):
    """Exercise both directions, pending orders and the observed session boundary."""
    def test_long_and_short_close_all_at_the_scheduled_close(self):
        """Liquidate the remaining quantity at the real final continuous candle Close."""
        rows = bars([('100', '101', '99', '100'), ('100', '103', '99', '102')],
                    datetime(2026, 4, 1, 14, 20, tzinfo=ZONE))
        for side, pnl in [('long', D(6)), ('short', D(-6))]:
            value = request(quantity=3, entry={side: {'gt': [1, 0]}}, exit={side: {'gt': [0, 1]}})
            result = run(value, rows)
            with self.subTest(side=side):
                self.assertEqual([fill['quantity'] for fill in result['fills']], [3, 3])
                self.assertEqual(result['fills'][-1]['price'], D(102))
                self.assertEqual(result['fills'][-1]['fill_time'], rows[-1].closed_at)
                self.assertEqual(result['trades'][-1]['reason'], 'END_OF_DAY')
                self.assertEqual(result['evaluations'][-1]['reason'], 'END_OF_DAY')
                self.assertIsNone(result['open_position'])
                self.assertEqual(result['summary']['realized_pnl'], pnl)
                self.assertEqual(result['summary']['unrealized_pnl'], D(0))
                self.assertEqual(result['summary']['closed_positions'], 1)

    def test_partial_target_leaves_only_the_remaining_quantity_to_liquidate(self):
        """Do not realize a previously closed target leg again at day end."""
        rows = bars([('100', '101', '99', '100'), ('100', '107', '99', '106'),
                     ('106', '109', '105', '108')], datetime(2026, 4, 1, 14, 15, tzinfo=ZONE))
        value = request(quantity=3, exit={}, risk={'targets': [
            {'pct': 6, 'quantity': 1}, {'pct': 12, 'quantity': 'remaining'}]})
        result = run(value, rows)
        self.assertEqual([trade['quantity'] for trade in result['trades']], [1, 2])
        self.assertEqual([trade['reason'] for trade in result['trades']], ['TP1', 'END_OF_DAY'])
        self.assertEqual(result['summary']['total_pnl'], D(22))
        self.assertEqual(len({trade['position_id'] for trade in result['trades']}), 1)

    def test_unfilled_lo_exit_expires_before_forced_close(self):
        """A pending strategy limit cannot postpone or duplicate the daily liquidation."""
        rows = bars([('100', '101', '99', '100')] * 3, datetime(2026, 4, 1, 14, 15, tzinfo=ZONE))
        value = request(order={'type': 'LO', 'limit_price': 120},
                        entry={'long': {'condition': {'gt': [1, 0]}, 'order': {'type': 'IMMEDIATE'}}},
                        exit={'long': {'gt': [1, 0]}})
        result = run(value, rows)
        self.assertEqual(result['orders'][1]['status'], 'EXPIRED')
        self.assertEqual(result['orders'][1]['reason'], 'END_OF_DAY')
        self.assertEqual(result['orders'][-1]['type'], 'IMMEDIATE')
        self.assertEqual(result['orders'][-1]['reason'], 'END_OF_DAY')
        self.assertEqual(len(result['fills']), 2)

    def test_pending_entry_expires_and_final_close_does_not_open(self):
        """Do not create a new position or refresh an unfilled order at session end."""
        rows = bars([('100', '101', '99', '100')] * 2, datetime(2026, 4, 1, 14, 20, tzinfo=ZONE))
        result = run(request(order={'type': 'LO', 'limit_price': 90}), rows)
        self.assertEqual(len(result['orders']), 1)
        self.assertEqual(result['orders'][0]['reason'], 'END_OF_DAY')
        self.assertFalse(result['fills'])
        self.assertFalse(run(request(), rows[-1:])['orders'])

    def test_final_candle_can_fill_existing_lo_then_close_without_duplicate_fills(self):
        """An entry before the boundary may fill inside its last candle, then close at its Close."""
        rows = bars([('101', '102', '101', '101'), ('99', '102', '98', '101')],
                    datetime(2026, 4, 1, 14, 20, tzinfo=ZONE))
        result = run(request(order={'type': 'LO', 'limit_price': 100}), rows)
        self.assertEqual([fill['price'] for fill in result['fills']], [D(99), D(101)])
        self.assertEqual(result['fills'][0]['fill_time'], rows[-1].trading_date)
        self.assertEqual(result['fills'][1]['fill_time'], rows[-1].closed_at)
        self.assertEqual(result['summary']['total_pnl'], D(2))
        value = request(entry={'long': {'condition': {'gt': [1, 0]}, 'order': {'type': 'IMMEDIATE'}}},
                        exit={'long': {'condition': {'gt': [1, 0]}, 'order': {'type': 'LO', 'limit_price': 100}}})
        three = bars([('100', '101', '99', '100')] * 3, datetime(2026, 4, 1, 14, 15, tzinfo=ZONE))
        already_closed = run(value, three)
        self.assertEqual(len(already_closed['fills']), 2)
        self.assertEqual(already_closed['trades'][0]['reason'], 'EXIT')

    def test_day_end_close_needs_only_the_actual_trade_close(self):
        """Liquidation must not depend on an unavailable strategy exit indicator."""
        rows = bars([('100', '101', '99', '100')] * 2, datetime(2026, 4, 1, 14, 20, tzinfo=ZONE))
        value = request(exit={'long': {'left': 'market.price', 'op': 'below', 'right': 0}})
        result = run(value, rows)
        self.assertEqual(result['trades'][-1]['reason'], 'END_OF_DAY')
        self.assertIsNone(result['open_position'])

    def test_daily_close_is_causal_and_does_not_close_an_intraday_cutoff(self):
        """The end of a truncated dataset is not evidence that the session has ended."""
        today = bars([('100', '101', '99', '100'), ('100', '103', '99', '102')],
                     datetime(2026, 4, 1, 14, 20, tzinfo=ZONE))
        tomorrow = bars([('110', '111', '109', '110')], datetime(2026, 4, 2, 9, tzinfo=ZONE))
        value = request(exit={'long': {'gt': [0, 1]}})
        full, prefix, intraday = run(value, today + tomorrow), run(value, today), run(value, today[:1])
        self.assertEqual(full['fills'][:2], prefix['fills'])
        self.assertEqual(full['pnl_history'][:3], prefix['pnl_history'])
        self.assertEqual(full['signals'][:2], prefix['signals'])
        self.assertEqual(len(intraday['fills']), 1)
        self.assertEqual(intraday['summary']['open_positions'], 1)
        self.assertEqual(prefix, run(value, today))

    def test_missing_final_candle_cannot_use_the_next_days_price(self):
        """Fail instead of backdating a close to an absent session-end candle."""
        today = bars([('100', '101', '99', '100')], datetime(2026, 4, 1, 14, 20, tzinfo=ZONE))
        tomorrow = bars([('110', '111', '109', '110')], datetime(2026, 4, 2, 9, tzinfo=ZONE))
        with self.assertRaisesRegex(ValueError, 'MISSING_POSITION_EXECUTION_BAR'):
            run(request(), today + tomorrow)
        data = InlineData(today, (), today[0].trading_date.date(), today[0].trading_date.date(), {
            'auto_fetch': {'to': int(today[0].closed_at.timestamp()) + 300},
            'data_gaps': {'trade_data': [today[0].closed_at.isoformat()]}})
        with self.assertRaisesRegex(ValueError, 'MISSING_POSITION_EXECUTION_BAR'):
            run_price_strategy(data, PriceRunRequest.model_validate(request()).compiled(),
                               {'trade_data': {'resolution': '5'}, 'market_data': None}, POLICY)

    def test_old_pinned_configuration_keeps_its_original_end_day_behavior(self):
        """Replay old policy without silently adding the newly approved closing rule."""
        rows = bars([('100', '101', '99', '100')] * 2, datetime(2026, 4, 1, 14, 20, tzinfo=ZONE))
        spec = PriceRunRequest.model_validate(request()).compiled()
        spec.pop('session_end_action', None)
        spec['default_profile_version'] = 'price-only-v1'
        data = InlineData(rows, (), rows[0].trading_date.date(), rows[0].trading_date.date(), {'data_gaps': {}})
        with self.assertRaisesRegex(ValueError, 'REQUIRED_EXIT_NOT_FILLED'):
            run_price_strategy(data, spec, {'trade_data': {'resolution': '5'}, 'market_data': None}, POLICY)

    def test_earlier_explicit_flat_by_remains_a_required_strategy_deadline(self):
        """Daily liquidation does not reinterpret an explicitly earlier exit constraint."""
        rows = bars([('100', '101', '99', '100')], datetime(2026, 4, 1, 14, 20, tzinfo=ZONE))
        with self.assertRaisesRegex(ValueError, 'REQUIRED_EXIT_NOT_FILLED'):
            run(request(exit={'long': {'gt': [0, 1]}, 'flat_by': '14:25'}), rows)

    def test_catalog_default_sample_runs_to_day_end_and_replays_from_saved_inputs(self):
        """The opening-page sample succeeds through the public API on a complete test session."""
        rows = tuple(bar for label in POLICY['sessions']['trade_data']['required_times']
                     if label < '14:30' for bar in bars([('100', '101', '99', '100')],
                         datetime.fromisoformat('2026-04-01T' + label).replace(tzinfo=ZONE)))
        rows = tuple(type(bar)(**{**bar.__dict__, 'close': D(100) + D(index) / 100})
                     for index, bar in enumerate(rows))
        sources = {'trade_data': {'symbol': 'VN30F1M', 'resolution': '5', 'bars': [
            {'time': int(bar.trading_date.timestamp()), **{key: str(getattr(bar, key))
             for key in ('open', 'high', 'low', 'close')}} for bar in rows]}}
        metadata = {'from': int(rows[0].trading_date.timestamp()), 'to': int(rows[-1].closed_at.timestamp()),
                    'provider': 'SYNTHETIC_END_DAY_TEST', 'fetched_at': rows[-1].closed_at.isoformat()}
        fetcher = Mock()
        fetcher.fetch.side_effect = lambda: (deepcopy(sources), deepcopy(metadata))
        with tempfile.TemporaryDirectory(dir='.agents') as temporary:
            repository = FileRunRepository(Path(temporary))
            service = BacktestService(repository, data_fetcher=fetcher)
            client = TestClient(create_app(service))
            value = strategy_parameters()['examples'][0]['payload']
            checked = client.post('/api/backtests/validate', json=value)
            self.assertEqual(checked.status_code, 200, checked.text)
            self.assertEqual(checked.json()['effective_config']['session_end_action'], 'close_at_close')
            response = client.post('/api/backtests', json=value)
            self.assertEqual(response.status_code, 201, response.text)
            result = response.json()
            self.assertEqual(result['trades'][-1]['reason'], 'END_OF_DAY')
            self.assertIsNone(result['open_position'])
            run_id = UUID(result['metadata']['run_id'])
            replay = BacktestService(FileRunRepository(Path(temporary))).replay_price(run_id)
            self.assertEqual(replay['fills'], result['fills'])
            self.assertEqual(replay['summary'], result['summary'])
