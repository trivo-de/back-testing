"""Legacy internal order regressions with simulated liquidity, not market acceptance."""
from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal as D
from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch
from uuid import UUID
from fastapi.testclient import TestClient

from legacy_inline_app import legacy_inline_app
from backtesting_api.application.inline_data import resolve_inline
from backtesting_api.application.inline_results import inline_result_to_dict
from backtesting_api.application.inline_strategy import InlineExecution, run_inline_strategy
from backtesting_api.application.run_backtest import BacktestService
from backtesting_api.domain.engine import run_engine
from backtesting_api.domain.execution import ContractExecution, InvalidExecution
from backtesting_api.domain.matching import Match
from backtesting_api.domain.multi_execution import MultiContractExecution
from backtesting_api.domain.orders import OrderRequest
from backtesting_api.domain.trading import FixedSignal
from backtesting_api.infrastructure.file_repository import FileRunRepository
from test_contract_execution import ACCOUNTING
from test_inline_pipeline import candle, normalized
from test_session_matching import DAY, POLICY, session_payload


def market_payload(kind='MTL', cap=2, side='LONG'):
    p = session_payload(side=side)
    p['execution'].pop('entry_fill_policy')
    p['execution']['continuous_match_quantity'] = cap
    entry = p['strategy']['entry']
    entry.pop('limit_price')
    entry['order'] = {'type': kind}
    if kind in ('MTL', 'LO'):
        entry['order']['pending'] = {'max_execution_bars': 4, 'cross_lunch': False,
                                     'cross_cutoff': False, 'cross_session': False}
    if kind == 'LO': entry['order']['limit_price'] = {'add': [1000, 0]}
    p['strategy']['sizing'].update(max_contracts=5, risk_fraction='0.5')
    p['strategy']['exit'] = {'bar_close': {
        'conditions': {'EXIT': {'gte': [{'ref': 'clock.local_time'}, '18:00']}},
        'any': ['EXIT'], 'priority': ['EXIT'], 'quantity': 'remaining', 'order': {'type': 'SIMULATED'}}}
    p['trade_data']['bars'] = [candle(DAY + timedelta(minutes=5*i)) for i in range(6)]
    p['trade_data']['price_limits'] = [{
        'trading_date': DAY.date().isoformat(), 'contract_code': 'VN30F2604',
        'floor_price': '900', 'ceiling_price': '1100',
        'available_at': int(DAY.replace(hour=8, minute=45).timestamp()), 'source': 'synthetic fixed bounds'}]
    return p


def execute(p):
    p = normalized(p)
    data = resolve_inline(p, POLICY)
    return run_inline_strategy(data, p)


class MarketOrdersTest(unittest.TestCase):
    def test_documented_market_example_runs_without_fetching(self):
        path = Path(__file__).parents[1]/'docs/examples/orders/market-fixed.json'
        result = execute(json.loads(path.read_text(encoding='utf-8')))
        self.assertEqual([f.quantity for f in result.fills], [2, 2, 1, 2, 2])
        self.assertEqual(result.portfolio.position.quantity, 1)

    def test_session_boundaries_cancel_remainder_and_no_match_crosses_lunch(self):
        for label, hour, minute in (('LUNCH', 11, 20), ('BEFORE_ATC', 14, 20)):
            p = market_payload()
            start = DAY.replace(hour=hour, minute=minute)
            p['trade_data']['bars'] = [candle(start), candle(start+timedelta(minutes=5))]
            stamp = (start+timedelta(minutes=5)).strftime('%H:%M')
            p['strategy']['entry']['conditions']['LONG'] = {'all': [
                {'gte': [{'ref': 'clock.local_time'}, stamp]}, {'lte': [{'ref': 'clock.local_time'}, stamp]}]}
            result = execute(p)
            self.assertEqual([f.quantity for f in result.fills], [2])
            self.assertEqual((result.orders[0].reason, result.orders[0].canceled_quantity), (label, 3))
        p = market_payload('MOK', 0)
        p['trade_data']['bars'] = [candle(DAY.replace(hour=11, minute=20)), candle(DAY.replace(hour=11, minute=25)),
                                   candle(DAY.replace(hour=13, minute=0))]
        p['strategy']['entry']['conditions']['LONG'] = {'gte': [{'ref': 'clock.local_time'}, '11:30']}
        p['strategy']['entry']['signal_windows'] = [['09:05', '11:30']]
        result = execute(p)
        self.assertEqual(result.fills, ())

    def test_missing_execution_bar_invalid_price_and_future_limits_fail(self):
        p = market_payload()
        p['trade_data']['bars'].pop(1)
        with self.assertRaisesRegex(InvalidExecution, 'MISSING_PENDING_EXECUTION_BAR'): execute(p)
        for value in ('1000.01', '1101'):
            p = market_payload('MAK', 0)
            p['trade_data']['bars'][1].update(open=value, close=value, high='1102', low='999')
            with self.assertRaisesRegex(ValueError, 'INVALID_MARKET_MATCH_PRICE'): execute(p)
        p = market_payload()
        p['trade_data']['price_limits'][0]['available_at'] = 10**100
        with self.assertRaisesRegex(ValueError, 'INVALID_PRICE_LIMITS'): execute(p)

    def test_partial_close_and_weighted_basis_serialize_all_entry_links(self):
        p = market_payload()
        p['trade_data']['bars'][2].update(open='1000.1', high='1001', low='999', close='1000')
        p['strategy']['exit']['bar_close'].update(
            conditions={'EXIT': {'gte': [{'ref': 'clock.local_time'}, '09:20']}}, order={'type': 'MAK'})
        result = execute(p)
        prepared = normalized(p)
        response = inline_result_to_dict(UUID(int=3), resolve_inline(prepared, POLICY), result,
                                         input_hash='i', policy_hash='p', accounting=p['accounting'])
        self.assertEqual(response['trades'][0]['entry_price'], '1000.04')
        self.assertEqual(len(response['trades'][0]['entry_fill_ids']), 3)
        self.assertEqual(response['open_position']['quantity'], 1)
        self.assertEqual(sum(t.net_pnl for t in result.trades), result.portfolio.realized_pnl)
        p['strategy']['exit']['bar_close']['order'] = {'type': 'SIMULATED'}
        result = execute(p)
        closing = next(o for o in result.orders if o.side == 'CLOSE')
        self.assertEqual((closing.quantity, closing.filled_quantity, closing.remaining_quantity), (5, 5, 0))

    def test_api_storage_reload_chart_and_pinned_replay(self):
        with tempfile.TemporaryDirectory(dir='.agents') as temporary:
            repo = FileRunRepository(Path(temporary), Path(temporary)/'unused.json')
            service = BacktestService(repo, inline_runner=run_inline_strategy)
            client = TestClient(legacy_inline_app(service))
            for kind in ('MTL', 'MAK', 'MOK'):
                p = market_payload(kind)
                response = client.post('/internal-test/legacy/backtests', json=p)
                self.assertEqual(response.status_code, 201, response.text)
                result = response.json()
                run_id = UUID(result['metadata']['run_id'])
                self.assertEqual(service.get(run_id), result)
                pinned = service.get_input(run_id)
                original_pinned = deepcopy(pinned)
                data = resolve_inline(deepcopy(pinned['payload']), pinned['policy'])
                with patch('backtesting_api.infrastructure.auto_fetch_data.AutoDataFetcher.fetch', side_effect=AssertionError('refetch')):
                    replay = inline_result_to_dict(run_id, data, run_inline_strategy(data, pinned['payload']),
                        input_hash=result['metadata']['input_hash'], policy_hash=result['metadata']['policy_hash'],
                        accounting=pinned['payload']['accounting'])
                replay['metadata']['run_at'] = result['metadata']['run_at']
                self.assertEqual(replay, result)
                self.assertEqual(service.get_input(run_id), original_pinned)
                self.assertEqual(result['metadata']['continuous_match_quantity'], 2)
                self.assertEqual(len(service.get_chart(run_id)['bars']), 6)
                order = result['orders'][0]
                self.assertEqual(order['quantity'], sum(order[k] for k in
                    ('filled_quantity', 'expired_quantity', 'canceled_quantity', 'rejected_quantity', 'remaining_quantity')))
                self.assertEqual(order['fill_ids'], [f['fill_id'] for f in result['fills']])
                if kind == 'MTL':
                    self.assertEqual([f['order_type'] for f in result['fills']], ['MTL', 'LO', 'LO'])
                    self.assertEqual(len(result['open_position']['entry_fill_ids']), 3)

    def test_protection_cancels_open_remainder_and_later_margin_failure_keeps_fills(self):
        p = market_payload()
        p['strategy']['exit'] = session_payload()['strategy']['exit']
        p['trade_data']['bars'][1]['high'] = '1007'
        result = execute(p)
        self.assertEqual([f.quantity for f in result.fills], [2, 2])
        self.assertEqual(result.orders[0].canceled_quantity, 3)
        self.assertIsNone(result.portfolio.position)
        p = market_payload(side='SHORT')
        p['initial_cash'] = '100000000'
        p['trade_data']['price_limits'][0]['ceiling_price'] = '5000'
        for row in p['trade_data']['bars'][2:]: row.update(open='4000', high='4001', low='3999', close='4000')
        result = execute(p)
        self.assertEqual([f.quantity for f in result.fills], [2])
        self.assertEqual(result.orders[0].rejected_quantity, 3)
        self.assertEqual(result.portfolio.position.quantity, 2)

    def test_multi_continuation_has_one_daily_entry_and_no_double_reservation(self):
        p = market_payload()
        p['strategy']['sizing']['pyramiding'] = True
        p['strategy']['entry']['priority'] = ['LONG']
        p['strategy']['daily_limits'] = {'stop_new_entry': {'gte': [{'ref': 'day.entry_fill_count'}, 2]}}
        result = execute(p)
        self.assertEqual([f.quantity for f in result.fills], [2, 2, 1])
        self.assertEqual({f.position_id for f in result.fills}, {'LONG:1'})
        self.assertFalse(any(e['reason'] == 'DAILY_ENTRY_LIMIT' for e in result.evaluations))
        self.assertEqual(result.portfolio.quantity, 5)

    def test_same_bar_budget_is_shared_and_account_rejection_preserves_it(self):
        p = normalized(market_payload())
        data = resolve_inline(p, POLICY)
        def provider(context):
            if len(context.bars) == 1:
                return (FixedSignal('LONG', 3, position_id='A', order=OrderRequest('MOK')),
                        FixedSignal('LONG', 2, position_id='B', order=OrderRequest('MAK')))
        cash = D(45000000)
        executor = MultiContractExecution(cash, lambda amount: ContractExecution(amount, ACCOUNTING))
        result = run_engine(data.bars, provider, initial_cash=cash, fee_rate=0, slippage_rate=0,
                            matching_model='hnx_sessions_v1', execution=lambda amount: executor,
                            continuous_match_quantity=5, price_limits=data.price_limits)
        self.assertEqual([f.position_id for f in result.fills], ['B'])
        self.assertEqual(result.orders[0].reason, 'INSUFFICIENT_MARGIN_AFTER_COSTS')

    def test_mak_mok_matrix_and_no_retry_both_directions(self):
        for side in ('LONG', 'SHORT'):
            for kind in ('MAK', 'MOK'):
                for cap in (0, 2, 5):
                    with self.subTest(side=side, kind=kind, cap=cap):
                        result = execute(market_payload(kind, cap, side))
                        order = result.orders[0]
                        filled = min(cap, 5) if kind == 'MAK' or cap >= 5 else 0
                        self.assertEqual((order.quantity, order.filled_quantity, order.canceled_quantity), (5, filled, 5-filled))
                        self.assertEqual(sum(f.quantity for f in result.fills), filled)
                        self.assertEqual(order.remaining_quantity, 0)
                        self.assertEqual(order.expired_quantity, 0)
                        if not filled: self.assertEqual(result.portfolio.fees, 0)

    def test_mtl_and_lo_multiple_fills_keep_one_order(self):
        for side in ('LONG', 'SHORT'):
            for kind in ('MTL', 'LO'):
                with self.subTest(side=side, kind=kind):
                    p = market_payload(kind, side=side)
                    result = execute(p)
                    self.assertEqual([f.quantity for f in result.fills], [2, 2, 1])
                    order = result.orders[0]
                    self.assertEqual((order.quantity, order.filled_quantity, order.status), (5, 5, 'FILLED'))
                    self.assertEqual(order.fill_indices, (0, 1, 2))
                    self.assertEqual(len(result.orders), 1)
                    self.assertEqual(result.portfolio.position.quantity, 5)
                    if kind == 'MTL':
                        self.assertEqual(order.order_type, 'MTL')
                        self.assertEqual(order.effective_order_type, 'LO')
                        self.assertEqual(order.converted_limit_price, D('1000.1' if side == 'LONG' else '999.9'))
                        self.assertEqual(result.fills[1].fill_date, DAY + timedelta(minutes=10))
                    self.assertEqual(result, execute(p))

    def test_mtl_zero_has_no_limit_and_mtl_does_not_reuse_conversion_bar(self):
        result = execute(market_payload(cap=0))
        self.assertEqual(result.fills, ())
        self.assertIsNone(result.orders[0].converted_limit_price)
        p = market_payload()
        p['trade_data']['bars'] = p['trade_data']['bars'][:2]
        result = execute(p)
        self.assertEqual([f.quantity for f in result.fills], [2])
        self.assertEqual(result.orders[0].expired_quantity, 3)

    def test_closing_market_orders_are_reduce_only(self):
        for side in ('LONG', 'SHORT'):
            for kind in ('MTL', 'MAK', 'MOK'):
                p = market_payload('LO', 2, side)
                p['strategy']['exit']['bar_close'].update(
                    conditions={'EXIT': {'gte': [{'ref': 'clock.local_time'}, '09:20']}}, order={'type': kind})
                result = execute(p)
                closing = next(o for o in result.orders if o.side == 'CLOSE')
                expected = 0 if kind == 'MOK' else 4 if kind == 'MTL' else 2
                self.assertEqual(closing.filled_quantity, expected)
                self.assertLessEqual(sum(t.quantity for t in result.trades), 5)
                self.assertTrue(result.portfolio.position is None or result.portfolio.position.direction == side)

    def test_margin_failure_does_not_resize_or_charge(self):
        p = market_payload('MOK', 5)
        p['initial_cash'] = '100000000'
        p['strategy']['sizing']['max_contracts'] = 5
        p['trade_data']['price_limits'][0]['ceiling_price'] = '5000'
        for row in p['trade_data']['bars'][1:]:
            row.update(open='4000', high='4001', low='3999', close='4000')
        result = execute(p)
        self.assertEqual(result.orders[0].reason, 'INSUFFICIENT_MARGIN_AFTER_COSTS')
        self.assertEqual(result.orders[0].quantity, 5)
        self.assertEqual(result.orders[0].rejected_quantity, 5)
        self.assertEqual(result.fills, ())
        self.assertEqual(result.portfolio.cash, D('100000000'))

    def test_invalid_limits_models_and_quantities_fail(self):
        p = market_payload()
        for change, message in ((lambda x: x['trade_data'].pop('price_limits'), 'MISSING_PRICE_LIMITS'),
                                 (lambda x: x['execution'].pop('continuous_match_quantity'), 'MARKET_ORDER_REQUIRES_MATCH_QUANTITY'),
                                 (lambda x: x['execution'].update(matching_model='next_open'), 'ORDER_UNSUPPORTED_BY_MATCHING_MODEL'),
                                 (lambda x: x['execution'].update(continuous_match_quantity=True), 'integer'),
                                 (lambda x: x['trade_data']['price_limits'][0].update(floor_price='900.01'), 'INVALID_PRICE_LIMITS'),
                                 (lambda x: x['trade_data']['price_limits'][0].update(contract_code='WRONG'), 'INVALID_PRICE_LIMITS'),
                                 (lambda x: x['trade_data']['price_limits'][0].update(available_at=int(DAY.timestamp())+1), 'INVALID_PRICE_LIMITS')):
            bad = deepcopy(p)
            change(bad)
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message): execute(bad)

    def test_shared_budget_mok_failure_leaves_quantity_for_later_order(self):
        p = normalized(market_payload())
        data = resolve_inline(p, POLICY)
        def provider(context):
            if len(context.bars) == 1:
                return (FixedSignal('LONG', 3, position_id='A', order=OrderRequest('MOK')),
                        FixedSignal('LONG', 2, position_id='B', order=OrderRequest('MAK')))
        executor = MultiContractExecution(D(500000000), lambda cash: ContractExecution(cash, ACCOUNTING))
        result = run_engine(data.bars, provider, initial_cash=500000000, fee_rate=0, slippage_rate=0,
                            matching_model='hnx_sessions_v1', execution=lambda cash: executor,
                            continuous_match_quantity=2, price_limits=data.price_limits)
        self.assertEqual([f.position_id for f in result.fills], ['B'])
        self.assertEqual([o.filled_quantity for o in result.orders], [0, 2])

    def test_open_and_close_share_budget_and_partial_entry_reserves_only_remainder(self):
        p = normalized(market_payload())
        data = resolve_inline(p, POLICY)
        def run(provider, cap):
            executor = MultiContractExecution(D(500000000), lambda cash: ContractExecution(cash, ACCOUNTING))
            return run_engine(data.bars, provider, initial_cash=500000000, fee_rate=0, slippage_rate=0,
                              matching_model='hnx_sessions_v1', execution=lambda cash: executor,
                              continuous_match_quantity=cap, price_limits=data.price_limits)
        def simultaneous(context):
            if len(context.bars) == 1:
                return (FixedSignal('LONG', 2, position_id='touch', order=OrderRequest('LO', D(999))),
                        FixedSignal('LONG', 2, position_id='open', order=OrderRequest('MAK')))
        result = run(simultaneous, 2)
        self.assertEqual([(f.position_id, f.quantity) for f in result.fills], [('open', 2)])
        def reserved(context):
            if len(context.bars) == 1:
                return FixedSignal('LONG', 5, position_id='A', order=OrderRequest('LO', D(1000), 4))
            if len(context.bars) == 2:
                self.assertEqual(sum(s.quantity for s in context.pending_signals), 3)
                return FixedSignal('LONG', 3, position_id='B', order=OrderRequest('MAK'))
        result = run(reserved, 2)
        self.assertEqual(result.orders[1].reason, 'MAX_CONTRACTS_RESERVED')
        self.assertEqual([f.quantity for f in result.fills], [2, 2, 1])

    def test_future_changes_do_not_resize_or_change_completed_events(self):
        p = market_payload('MAK')
        original = execute(p)
        future = deepcopy(p)
        future['trade_data']['bars'][-1].update(high='1008', close='1008')
        changed = execute(future)
        truncated = deepcopy(p)
        truncated['trade_data']['bars'] = truncated['trade_data']['bars'][:3]
        for result in (changed, execute(truncated)):
            self.assertEqual(result.orders, original.orders)
            self.assertEqual(result.fills, original.fills)

    def test_out_of_range_match_aborts_before_accounting(self):
        p = normalized(market_payload('MAK'))
        data = resolve_inline(p, POLICY)
        executor = InlineExecution(p['initial_cash'], p)
        with patch('backtesting_api.domain.session_matching.match_continuous',
                   return_value=Match(D(1000), data.bars[1].trading_date, 6, data.bars[1].trading_date)):
            with self.assertRaisesRegex(InvalidExecution, 'MATCH_RESPONSE_OUT_OF_RANGE'):
                run_engine(data.bars, lambda c: FixedSignal('LONG', order=OrderRequest('MAK')) if len(c.bars)==1 else None,
                           initial_cash=p['initial_cash'], fee_rate=0, slippage_rate=0,
                           matching_model='hnx_sessions_v1', execution=lambda cash: executor,
                           continuous_match_quantity=2, price_limits=data.price_limits)
        self.assertIsNone(executor.portfolio.position)


if __name__ == '__main__':
    unittest.main()
