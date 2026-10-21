import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D

from backtesting_api.domain.market import StrategyBar
from backtesting_api.domain.matching import MatchBudget, match_auction, match_continuous, match_next_open, mtl_limit_price
from backtesting_api.domain.orders import OrderRequest, OrderResult
from backtesting_api.domain.trading import OrderResult as LegacyOrderResult


class OrdersTest(unittest.TestCase):
    def test_market_matrix_shared_budget_and_validation(self):
        stamp = datetime(2026, 3, 25, 9, 5, tzinfo=timezone(timedelta(hours=7)))
        bar = StrategyBar(stamp, D(1000), D(1002), D(998), D(1001), D(1), close_time=stamp + timedelta(minutes=5))
        for buy in (True, False):
            for kind in ('MOK', 'MAK', 'MTL'):
                for available in (0, 2, 5, 8):
                    with self.subTest(buy=buy, kind=kind, available=available):
                        budget = MatchBudget(available)
                        match = match_continuous(OrderRequest(kind), bar, buy=buy, quantity=5,
                                                 available_quantity=budget.remaining,
                                                 floor_price=D(900), ceiling_price=D(1100))
                        expected = 0 if kind == 'MOK' and available < 5 else min(5, available)
                        self.assertEqual(match.quantity if match else 0, expected)
                        self.assertEqual(budget.remaining, available)
                        if match: budget.consume(match.quantity)
                        self.assertEqual(budget.remaining, available - expected)
        budget = MatchBudget(2)
        self.assertIsNone(match_continuous(OrderRequest('LO', D(990)), bar, buy=True, quantity=5,
                                          available_quantity=budget.remaining))
        self.assertEqual(budget.remaining, 2)
        for value in (-1, True, D('2.5'), None):
            with self.subTest(value=value), self.assertRaises(ValueError): MatchBudget(value)
        for price in (None, D('NaN'), D('0'), D('1000.01'), D(1200)):
            from dataclasses import replace
            with self.subTest(price=price), self.assertRaisesRegex(ValueError, 'INVALID_MARKET_MATCH_PRICE'):
                match_continuous(OrderRequest('MAK'), replace(bar, open=price), buy=True, quantity=5,
                                 available_quantity=0, floor_price=D(900), ceiling_price=D(1100))
        for kind in ('MOK', 'MAK', 'MTL'):
            with self.assertRaises(ValueError): match_next_open(OrderRequest(kind), bar)
        for buy, price, expected in ((True, 1000, '1000.1'), (False, 1000, '999.9'),
                                     (True, 1100, '1100'), (False, 900, '900')):
            self.assertEqual(mtl_limit_price(D(price), buy=buy, floor_price=D(900), ceiling_price=D(1100)), D(expected))

    def test_request_validation_and_single_result_definition(self):
        self.assertIs(OrderResult, LegacyOrderResult)
        for request in (OrderRequest(), OrderRequest('LO', D('1000.1')), OrderRequest('ATO'), OrderRequest('ATC')):
            request.validate()
        for request in (OrderRequest('UNKNOWN'), OrderRequest('LO'), OrderRequest('LO', D('NaN')),
                        OrderRequest('LO', D('0')), OrderRequest('LO', D('1000.01')),
                        OrderRequest('ATO', D('1000')), OrderRequest('ATC', D('1000')),
                        OrderRequest(max_execution_bars=True)):
            with self.subTest(request=request), self.assertRaises(ValueError):
                request.validate()

    def test_matching_prices_timing_and_partial_quantity(self):
        stamp = datetime(2026, 3, 25, 9, tzinfo=timezone(timedelta(hours=7)))
        bar = StrategyBar(stamp, D(1000), D(1002), D(998), D(1001), D(1), close_time=stamp + timedelta(minutes=5))
        opened = match_next_open(OrderRequest(), bar)
        self.assertEqual((opened.price, opened.time), (D(1000), stamp))
        for buy, limit in ((True, D(999)), (False, D(1001))):
            matched = match_continuous(OrderRequest('LO', limit), bar, buy=buy, quantity=5)
            self.assertEqual((matched.price, matched.time, matched.quantity), (limit, bar.closed_at, 5))
        self.assertIsNone(match_continuous(OrderRequest('LO', D(997)), bar, buy=True, quantity=5))
        with self.assertRaisesRegex(ValueError, 'ORDER_UNSUPPORTED_BY_NEXT_OPEN'):
            match_next_open(OrderRequest('LO', D(1000)), bar)
        for limit, expected in ((None, 5), (2, 2), (0, None)):
            matched = match_auction(OrderRequest('ATO'), price=bar.open, time=stamp,
                                    bar_time=stamp, quantity=5, quantity_limit=limit)
            self.assertEqual(matched.quantity if matched else None, expected)
