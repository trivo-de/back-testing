"""Verify approved Close-only protection, fixed target quantities and causal trailing."""
from decimal import Decimal as D
import unittest
from pydantic import ValidationError
from backtesting_api.api.price_schemas import PriceRunRequest
from test_price_strategy import PriceApiTest, bars, request, run


class PriceProtectionTest(unittest.TestCase):
    """Calculate expected fills independently from the protection state machine."""
    def test_long_and_short_percentages_ignore_wicks_and_match_exact_close(self):
        """Six means six percent; only Close can trigger a stop or target."""
        for side, neutral, stop in [('long', '97', '94'), ('short', '103', '106')]:
            value = request(entry={side: {'gt': [1, 0]}}, exit={}, risk={'sl': 6, 'tp': 12})
            result = run(value, bars([('100', '130', '70', '100'), ('100', '125', '75', neutral),
                                      (neutral, '110', '90', stop)]))
            with self.subTest(side=side):
                self.assertEqual([fill['price'] for fill in result['fills']], [D(100), D(stop)])
                self.assertEqual(result['trades'][0]['reason'], 'STOP_LOSS')
        for side, close in [('long', '112'), ('short', '88')]:
            value = request(entry={side: {'gt': [1, 0]}}, exit={}, risk={'tp': 12})
            result = run(value, bars([('100', '101', '99', '100'), ('100', '115', '85', close)]))
            self.assertEqual(result['fills'][-1]['price'], D(close))
            self.assertEqual(result['trades'][-1]['reason'], 'TAKE_PROFIT')

    def test_multiple_targets_close_at_actual_close_and_retain_links(self):
        """Resolve initial-quantity arithmetic once and close every crossed leg at Close."""
        value = request(quantity=3, exit={}, risk={'targets': [
            {'pct': 6, 'quantity': {'floor': [{'div': [{'ref': 'position.initial_quantity'}, 2]}]}},
            {'pct': 12, 'quantity': 'remaining'}]})
        result = run(value, bars([('100', '101', '99', '100'), ('100', '120', '99', '115')]))
        self.assertEqual([fill['quantity'] for fill in result['fills']], [3, 1, 2])
        self.assertEqual([fill['price'] for fill in result['fills'][1:]], [D(115), D(115)])
        self.assertEqual([trade['reason'] for trade in result['trades']], ['TP1', 'TP2'])
        self.assertEqual(result['summary']['total_pnl'], D(45))
        self.assertEqual(result['summary']['closed_positions'], 1)
        self.assertEqual({fill['position_id'] for fill in result['fills']}, {'p1'})

    def test_absolute_prices_are_pinned_at_decision_before_better_lo_fill(self):
        """Do not recompute stop or target using a later fill bar's Close."""
        value = request(exit={}, order={'type': 'LO', 'limit_price': 100}, risk={
            'stop_price': {'sub': [{'ref': 'price'}, 5]},
            'targets': [{'price': {'add': [{'ref': 'price'}, 10]}, 'quantity': 'remaining'}]})
        result = run(value, bars([('100', '101', '99', '100'), ('96', '112', '95', '111')]))
        self.assertEqual(result['orders'][0]['protection']['stop_price'], D(95))
        self.assertEqual(result['orders'][0]['protection']['targets'][0]['price'], D(110))
        self.assertEqual([fill['price'] for fill in result['fills']], [D(96), D(111)])
        self.assertEqual(result['summary']['total_pnl'], D(15))

    def test_invalid_levels_are_rejected_against_actual_fill_before_recording_it(self):
        """A better LO fill cannot make an already pinned wrong-side stop valid."""
        invalid = [request(exit={}, risk={'stop_price': 101}), request(exit={}, risk={'sl': 100}),
                   request(exit={}, risk={'trailing': 100}),
                   request(exit={}, risk={'targets': [{'price': 110, 'quantity': 1}, {'price': 105, 'quantity': 1}]}, quantity=2),
                   request(entry={'short': {'gt': [1, 0]}}, exit={}, risk={'tp': 100})]
        for value in invalid:
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'INVALID_PROTECTION_LEVEL|TARGETS_OUT_OF_ORDER'):
                run(value, bars([('100', '101', '99', '100')]))
        value = request(exit={}, risk={'stop_price': 95}, order={'type': 'LO', 'limit_price': 100})
        with self.assertRaisesRegex(ValueError, 'INVALID_PROTECTION_LEVEL'):
            run(value, bars([('100', '101', '99', '100'), ('94', '101', '93', '100')]))

    def test_trailing_uses_close_extreme_without_wick_or_same_bar_retroaction(self):
        """Check the old threshold first and tighten only for the following candle."""
        examples = [
            ('long', [('100', '101', '99', '100'), ('100', '150', '80', '110'),
                      ('110', '111', '90', '105'), ('105', '106', '90', '103.4')], D('103.4')),
            ('short', [('100', '101', '99', '100'), ('100', '120', '50', '90'),
                       ('90', '110', '80', '94'), ('94', '110', '90', '95.4')], D('95.4'))]
        for side, prices, expected in examples:
            value = request(entry={side: {'gt': [1, 0]}}, exit={}, risk={'trailing': 6})
            result = run(value, bars(prices))
            with self.subTest(side=side):
                self.assertEqual(len(result['fills']), 2)
                self.assertEqual(result['fills'][-1]['price'], expected)
                self.assertEqual(result['fills'][-1]['fill_time'], bars(prices)[-1].closed_at)
                self.assertEqual(result['trades'][-1]['reason'], 'TRAILING_STOP')

    def test_after_tp1_trailing_starts_from_actual_tp1_close(self):
        """Do not reuse a target level or the candle's earlier favorable wick as seed."""
        value = request(quantity=2, exit={}, risk={'targets': [
            {'pct': 5, 'quantity': 1}, {'pct': 50, 'quantity': 'remaining'}], 'trailing_after_tp1': 6})
        prices = [('100', '101', '99', '100'), ('100', '140', '99', '106'),
                  ('106', '110', '100', '102'), ('102', '105', '99', '99.64')]
        result = run(value, bars(prices))
        self.assertEqual([fill['price'] for fill in result['fills']], [D(100), D(106), D('99.64')])
        self.assertEqual([trade['reason'] for trade in result['trades']], ['TP1', 'TRAILING_STOP'])
        self.assertEqual(result['summary']['total_pnl'], D('5.64'))

    def test_trailing_fallback_lo_is_not_refreshed_while_pending(self):
        """A trailing trigger is a signal, and the fixed fallback LO can stay unfilled."""
        value = request(entry={'long': {'condition': {'gt': [1, 0]}, 'order': {'type': 'IMMEDIATE'}}},
                        exit={}, risk={'trailing': 6},
                        order={'type': 'LO', 'limit_price': {'add': [{'ref': 'price'}, 10]}})
        prices = [('100', '101', '99', '100'), ('100', '115', '99', '110'),
                  ('110', '111', '99', '100'), ('100', '105', '99', '101'), ('101', '105', '100', '102')]
        result = run(value, bars(prices))
        self.assertEqual(len(result['orders']), 2)
        order = result['orders'][1]
        self.assertEqual(order['type'], 'LO')
        self.assertEqual(order['limit_price'], D(110))
        self.assertEqual(order['execution_bars'], 2)
        self.assertEqual(order['reason'], 'END_OF_REPORT')
        self.assertEqual(len(result['fills']), 1)
        self.assertIsNotNone(result['open_position'])

    def test_trailing_uses_direction_exit_order_override(self):
        """Use the closing action's LO rather than the request's immediate default."""
        value = request(exit={'long': {'condition': {'gt': [0, 1]}, 'order': {'type': 'LO', 'limit_price': 105}}},
                        risk={'trailing': 6})
        result = run(value, bars([('100', '101', '99', '100'), ('100', '115', '99', '110'),
                                  ('110', '111', '99', '100'), ('106', '108', '100', '107')]))
        self.assertEqual(result['orders'][1]['reason'], 'TRAILING_STOP')
        self.assertEqual(result['fills'][1]['price'], D(106))
        self.assertEqual(result['fills'][1]['fill_phase'], 'open')

    def test_stop_precedes_trailing_and_cancels_its_pending_lo(self):
        """A hard stop remains Close-only immediate while trailing is awaiting its LO."""
        value = request(exit={'long': {'condition': {'gt': [0, 1]}, 'order': {'type': 'LO', 'limit_price': 120}}},
                        risk={'sl': 6, 'trailing': 6})
        result = run(value, bars([('100', '101', '99', '100'), ('100', '115', '99', '110'),
                                  ('110', '111', '99', '100'), ('100', '101', '85', '90')]))
        self.assertEqual(result['orders'][1]['status'], 'CANCELED')
        self.assertEqual(result['orders'][1]['reason'], 'POSITION_CHANGED')
        self.assertEqual(result['trades'][-1]['reason'], 'STOP_LOSS')
        self.assertEqual(result['fills'][-1]['price'], D(90))

    def test_lo_entry_uses_actual_fill_and_can_protect_at_entry_close(self):
        """Percentage levels use a better Open, and intrabar entries can stop at Close."""
        value = request(exit={}, order={'type': 'LO', 'limit_price': 100}, risk={'sl': 6})
        result = run(value, bars([('100', '101', '99', '100'), ('95', '96', '89', '90'),
                                  ('90', '91', '88', '89.3')]))
        self.assertEqual([fill['price'] for fill in result['fills']], [D(95), D('89.3')])
        result = run(value, bars([('100', '101', '99', '100'), ('102', '103', '89', '90')]))
        self.assertEqual([fill['fill_phase'] for fill in result['fills']], ['intrabar_assumed', 'decision_close'])
        self.assertEqual(result['trades'][0]['realized_pnl'], D(-10))

    def test_protection_quantities_do_not_expand_after_conditional_partial_exit(self):
        """A pinned target larger than the remaining position is an error, never capped."""
        value = request(quantity=3, exit={'long': {'condition': {'all': [
            {'gte': [{'ref': 'position.held_bars'}, 2]}, {'lte': [{'ref': 'position.held_bars'}, 2]}]},
            'quantity': 2}}, risk={'targets': [{'pct': 6, 'quantity': 2}]})
        with self.assertRaisesRegex(ValueError, 'INVALID_CLOSE_QUANTITY_OR_PRICE'):
            run(value, bars([('100', '101', '99', '100'), ('100', '102', '99', '101'), ('101', '108', '100', '107')]))

    def test_invalid_target_configuration_is_rejected_before_runtime(self):
        """Reject ambiguous bases, noninteger quantities and hidden remaining legs."""
        bad_risks = [
            {'targets': []}, {'targets': [{'pct': 6, 'quantity': True}]},
            {'targets': [{'pct': 6, 'quantity': 1.5}]}, {'targets': [{'pct': 6, 'quantity': '1'}]},
            {'targets': [{'pct': 6, 'price': 106, 'quantity': 1}]}, {'targets': [{'quantity': 1}]},
            {'targets': [{'pct': 6, 'quantity': 'remaining'}, {'pct': 12, 'quantity': 1}]},
            {'targets': [{'pct': 12, 'quantity': 1}, {'pct': 6, 'quantity': 1}]},
            {'targets': [{'pct': 6, 'quantity': {'div': [{'ref': 'position.initial_quantity'}, 2]}}]},
            {'targets': [{'pct': 6, 'quantity': {'ref': 'trade_data.close'}}]},
            {'sl': 6, 'stop_price': 94}, {'tp': 6, 'targets': [{'pct': 6, 'quantity': 1}]},
            {'trailing': 6, 'trailing_after_tp1': 6}, {'trailing_after_tp1': 6},
            {'stop_price': {'ref': 'position.entry_price'}}]
        for risk in bad_risks:
            with self.subTest(risk=risk), self.assertRaises(ValidationError):
                PriceRunRequest.model_validate(request(risk=risk))

    def test_complete_and_truncated_sources_keep_protection_prefix_identical(self):
        """Future favorable bars cannot revise an earlier trailing level or fill."""
        value = request(exit={}, risk={'trailing': 6})
        rows = bars([('100', '101', '99', '100'), ('100', '115', '99', '110'),
                     ('110', '112', '103', '105'), ('105', '106', '100', '103')])
        complete, prefix = run(value, rows), run(value, rows[:3])
        self.assertEqual(complete['fills'][:1], prefix['fills'])
        self.assertEqual(complete['pnl_history'][:4], prefix['pnl_history'])
        self.assertEqual(complete['evaluations'][:3], prefix['evaluations'])
        self.assertEqual(prefix['open_position']['trailing_price'], D('103.4'))


class PriceProtectionApiTest(unittest.TestCase):
    """Exercise advanced protection through the same validation/run boundary as the UI."""
    def setUp(self):
        """Reuse the fixed-source local-only API fixture without copying its tests."""
        PriceApiTest.setUp(self)

    def test_api_accepts_multiple_targets_and_deferred_trailing(self):
        """Preserve advanced intent through validation, actual fills and schema-3 output."""
        value = request(quantity=3, risk={'targets': [
            {'pct': 6, 'quantity': 1}, {'pct': 12, 'quantity': 'remaining'}], 'trailing_after_tp1': 6})
        checked = self.client.post('/api/backtests/validate', json=value)
        self.assertEqual(checked.status_code, 200, checked.text)
        self.assertIn('targets', checked.json()['effective_config']['risk'])
        response = self.client.post('/api/backtests', json=value)
        self.assertEqual(response.status_code, 201, response.text)
        result = response.json()
        self.assertEqual([fill['quantity'] for fill in result['fills']], [3, 1, 2])
        self.assertEqual(result['summary']['realized_pnl'], '36')
        self.assertIsNone(result['open_position'])

    def test_bad_absolute_fill_level_leaves_failed_run_instead_of_success(self):
        """Reject a wrong-side level before publishing any successful result."""
        response = self.client.post('/api/backtests', json=request(exit={}, risk={'stop_price': 101}))
        self.assertEqual(response.status_code, 422)
        self.assertIn('INVALID_PROTECTION_LEVEL', response.text)
        import json
        states = [json.loads(path.read_bytes()) for path in (self.repository.store / 'runs').glob('*.json')]
        self.assertEqual([state['status'] for state in states], ['failed'])
        self.assertEqual(self.repository.list_runs(), [])
