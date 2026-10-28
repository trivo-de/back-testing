"""Legacy internal engine/normalization/storage regressions; production POST accepts only price-only requests."""
from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
import tempfile
import unittest
from uuid import UUID

from fastapi.testclient import TestClient

from legacy_inline_app import legacy_inline_app
from backtesting_api.api.inline_schemas import InlineRunRequest
from backtesting_api.application.inline_strategy import run_inline_strategy
from backtesting_api.application.inline_data import resolve_inline
from backtesting_api.application.inline_results import inline_result_to_dict
from backtesting_api.application.run_backtest import BacktestService
from backtesting_api.infrastructure.file_repository import FileRunRepository
from test_order_strategy import execute, modern
from test_session_matching import DAY, session_payload
from test_inline_pipeline import candle
from test_inline_pipeline import normalized
from test_session_matching import POLICY


def multi_payload():
    p = modern(session_payload())
    p['strategy']['sizing'].update(pyramiding=True, max_contracts=5, risk_fraction='0.004')
    entry = p['strategy']['entry']
    condition = entry['conditions']['LONG']
    action = entry['actions']['LONG']
    entry.update(conditions={'A': deepcopy(condition), 'B': deepcopy(condition)},
                 actions={'A': deepcopy(action), 'B': deepcopy(action)}, any=['A', 'B'], priority=['A', 'B'])
    p['strategy']['exit']['bar_close'] = {
        'conditions': {'TIME': {'gte': [{'ref': 'position.held_bars'}, 2]}},
        'any': ['TIME'], 'priority': ['TIME'], 'quantity': 'remaining', 'order': {'type': 'SIMULATED'}}
    return p


class MultiStrategyTest(unittest.TestCase):
    def test_mixed_lot_evaluations_count_one_time_and_report_partial_status(self):
        p = normalized(multi_payload())
        data = resolve_inline(p, POLICY)
        result = execute(p)
        stamp = data.bars[-1].closed_at
        result = replace(result, evaluations=(
            {'time': stamp, 'position_id': 'A:1', 'status': 'UNEVALUABLE'},
            {'time': stamp, 'position_id': 'B:2', 'status': 'EVALUABLE'}))
        response = inline_result_to_dict(UUID(int=1), data, result, input_hash='input', policy_hash='policy',
                                         accounting=p['accounting'])
        self.assertEqual(response['evaluation_status'],
                         {'status': 'PARTIALLY_EVALUABLE', 'evaluated_bars': 0, 'unevaluable_bars': 1})
        self.assertEqual(len(response['evaluations']), 2)

    def test_each_entry_keeps_its_own_price_and_hold_clock(self):
        p = multi_payload()
        p['strategy']['entry']['conditions']['B'] = {'all': [
            {'gte': [{'ref': 'clock.local_time'}, '09:10']},
            {'lte': [{'ref': 'clock.local_time'}, '09:10']}]}
        p['strategy']['entry']['actions']['B']['order']['limit_price'] = {'add': [1002, 0]}
        p['trade_data']['bars'] = [candle(DAY), candle(DAY + timedelta(minutes=5)),
                                  *[candle(DAY + timedelta(minutes=5*i), opened='1002', high='1003', low='1001', close='1002')
                                    for i in range(2, 5)]]
        result = execute(p)
        self.assertEqual([trade.entry_price for trade in result.trades], [1000, 1002])
        self.assertEqual([trade.exit_date.strftime('%H:%M') for trade in result.trades], ['09:15', '09:20'])
        self.assertEqual([trade.quantity for trade in result.trades], [3, 2])

    def test_daily_fill_counter_is_shared_across_lots(self):
        p = multi_payload()
        for name in ('A', 'B'):
            p['strategy']['entry']['conditions'][name] = {'gte': [{'ref': 'clock.local_time'}, '09:05']}
        p['strategy']['daily_limits'] = {'stop_new_entry': {'gte': [{'ref': 'day.entry_fill_count'}, 2]}}
        result = execute(p)
        self.assertEqual(len([s for s in result.signals if s.side == 'LONG']), 2)
        self.assertTrue(any(row['reason'] == 'DAILY_ENTRY_LIMIT' for row in result.evaluations))

    def test_api_persists_multiple_positions_and_trade_links(self):
        with tempfile.TemporaryDirectory(dir='.agents') as temporary:
            repo = FileRunRepository(Path(temporary), Path(temporary) / 'unused.json')
            service = BacktestService(repo, inline_runner=run_inline_strategy)
            client = TestClient(legacy_inline_app(service))
            p = multi_payload()
            response = client.post('/internal-test/legacy/backtests', json=p)
            self.assertEqual(response.status_code, 201, response.text)
            result = response.json()
            run_id = UUID(result['metadata']['run_id'])
            self.assertEqual(service.get(run_id), result)
            self.assertEqual(result['open_positions'], [])
            fills = {fill['fill_id']: fill for fill in result['fills']}
            for trade in result['trades']:
                self.assertEqual(trade['position_id'], fills[trade['entry_fill_id']]['position_id'])
                self.assertEqual(trade['position_id'], fills[trade['exit_fill_id']]['position_id'])
            self.assertEqual(service.get_input(run_id)['payload']['strategy']['entry']['priority'], ['A', 'B'])
            pinned = service.get_input(run_id)
            data = resolve_inline(deepcopy(pinned['payload']), pinned['policy'])
            replay = inline_result_to_dict(run_id, data, run_inline_strategy(data, pinned['payload']),
                                          input_hash=result['metadata']['input_hash'],
                                          policy_hash=result['metadata']['policy_hash'], accounting=pinned['payload']['accounting'])
            replay['metadata']['run_at'] = result['metadata']['run_at']
            self.assertEqual(replay, result)
            status = result['evaluation_status']
            self.assertEqual(status['evaluated_bars'] + status['unevaluable_bars'],
                             len({row['time'] for row in result['evaluations']}))
            self.assertGreater(len(result['evaluations']), status['evaluated_bars'])
            self.assertEqual(len(service.get_chart(run_id)['bars']), 4)
            p['strategy']['exit'].pop('bar_close')
            response = client.post('/internal-test/legacy/backtests', json=p)
            self.assertEqual(response.status_code, 201, response.text)
            opened = response.json()['open_positions']
            self.assertEqual([lot['quantity'] for lot in opened], [3, 2])
            self.assertTrue(all('active_stop' in lot['strategy_details'] for lot in opened))

    def test_priority_two_entries_and_per_lot_exit(self):
        p = multi_payload()
        result = execute(p)
        self.assertEqual([fill.quantity for fill in result.fills], [3, 2, 3, 2])
        self.assertEqual([fill.position_id for fill in result.fills], ['A:1', 'B:2', 'A:1', 'B:2'])
        self.assertEqual(result.portfolio.quantity, 0)
        self.assertEqual(result, execute(p))
        p['strategy']['entry']['priority'] = ['B', 'A']
        reversed_result = execute(p)
        self.assertEqual([fill.position_id for fill in reversed_result.fills[:2]], ['B:1', 'A:2'])
        self.assertEqual([fill.quantity for fill in reversed_result.fills[:2]], [3, 2])

    def test_rejects_incompatible_multi_flags_and_order_types(self):
        for mutate, message in (
                (lambda p: p['strategy']['entry'].pop('priority'), 'MISSING_CONFLICT_POLICY'),
                (lambda p: p['strategy']['entry'].update(require_flat=True), 'CONFLICTING_SINGLE_POSITION_FLAGS'),
                (lambda p: p['strategy']['entry'].update(require_no_pending=True), 'CONFLICTING_SINGLE_POSITION_FLAGS'),
                (lambda p: p['strategy']['entry']['actions']['A'].update(order={'type': 'SIMULATED'}), 'REQUIRES_SESSION_LO_OR_ATO'),
                (lambda p: p['execution'].update(matching_model='next_open'), 'REQUIRES_SESSION_LO_OR_ATO')):
            p = multi_payload()
            mutate(p)
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                InlineRunRequest.model_validate(p)
        p = modern(session_payload())
        p['strategy']['entry']['require_flat'] = False
        with self.assertRaisesRegex(ValueError, 'FLAGS_REQUIRE_PYRAMIDING'):
            InlineRunRequest.model_validate(p)


if __name__ == '__main__':
    unittest.main()
