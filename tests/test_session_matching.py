'Legacy internal engine/normalization/storage regressions; production POST accepts only price-only requests. Synthetic session tests; these do not establish acceptance of market ATC data.'
from copy import deepcopy
from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta
from decimal import Decimal as D
import json
from pathlib import Path
import tempfile
import unittest
from uuid import UUID
from fastapi.testclient import TestClient
from legacy_inline_app import legacy_inline_app
from backtesting_api.api.inline_schemas import InlineRunRequest
from backtesting_api.application.inline_data import resolve_inline
from backtesting_api.application.inline_strategy import run_inline_strategy
from backtesting_api.application.run_backtest import BacktestService
from backtesting_api.domain.session_matching import phase_at
from backtesting_api.infrastructure.file_repository import FileRunRepository
from test_inline_pipeline import ZONE, candle, normalized, payload

POLICY = json.loads(Path('docs/data/vn30f1m/runtime-policy-v1.json').read_bytes())
DAY = datetime(2026, 3, 25, 9, tzinfo=ZONE)


def full_day():
    return [candle(DAY.replace(hour=m // 60, minute=m % 60))
            for lo, hi in ((540, 690), (780, 870)) for m in range(lo, hi, 5)]


def session_payload(*, side='LONG', limit=1000, atc=False):
    p = payload()
    p['initial_cash'] = '500000000'
    p['execution'].update(matching_model='hnx_sessions_v1', entry_fill_policy='limit')
    p['trade_data'].update(
        bars=full_day() if atc else [candle(DAY + timedelta(minutes=5*i)) for i in range(4)],
        contract_dates=[{'date': '2026-03-25', 'contract_code': 'VN30F2604'}],
        provenance={'provider': 'synthetic test', 'timestamp_convention': 'bar_open', 'note': 'Synthetic OHLC only.'})
    p['strategy']['entry'] = {'conditions': {side: {'all': [
        {'gte': [{'ref': 'clock.local_time'}, '09:05']}, {'lte': [{'ref': 'clock.local_time'}, '09:05']}]}},
                              'any': [side], 'limit_price': {'add': [float(limit), 0]},
                              'signal_windows': [['09:05', '14:25']]}
    p['strategy']['sizing']['max_contracts'] = 1
    p['strategy']['exit'] = {
        'targets': {side: {'TP1': {'add' if side == 'LONG' else 'sub': [{'ref': 'position.entry_price'}, 6]}}},
        'intrabar': {'conditions': {
            'STOP': {'type': 'protective_stop', 'distance_points': 6, 'quantity': 'remaining'},
            'TP1': {'type': 'target_touch', 'level': 'TP1', 'quantity': 'remaining'}},
            'any': ['STOP', 'TP1'], 'priority': ['STOP', 'TP1']}}
    if atc:
        p['strategy']['exit'].update(allow_overnight=False, flat_by='14:45', bar_close={
            'conditions': {'CLOSE_ATC': {'gte': [{'ref': 'clock.local_time'}, '14:30']}},
            'any': ['CLOSE_ATC'], 'priority': ['CLOSE_ATC'], 'quantity': 'remaining', 'fill_policy': 'atc'})
        stamp = int(DAY.replace(hour=14, minute=45).timestamp())
        p['trade_data']['auctions'] = [{'contract_code': 'VN30F2604', 'match_time': stamp,
                                      'available_at': stamp+2, 'status': 'matched', 'price': '1002',
                                      'source': 'synthetic confirmed auction fixture'}]
    return p


def ato_payload(match_quantity=None, side='LONG'):
    p = session_payload(side=side)
    previous = DAY - timedelta(days=1)
    p['trade_data']['bars'] = [candle(previous.replace(hour=14, minute=25)), *full_day()]
    p['trade_data']['contract_dates'] = [
        {'date': previous.date().isoformat(), 'contract_code': 'VN30F2604'},
        {'date': DAY.date().isoformat(), 'contract_code': 'VN30F2604'},
    ]
    p['report'] = {'start_date': DAY.date().isoformat(), 'end_date': DAY.date().isoformat()}
    p['execution']['entry_fill_policy'] = 'ato'
    if match_quantity is not None: p['execution']['auction_match_quantity'] = match_quantity
    p['strategy']['entry'].update(
        conditions={side: {'all': [
            {'gte': [{'ref': 'clock.local_time'}, '08:45']},
            {'lte': [{'ref': 'clock.local_time'}, '08:45']}]}},
        any=[side], signal_windows=[['08:45', '08:55']])
    p['strategy']['entry'].pop('limit_price')
    p['strategy']['sizing']['max_contracts'] = 5
    return p


def run(p):
    p = normalized(p)
    return run_inline_strategy(resolve_inline(p, POLICY), p)


class SessionMatchingTest(unittest.TestCase):
    def test_phase_boundaries(self):
        expected = {'08:44': 'CLOSED', '08:45': 'ATO', '09:00': 'CONTINUOUS_AM',
                    '11:30': 'LUNCH', '13:00': 'CONTINUOUS_PM', '14:30': 'ATC', '14:45': 'CLOSED'}
        for label, phase in expected.items():
            hour, minute = map(int, label.split(':'))
            self.assertEqual(phase_at(DAY.replace(hour=hour, minute=minute)), phase)

    def test_lo_open_improvement_both_directions_without_volume(self):
        for side, limit in [('LONG', 1001), ('SHORT', 999)]:
            result = run(session_payload(side=side, limit=limit))
            self.assertEqual(result.fills[0].price, 1000)
            self.assertEqual(result.fills[0].fill_date, DAY + timedelta(minutes=5))
            self.assertEqual(result.orders[0].quantity, 1)

    def test_intrabar_entry_defers_targets_and_keeps_stop(self):
        for side, limit, high, low, target in [('LONG', '999.5', '1007', '999', '1005.5'),
                                               ('SHORT', '1000.5', '1001', '993', '994.5')]:
            p = session_payload(side=side, limit=limit)
            for row in p['trade_data']['bars'][1:3]: row.update(high=high, low=low)
            result = run(p)
            self.assertEqual(result.fills[0].fill_date, DAY + timedelta(minutes=10))
            self.assertEqual(result.fills[0].bar_time, DAY + timedelta(minutes=5))
            self.assertEqual(result.fills[1].price, D(target))
            self.assertEqual(result.fills[1].fill_date, DAY + timedelta(minutes=15))
        p = session_payload(limit=999)
        p['trade_data']['bars'][1].update(low='990', high='1007')
        result = run(p)
        self.assertEqual([f.price for f in result.fills], [999, 993])
        self.assertEqual(result.signals[-1].reason, 'STOP_LOSS')
        self.assertEqual(result.fills[0].fill_date, result.fills[1].fill_date)

    def test_lo_waits_then_expires_without_replacing_pending(self):
        p = session_payload(limit=990)
        p['strategy']['entry']['pending'] = {'max_execution_bars': 3, 'cross_lunch': False,
                                            'cross_cutoff': False, 'cross_session': False}
        result = run(p)
        self.assertEqual(len(result.orders), 1)
        self.assertEqual(result.orders[0].status, 'EXPIRED')
        self.assertEqual(result.orders[0].reason, 'MAX_EXECUTION_BARS')
        self.assertEqual(result.orders[0].events[-1]['time'], DAY + timedelta(minutes=20))
        self.assertEqual(result.evaluations[1]['reason'], 'ORDER_PENDING')
        self.assertEqual(result.fills, ())
        missing = deepcopy(p)
        missing['trade_data']['bars'].pop(1)
        with self.assertRaisesRegex(ValueError, 'MISSING_PENDING_EXECUTION_BAR'):
            run(missing)

    def test_lo_closes_both_directions_and_protective_exit_cancels_waiting_lo(self):
        for side, limit, price in [('LONG', 1002, '1003'), ('SHORT', 998, '997')]:
            p = session_payload(side=side)
            p['execution']['entry_fill_policy'] = 'next_open'
            p['strategy']['entry'].pop('limit_price')
            p['strategy']['exit']['bar_close'] = {
                'conditions': {'LIMIT_CLOSE': {'gte': [{'ref': 'clock.local_time'}, '09:10']}},
                'any': ['LIMIT_CLOSE'], 'priority': ['LIMIT_CLOSE'], 'quantity': 'remaining',
                'fill_policy': 'limit', 'limit_price': {'add': [limit, 0]}}
            p['trade_data']['bars'][2].update(open=price, high=str(int(price)+1), low=str(int(price)-1), close=price)
            result = run(p)
            self.assertEqual(result.fills[-1].price, D(price))
            self.assertEqual(result.orders[-1].order_type, 'LO')
            self.assertIsNone(result.portfolio.position)
        p = session_payload()
        p['strategy']['entry']['pending'] = {'max_execution_bars': 3, 'cross_lunch': False,
                                            'cross_cutoff': False, 'cross_session': False}
        p['strategy']['exit']['bar_close'] = {
            'conditions': {'WAITING_CLOSE': {'gte': [{'ref': 'clock.local_time'}, '09:10']}},
            'any': ['WAITING_CLOSE'], 'priority': ['WAITING_CLOSE'], 'quantity': 'remaining',
            'fill_policy': 'limit', 'limit_price': {'add': [1010, 0]}}
        p['trade_data']['bars'][2].update(high='1007')
        result = run(p)
        self.assertEqual([o.status for o in result.orders], ['FILLED', 'CANCELED', 'FILLED'])
        self.assertEqual(result.orders[1].reason, 'POSITION_CHANGED')
        from backtesting_api.application.inline_results import inline_result_to_dict
        result_json = inline_result_to_dict(UUID(int=1), resolve_inline(normalized(p), POLICY), result,
                                            input_hash='i', policy_hash='p', accounting=p['accounting'])
        self.assertEqual(result_json['trades'][0]['exit_fill_id'], result_json['fills'][1]['fill_id'])

    def test_next_open_close_across_lunch_keeps_existing_timing(self):
        p = session_payload()
        p['trade_data']['bars'] = full_day()
        p['strategy']['entry']['conditions']['LONG'] = {'all': [
            {'gte': [{'ref': 'clock.local_time'}, '11:20']}, {'lte': [{'ref': 'clock.local_time'}, '11:20']}]}
        p['strategy']['exit']['bar_close'] = {
            'conditions': {'LUNCH_CLOSE': {'gte': [{'ref': 'clock.local_time'}, '11:30']}},
            'any': ['LUNCH_CLOSE'], 'priority': ['LUNCH_CLOSE'], 'quantity': 'remaining', 'fill_policy': 'next_open'}
        result = run(p)
        self.assertEqual(result.fills[-1].fill_date.strftime('%H:%M'), '13:00')
        self.assertIsNone(result.portfolio.position)

    def test_lo_cancellation_before_lunch_and_atc(self):
        for signal_time, final_time, reason in [('11:20', '11:30', 'LUNCH'), ('14:20', '14:30', 'BEFORE_ATC')]:
            p = session_payload(limit=990)
            p['trade_data']['bars'] = full_day()
            p['strategy']['entry']['conditions']['LONG']['all'][0]['gte'][1] = signal_time
            p['strategy']['entry']['conditions']['LONG']['all'][1]['lte'][1] = signal_time
            p['strategy']['entry']['pending'] = {'max_execution_bars': 99, 'cross_lunch': False,
                                                'cross_cutoff': False, 'cross_session': False}
            result = run(p)
            self.assertEqual(result.orders[0].status, 'CANCELED')
            self.assertEqual(result.orders[0].reason, reason)
            self.assertEqual(result.orders[0].events[-1]['time'].strftime('%H:%M'), final_time)
            self.assertTrue(result.orders[0].events[-1]['phase'].startswith('CONTINUOUS'))

    def test_fixed_quantity_rechecks_margin_without_resizing(self):
        p = session_payload(side='SHORT')
        p['initial_cash'] = '15000000'
        p['strategy']['sizing'].update(risk_fraction='0.1', margin_buffer='1.1')
        p['accounting']['margin_rate'] = '0.1'
        p['trade_data']['bars'][1].update(open='2000', high='2001', low='1999', close='2000')
        result = run(p)
        self.assertEqual(result.orders[0].quantity, 1)
        self.assertEqual(result.orders[0].reason, 'INSUFFICIENT_MARGIN_AFTER_COSTS')
        self.assertEqual(result.fills, ())

    def test_atc_closes_at_confirmed_price_and_keeps_auction_out_of_indicators(self):
        p = session_payload(atc=True)
        p['trade_data']['bars'].insert(0, candle(DAY.replace(hour=8, minute=45), '500', '501', '499', '500'))
        result = run(p)
        self.assertEqual([f.price for f in result.fills], [1000, 1002])
        self.assertEqual(result.fills[-1].fill_date.strftime('%H:%M'), '14:45')
        self.assertEqual(result.orders[-1].signal_date.strftime('%H:%M'), '14:30')
        self.assertEqual(result.orders[-1].order_type, 'ATC')
        self.assertEqual(result.orders[-1].quantity, 1)
        self.assertIsNone(result.portfolio.position)
        self.assertEqual(len(result.evaluations), 48)
        self.assertEqual(result.summary.final_equity, D(p['initial_cash']) + 200000 - result.portfolio.fees)
        self.assertEqual(result, run(p))
        short = run(session_payload(side='SHORT', atc=True))
        self.assertEqual(short.fills[-1].direction, 'SHORT')
        self.assertEqual(short.summary.final_equity, D(p['initial_cash']) - 200000 - short.portfolio.fees)

    def test_atc_freezes_remaining_quantity_after_partial_profit_exit(self):
        p = session_payload(atc=True)
        p['strategy']['sizing']['max_contracts'] = 3
        p['strategy']['exit']['intrabar']['conditions']['TP1']['quantity'] = {
            'if_initial_quantity_eq': 1, 'then': 'remaining',
            'else': {'floor': [{'div': [{'ref': 'position.initial_quantity'}, 2]}]}}
        p['trade_data']['bars'][2].update(high='1007')
        result = run(p)
        self.assertEqual([f.quantity for f in result.fills], [3, 1, 2])
        self.assertEqual(result.orders[-1].quantity, 2)
        self.assertIsNone(result.portfolio.position)

    def test_ato_full_partial_and_zero_fill_keep_order_quantity(self):
        for cap, filled, expired, status in [(None, 5, 0, 'FILLED'), (2, 2, 3, 'EXPIRED'), (0, 0, 5, 'EXPIRED')]:
            p = ato_payload(cap)
            result = run(p)
            order = result.orders[0]
            self.assertEqual((order.quantity, order.filled_quantity, order.expired_quantity,
                              order.remaining_quantity, order.status), (5, filled, expired, 0, status))
            self.assertEqual(sum(fill.quantity for fill in result.fills), filled)
            self.assertEqual(result.portfolio.position.quantity if result.portfolio.position else 0, filled)
            self.assertEqual(result.portfolio.fees > 0, filled > 0)
            self.assertEqual(order.events[-1]['time'].strftime('%H:%M'), '09:00')
            self.assertEqual(order.events[-1]['phase'], 'ATO')
            if cap == 2:
                self.assertEqual([event['status'] for event in order.events],
                                 ['submitted', 'partially_filled', 'expired'])
                with self.assertRaises(FrozenInstanceError): order.quantity = 1
                self.assertEqual(result, run(ato_payload(cap)))
                from backtesting_api.application.inline_results import inline_result_to_dict
                data = resolve_inline(normalized(deepcopy(p)), POLICY)
                result_json = inline_result_to_dict(UUID(int=2), data, result, input_hash='i', policy_hash='p',
                                                    accounting=p['accounting'])
                self.assertEqual(result_json['orders'][0]['status'], 'expired')
                self.assertEqual(result_json['orders'][0]['filled_quantity'], 2)
                self.assertEqual(result_json['fills'][0]['order_type'], 'ATO')
                self.assertEqual(result_json['fills'][0]['source'], 'synthetic test')
                self.assertEqual(result_json['open_position']['quantity'], 2)
                future = ato_payload(cap)
                future['trade_data']['bars'][1].update(open='1200', high='1201', low='1199', close='1200')
                changed = run(future)
                self.assertEqual(changed.signals[0], result.signals[0])
                self.assertEqual(changed.orders[0].quantity, result.orders[0].quantity)
                self.assertEqual(changed.evaluations[0], result.evaluations[0])
        short = run(ato_payload(2, 'SHORT'))
        self.assertEqual((short.fills[0].direction, short.fills[0].quantity,
                          short.portfolio.position.quantity), ('SHORT', 2, 2))

    def test_atc_uses_1445_close_and_partial_remainder_expires(self):
        p = session_payload(atc=True)
        p['trade_data']['auctions'] = []
        p['trade_data']['bars'].append(candle(DAY.replace(hour=14, minute=45), '1001', '1003', '1000', '1002'))
        p['execution']['auction_match_quantity'] = 2
        p['strategy']['sizing']['max_contracts'] = 5
        p['strategy']['exit'].pop('allow_overnight')
        result = run(p)
        order = result.orders[-1]
        self.assertEqual(result.fills[-1].price, D('1002'))
        self.assertEqual(result.fills[-1].fill_date.strftime('%H:%M'), '14:45')
        self.assertEqual((order.quantity, order.filled_quantity, order.expired_quantity,
                          order.remaining_quantity, order.status), (5, 2, 3, 0, 'EXPIRED'))
        self.assertEqual(result.portfolio.position.quantity, 3)
        self.assertEqual(result.trades[-1].quantity, 2)
        from backtesting_api.application.inline_results import inline_result_to_dict
        data = resolve_inline(normalized(deepcopy(p)), POLICY)
        result_json = inline_result_to_dict(UUID(int=3), data, result, input_hash='i', policy_hash='p',
                                            accounting=p['accounting'])
        self.assertEqual(result_json['orders'][-1]['status'], 'expired')
        self.assertEqual(result_json['fills'][-1]['order_type'], 'ATC')
        self.assertEqual(result_json['open_position']['quantity'], 3)
        strict = deepcopy(p)
        strict['strategy']['exit']['allow_overnight'] = False
        with self.assertRaisesRegex(ValueError, 'END_OF_DAY_POSITION_REQUIRES_EXIT'):
            run(strict)

    def test_atc_missing_no_match_wrong_contract_and_late_decision_fail(self):
        for mutation, error in [
            (lambda p: p['trade_data'].update(auctions=[]), 'MISSING_ATC_MATCH_BAR'),
            (lambda p: p['trade_data']['auctions'][0].update(status='no_match', price=None), 'END_OF_DAY_POSITION_REQUIRES_EXIT'),
            (lambda p: p['trade_data']['auctions'][0].update(contract_code='OTHER'), 'ATC_CONTRACT_MISMATCH')]:
            p = session_payload(atc=True)
            mutation(p)
            with self.assertRaisesRegex(ValueError, error): run(p)
        p = session_payload(atc=True)
        p['trade_data']['bars'].pop()
        with self.assertRaisesRegex(ValueError, 'REQUIRES_EXIT'): run(p)

    def test_future_prices_and_auction_do_not_change_prior_decisions(self):
        p = session_payload(atc=True)
        full = run(p)
        future = deepcopy(p)
        future['trade_data']['auctions'][0]['price'] = '1200'
        changed = run(future)
        self.assertEqual(full.evaluations, changed.evaluations)
        self.assertEqual(full.fills[0], changed.fills[0])
        self.assertEqual(full.equity_history[:-1], changed.equity_history[:-1])
        cut = session_payload()
        first = run(cut)
        cut['trade_data']['bars'] = cut['trade_data']['bars'][:2]
        shorter = run(cut)
        self.assertEqual(shorter.fills, first.fills[:len(shorter.fills)])
        self.assertEqual(shorter.equity_history, first.equity_history[:2])

    def test_validation_rejects_incomplete_or_unsupported_contracts(self):
        cases = [lambda p: p['execution'].pop('matching_model'),
                 lambda p: p['trade_data'].pop('contract_dates'),
                 lambda p: p['trade_data'].pop('provenance'),
                 lambda p: p['strategy']['entry'].update(limit_price={'add': [1000.01, 0]}),
                 lambda p: p['execution'].update(auction_match_quantity=-1),
                 lambda p: p['execution'].update(slippage_rate='0.01'),
                 lambda p: p['strategy']['exit'].update(flat_by='14:30')]
        for mutation in cases:
            p = session_payload(atc=True)
            mutation(p)
            if p['strategy']['entry'].get('limit_price') == {'add': [1000.01, 0]}:
                result = run(p)
                self.assertEqual(result.orders[0].reason, 'LIMIT_PRICE_INVALID_OR_OFF_TICK')
            else:
                with self.assertRaises(ValueError): InlineRunRequest.model_validate(p)
        p = session_payload(atc=True)
        p['trade_data']['auctions'][0]['available_at'] -= 10
        with self.assertRaisesRegex(ValueError, 'INVALID_AUCTION_TIME'): normalized(p)
        p = session_payload()
        p['execution']['auction_match_quantity'] = 1
        with self.assertRaisesRegex(ValueError, 'AUCTION_MATCH_QUANTITY_REQUIRES_AUCTION_ORDER'):
            normalized(p)

    def test_api_hash_pinned_auction_reload_chart_and_lifecycle(self):
        with tempfile.TemporaryDirectory(dir='.agents') as temporary:
            repo = FileRunRepository(Path(temporary), Path(temporary) / 'unused.json')
            service = BacktestService(repo, inline_runner=run_inline_strategy)
            client = TestClient(legacy_inline_app(service))
            p = session_payload(atc=True)
            response = client.post('/internal-test/legacy/backtests', json=p)
            self.assertEqual(response.status_code, 201, response.text)
            result = response.json()
            run_id = UUID(result['metadata']['run_id'])
            self.assertEqual(service.get(run_id), result)
            self.assertEqual(result['orders'][-1]['events'][-1]['phase'], 'ATC')
            self.assertEqual(result['fills'][-1]['time_precision'], 'auction')
            self.assertIn('available_at', result['fills'][-1])
            self.assertEqual(service.get_input(run_id)['payload']['trade_data']['auctions'][0]['price'], '1002')
            chart = service.get_chart(run_id)
            self.assertEqual(chart['auctions'][0]['price'], '1002')
            self.assertFalse(any(b['time'] == chart['auctions'][0]['time'] for b in chart['bars']))
            changed = deepcopy(p)
            changed['trade_data']['auctions'][0]['price'] = '1003'
            other = client.post('/internal-test/legacy/backtests', json=changed).json()
            self.assertNotEqual(result['metadata']['input_hash'], other['metadata']['input_hash'])
            partial = client.post('/internal-test/legacy/backtests', json=ato_payload(2))
            self.assertEqual(partial.status_code, 201, partial.text)
            partial_result = partial.json()
            partial_id = UUID(partial_result['metadata']['run_id'])
            self.assertEqual(partial_result['orders'][0]['status'], 'expired')
            self.assertEqual(partial_result['orders'][0]['filled_quantity'], 2)
            self.assertEqual(partial_result['orders'][0]['expired_quantity'], 3)
            self.assertEqual(service.get(partial_id), partial_result)
            self.assertEqual(service.get_input(partial_id)['payload']['execution']['auction_match_quantity'], 2)
            self.assertEqual(datetime.fromtimestamp(service.get_chart(partial_id)['bars'][0]['time'], ZONE).strftime('%H:%M'), '09:00')
