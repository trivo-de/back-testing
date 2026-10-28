"""Check hand-calculated phase A examples without claiming a new engine exists."""

import json
import unittest
from datetime import datetime
from decimal import Decimal as D
from pathlib import Path


class PriceOnlyFixtureTest(unittest.TestCase):
    """Protect independent accounting and causal examples during the migration."""

    @classmethod
    def setUpClass(cls):
        """Load the small synthetic contract oracle, never live market data."""
        cls.fixture = json.loads((Path(__file__).parent / 'fixtures/price-only-cases.json').read_text(encoding='utf-8'))

    def test_hand_calculated_long_short_and_partial_pnl(self):
        """Reconcile closed legs and remaining quantity exactly with Decimal."""
        for case in self.fixture['pnl_cases']:
            with self.subTest(case=case['id']):
                sign = 1 if case['direction'] == 'LONG' else -1
                entry = D(case['entry_price'])
                remaining = case['initial_quantity']
                realized = D(0)
                for leg in case['exits']:
                    self.assertGreater(leg['quantity'], 0)
                    self.assertLessEqual(leg['quantity'], remaining)
                    realized += sign * (D(leg['price']) - entry) * leg['quantity']
                    remaining -= leg['quantity']
                unrealized = sign * (D(case['last_close']) - entry) * remaining
                expected = case['expected']
                self.assertEqual((realized, unrealized, realized + unrealized, remaining),
                                 (D(expected['realized']), D(expected['unrealized']), D(expected['total']), expected['remaining']))

    def test_timeline_pnl_drawdown_and_no_future_source(self):
        """Keep the response example causal and avoid double-counting partial exits."""
        for case in self.fixture['timeline']:
            stamp = datetime.fromisoformat
            self.assertLess(stamp(case['signal_bar_open']), stamp(case['signal_time']))
            self.assertLessEqual(stamp(case['source_available_at']), stamp(case['signal_time']))
            self.assertLessEqual(stamp(case['signal_time']), stamp(case['entry_open_time']))
            previous = stamp(case['entry_open_time'])
            realized, peak, drawdown = D(0), D(0), D(0)
            remaining = case['quantity']
            for row in case['close_points']:
                self.assertGreater(stamp(row['time']), previous)
                previous = stamp(row['time'])
                quantity = row['closed_quantity']
                self.assertLessEqual(quantity, remaining)
                if quantity:
                    realized += (D(row['exit_price']) - D(case['entry_price'])) * quantity
                    remaining -= quantity
                total = realized + (D(row['mark']) - D(case['entry_price'])) * remaining
                self.assertEqual(total, D(row['expected_total']))
                peak = max(peak, total)
                drawdown = max(drawdown, peak - total)
            self.assertEqual(drawdown, D(case['expected_max_drawdown']))

    def test_documented_requests_match_fixture(self):
        """Keep published request examples identical to their migration fixtures."""
        import re

        contract = (Path(__file__).parents[1] / 'docs/design/price-only-contract.md').read_text(encoding='utf-8')
        examples = [json.loads(block) for block in re.findall(r'```json\n(.*?)\n```', contract, re.S)]
        self.assertEqual(examples[:2], self.fixture['request_examples'])

    def test_percentage_risk_hand_calculated_levels(self):
        """Check percentage scale and LONG/SHORT levels independently of runtime."""
        for case in self.fixture['risk_pct_cases']:
            with self.subTest(direction=case['direction'], sl_pct=case['sl_pct']):
                sign = 1 if case['direction'] == 'LONG' else -1
                entry = D(case['entry_price'])
                stop = entry * (1 - sign * D(case['sl_pct']) / 100)
                target = entry * (1 + sign * D(case['tp_pct']) / 100)
                trailing = D(case['extreme']) * (1 - sign * D(case['trailing_pct']) / 100)
                self.assertEqual((stop, target, trailing), tuple(D(case[key]) for key in
                                 ('expected_stop', 'expected_target', 'expected_trailing')))
                self.assertTrue(all(value.is_finite() and value > 0 for value in (stop, target, trailing)))

    def test_close_only_protection_hand_examples(self):
        """Check threshold examples without using candle wicks or capping fills."""
        for case in self.fixture['close_protection_cases']:
            with self.subTest(case=case['id']):
                opened, high, low, close = map(D, case['bar'])
                self.assertLessEqual(low, min(opened, close))
                self.assertGreaterEqual(high, max(opened, close))
                entry = D(case['entry'])
                sign = 1 if case['direction'] == 'LONG' else -1
                change = sign * (close / entry - 1) * 100
                reason = ('STOP_LOSS' if change <= -D(case['sl_pct']) else
                          'TAKE_PROFIT' if change >= D(case['tp_pct']) else None)
                self.assertEqual(reason, case['expected_reason'])
                self.assertEqual(str(close) if reason else None, case['expected_fill'])

    def test_immediate_same_close_oracle(self):
        """Keep the approved close-fill examples distinct from next-open or LO."""
        for case in self.fixture['immediate_cases']:
            with self.subTest(action=case['action']):
                stamp = datetime.fromisoformat
                self.assertLessEqual(stamp(case['source_available_at']), stamp(case['signal_time']))
                self.assertEqual(case['signal_time'], case['order_time'])
                self.assertEqual(case['order_time'], case['fill_time'])
                self.assertEqual(case['event_order'], ['signal', 'order', 'fill'])
                self.assertEqual(D(case['expected_fill_price']), D(case['signal_close']))
                self.assertNotEqual(D(case['expected_fill_price']), D(case['next_open']))
                self.assertEqual(case['expected_fill_phase'], 'decision_close')
                self.assertFalse(case['expected_pending'])

    def test_lo_oracles_against_existing_price_matcher(self):
        """Compare BUY/SELL price cases with the existing shared LO primitive."""
        from backtesting_api.domain.matching import match_continuous
        from backtesting_api.domain.orders import OrderRequest
        from backtesting_api.domain.market import StrategyBar
        from datetime import timedelta

        opened = datetime.fromisoformat('2026-04-01T09:05:00+07:00')
        for case in self.fixture['lo_cases']:
            with self.subTest(case=case['id']):
                prices = list(map(D, case['bar']))
                bar = StrategyBar(opened, *prices, D(1), close_time=opened + timedelta(minutes=5))
                match = match_continuous(OrderRequest('LO', D(case['limit'])), bar,
                                         buy=case['side'] == 'BUY', quantity=1)
                if case['expected_price'] is None:
                    self.assertIsNone(match)
                else:
                    self.assertEqual(match.price, D(case['expected_price']))
                    self.assertEqual(match.time, opened if case['expected_phase'] == 'open' else bar.closed_at)
                    self.assertEqual(match.quantity, 1)


if __name__ == '__main__':
    unittest.main()
