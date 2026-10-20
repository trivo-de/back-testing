from dataclasses import asdict, replace
from datetime import timedelta
from decimal import Decimal as D
import unittest

from backtesting_api.domain.engine import run_engine
from backtesting_api.domain.execution import Bracket, ContractExecution
from backtesting_api.domain.multi_execution import MultiContractExecution
from backtesting_api.domain.orders import OrderRequest
from backtesting_api.domain.trading import FixedSignal
from backtesting_api.application.inline_data import InputBar
from test_contract_execution import ACCOUNTING, bar


def opening(key, quantity=3, price=1000, age=1, kind='LO'):
    return FixedSignal('LONG', quantity, position_id=key,
                       order=OrderRequest(kind, D(price) if kind == 'LO' else None, age))


def run(rows, provider, *, bracket=None, **kwargs):
    executor = MultiContractExecution(200000000, lambda cash: ContractExecution(cash, ACCOUNTING, bracket=bracket))
    return run_engine(rows, provider, initial_cash=200000000, fee_rate=0, slippage_rate=0,
                      matching_model='hnx_sessions_v1', execution=lambda cash: executor,
                      on_open=executor.before_open, **kwargs)


class MultiSessionTest(unittest.TestCase):
    def test_gap_stop_precedes_limit_touch_and_cancels_same_lot_close(self):
        rows = [bar(0), bar(1), bar(2, 990, 1005, 989, 1000)]
        def provider(context):
            if len(context.bars) == 1:
                return opening('A', 1)
            if len(context.bars) == 2:
                return (FixedSignal('CLOSE', position_id='A', order=OrderRequest('LO', D(1004))),
                        opening('B', 1, price=989))
        result = run(rows, provider, bracket=Bracket(D(6)))
        self.assertEqual([fill.position_id for fill in result.fills], ['A', 'A', 'B'])
        self.assertEqual([fill.fill_date for fill in result.fills[1:]],
                         [rows[2].trading_date, rows[2].closed_at])
        self.assertEqual(result.trades[0].exit_price, 990)
        close = next(order for order in result.orders if order.side == 'CLOSE' and order.order_type == 'LO')
        self.assertEqual((close.status, close.reason), ('CANCELED', 'POSITION_CHANGED'))

    def test_open_target_cannot_be_replaced_by_a_later_stop(self):
        rows = [bar(0), bar(1), bar(2, 1010, 1012, 990, 1000)]
        def provider(context):
            if len(context.bars) == 1:
                return opening('A', 2)
        result = run(rows, provider, bracket=Bracket(D(6), ((D(8), 1),)))
        self.assertEqual([fill.price for fill in result.fills], [1000, 1008, 994])
        self.assertEqual([fill.fill_date for fill in result.fills[1:]],
                         [rows[2].trading_date, rows[2].closed_at])
        changed_future = run([*rows[:2], bar(2, 1010, 1012, 1005, 1010)], provider,
                             bracket=Bracket(D(6), ((D(8), 1),)))
        self.assertEqual(changed_future.fills[:2], result.fills[:2])

    def test_multi_execution_rejects_next_open_model(self):
        with self.assertRaisesRegex(ValueError, 'MULTI_ENTRY_REQUIRES_SESSION_MATCHING'):
            run_engine([bar(0)], lambda context: None, initial_cash=200000000,
                       fee_rate=0, slippage_rate=0, matching_model='next_open',
                       execution=lambda cash: MultiContractExecution(
                           cash, lambda amount: ContractExecution(amount, ACCOUNTING)))

    def test_expiration_releases_capacity_before_next_decision(self):
        rows = [bar(i) for i in range(3)]
        def provider(context):
            if len(context.bars) == 1:
                return opening('expired', 5, price=980)
            if len(context.bars) == 2:
                self.assertFalse(context.pending_signals)
                return (opening('A'), opening('B'))
        result = run(rows, provider)
        self.assertEqual((result.orders[0].status, result.orders[0].expired_quantity), ('EXPIRED', 5))
        self.assertEqual([fill.quantity for fill in result.fills], [3, 2])
        self.assertEqual(result.portfolio.quantity, 5)

    def test_completed_trades_do_not_depend_on_future_bars(self):
        rows = [bar(i) for i in range(3)]
        def provider(context):
            if len(context.bars) == 1:
                return (opening('A'), opening('B'))
            if len(context.bars) == 2:
                return tuple(FixedSignal('CLOSE', position_id=key) for key, _ in context.portfolio.positions)
        truncated = run(rows, provider)
        for future in (bar(3, 1500, 2000, 500, 1800), bar(3, 800, 900, 700, 750)):
            extended = run([*rows, future], provider)
            self.assertEqual(extended.fills, truncated.fills)
            self.assertEqual(extended.trades, truncated.trades)
            self.assertEqual(extended.orders, truncated.orders)
            self.assertEqual(extended.equity_history[:3], truncated.equity_history)

    def test_open_fill_precedes_earlier_submitted_limit_touch(self):
        rows = [bar(0), bar(1, 1000, 1001, 998, 1000)]
        def provider(context):
            if len(context.bars) == 1:
                return (opening('touch', 1, price=999), opening('open', 1))
        result = run(rows, provider)
        self.assertEqual([fill.position_id for fill in result.fills], ['open', 'touch'])
        self.assertEqual([fill.fill_date for fill in result.fills], [rows[1].trading_date, rows[1].closed_at])
        self.assertEqual([order.fill_index for order in result.orders], [1, 0])

    def test_two_orders_share_capacity_and_keep_links(self):
        rows = [bar(i) for i in range(3)]
        contexts = []
        def provider(context):
            contexts.append(context)
            if len(context.bars) == 1:
                return (opening('A'), opening('B'))
            if len(context.bars) == 2:
                return tuple(FixedSignal('CLOSE', position_id=key) for key, _ in context.portfolio.positions)
        result = run(rows, provider)
        self.assertEqual([f.quantity for f in result.fills], [3, 2, 3, 2])
        self.assertEqual([f.position_id for f in result.fills], ['A', 'B', 'A', 'B'])
        self.assertEqual([o.position_id for o in result.orders], ['A', 'B', 'A', 'B'])
        self.assertEqual([s.position_id for s in result.signals], ['A', 'B', 'A', 'B'])
        self.assertEqual([t.position_id for t in result.trades], ['A', 'B'])
        self.assertEqual(result.portfolio.quantity, 0)
        self.assertEqual(result.portfolio.cash - 200000000, sum(t.net_pnl for t in result.trades))
        for order in result.orders:
            self.assertEqual(order.quantity, order.filled_quantity + order.expired_quantity + order.remaining_quantity)
        self.assertEqual(result, run(rows, provider))

    def test_protection_cancels_only_its_lots_closing_order(self):
        rows = [bar(0), bar(1), bar(2, 1000, 1001, 993, 1000), bar(3)]
        seen_pending = []
        def provider(context):
            seen_pending.append(tuple(s.position_id for s in context.pending_signals))
            if len(context.bars) == 1:
                return opening('A', 1)
            if len(context.bars) == 2:
                return (FixedSignal('CLOSE', position_id='A', order=OrderRequest('LO', D(1020), 4)),
                        opening('B', 1, price=980, age=4))
        result = run(rows, provider, bracket=Bracket(D(6)))
        close = next(o for o in result.orders if o.order_type == 'LO' and o.side == 'CLOSE')
        pending_entry = next(o for o in result.orders if o.position_id == 'B')
        self.assertEqual((close.status, close.reason), ('CANCELED', 'POSITION_CHANGED'))
        self.assertEqual((pending_entry.status, pending_entry.reason), ('EXPIRED', 'END_OF_REPORT'))
        self.assertIn(('B',), seen_pending)
        self.assertEqual(result.trades[0].position_id, 'A')

    def test_auction_partial_entries_and_separate_atc_closes(self):
        first = bar(0)
        history = replace(first, trading_date=first.trading_date - timedelta(days=1),
                          close_time=first.closed_at - timedelta(days=1))
        rows = [InputBar(**asdict(row), contract_code='VN30F2604')
                for row in (history, first, bar(64), bar(65), bar(69))]
        def provider(context):
            if context.decision_time:
                return (opening('A', kind='ATO'), opening('B', kind='ATO'))
            if context.bars[-1].closed_at.strftime('%H:%M') == '14:30':
                return tuple(FixedSignal('CLOSE', position_id=key, order=OrderRequest('ATC'))
                             for key, _ in context.portfolio.positions)
        result = run(rows, provider, auction_entry=True, auction_match_quantity=1, require_end_flat=True)
        self.assertEqual([o.quantity for o in result.orders], [3, 2, 1, 1])
        self.assertEqual([o.filled_quantity for o in result.orders], [1, 1, 1, 1])
        self.assertEqual([o.expired_quantity for o in result.orders], [2, 1, 0, 0])
        self.assertEqual(result.portfolio.quantity, 0)
        self.assertEqual([f.position_id for f in result.fills], ['A', 'B', 'A', 'B'])
        self.assertEqual(sum(point.trading_date == rows[-1].trading_date for point in result.equity_history), 1)


if __name__ == '__main__':
    unittest.main()
