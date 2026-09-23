"""R2 technical fixtures, not a second production trading strategy."""

from dataclasses import fields, replace
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal as D
import unittest
from uuid import UUID

from backtest_hpg.application.contracts import RunConfig
from backtest_hpg.application.result_mapper import result_to_dict
from backtest_hpg.domain.engine import run_engine, run_fixed_signals
from backtest_hpg.domain.market import Bar
from backtest_hpg.domain.strategies.canslim_breakout_v0 import CanslimStrategy, size_buy
from backtest_hpg.domain.trading import FixedSignal


def bars():
    return [Bar(date(2026, 1, i), D(100), D(100)) for i in range(1, 6)]


class EngineContractTest(unittest.TestCase):
    def test_fixed_quantity_without_stop_or_market_and_mapper_compatibility(self):
        data = bars()
        result = run_fixed_signals(data, {data[0].trading_date: FixedSignal("BUY", 2)},
                                   initial_cash=1000, fee_rate="0.001")
        self.assertEqual(result.portfolio.cash, D("799.800"))
        self.assertEqual(result.position_details, ())
        self.assertEqual({f.name for f in fields(result.portfolio.position)}, {"quantity", "entry_price", "entry_fee"})
        # Only test the mapper; no additional strategy is registered/exposed by API.
        config = RunConfig("fixture", "1", "HPG", data[0].trading_date, data[-1].trading_date,
                           "canslim_breakout_v0", 1000, "0.001", 0)
        response = result_to_dict(UUID(int=1), {}, config, result, strategy_parameters={})
        self.assertIsNone(response["signals"][0]["pivot"])
        self.assertIsNone(response["open_position"]["entry_pivot"])
        self.assertIsNone(response["open_position"]["stop_reference"])

    def test_sizing_at_open_and_only_fill_context(self):
        data = bars()[:2]
        data[1] = replace(data[1], open=D(200), close=D(999))
        seen = []

        def sizing(context):
            seen.append(context)
            return size_buy(context)

        result = run_fixed_signals(data, {data[0].trading_date: FixedSignal("BUY")},
                                   initial_cash=10000, fee_rate="0.001", slippage_rate="0.01", size_buy=sizing)
        self.assertEqual(len(seen), 1)
        self.assertEqual({f.name for f in fields(seen[0])}, {"cash", "fill_price", "fee_rate"})
        self.assertEqual((seen[0].cash, seen[0].fill_price, seen[0].fee_rate), (D(10000), D(202), D("0.001")))
        self.assertEqual(result.fills[0].quantity, 14)
        # Changing the unknown Close cannot affect sizing at this Open.
        changed = run_fixed_signals([data[0], replace(data[1], close=D(1))],
                                    {data[0].trading_date: FixedSignal("BUY")}, initial_cash=10000,
                                    fee_rate="0.001", slippage_rate="0.01", size_buy=sizing)
        self.assertEqual(changed.fills, result.fills)

    def test_state_feedback_rejection_fill_exit_and_final_pending(self):
        data = bars()
        state = CanslimStrategy()
        observed = []
        signals = {
            data[0].trading_date: FixedSignal("BUY", 100, details=(("pivot", D(90)),)),
            data[1].trading_date: FixedSignal("BUY", 2, details=(("pivot", D(95)),)),
            data[2].trading_date: FixedSignal("SELL", details=(("pivot", D(95)),)),
            data[4].trading_date: FixedSignal("BUY", 1, details=(("pivot", D(99)),)),
        }

        def feedback(signal, order, fill):
            state.on_execution(signal, order, fill)
            observed.append((order.status, state.entry_pivot, state.stop_reference))

        result = run_fixed_signals(data, signals, initial_cash=1000, fee_rate=0, on_execution=feedback)
        self.assertEqual(observed, [("REJECTED", None, None), ("FILLED", D(95), D(93)), ("FILLED", None, None)])
        self.assertEqual(result.orders[-1].status, "PENDING")
        self.assertEqual(len(result.fills), 2)
        self.assertIsNone(state.entry_pivot)
        holding = CanslimStrategy()
        run_fixed_signals(data[:2], {data[0].trading_date: signals[data[1].trading_date]},
                          initial_cash=1000, fee_rate=0, on_execution=holding.on_execution)
        self.assertEqual(holding.entry_pivot, D(95))
        self.assertIsNone(CanslimStrategy().entry_pivot)

    def test_context_is_completed_prefix_and_feedback_precedes_next_decision(self):
        start = datetime(2026, 3, 18, 9, tzinfo=timezone(timedelta(hours=7)))
        data = [Bar(start + timedelta(minutes=5*i), D(100), D(100),
                    start + timedelta(minutes=5*(i+1))) for i in range(3)]
        support = [replace(data[0], close_time=start + timedelta(minutes=7)),
                   replace(data[1], close_time=start + timedelta(minutes=16))]
        contexts, events = [], []

        def evaluate(context):
            contexts.append(context)
            events.append("decision")
            return FixedSignal("BUY", 1) if len(context.bars) == 1 else None

        def feedback(signal, order, fill):
            events.append("fill")

        run_engine(data, evaluate, support_bars=support, initial_cash=1000, fee_rate=0,
                   slippage_rate=0, on_execution=feedback)
        self.assertEqual(events, ["decision", "fill", "decision", "decision"])
        self.assertEqual([len(c.bars) for c in contexts], [1, 2, 3])
        self.assertEqual([len(c.support_bars) for c in contexts], [0, 1, 1])
        self.assertIsNone(contexts[0].portfolio.position)
        self.assertEqual(contexts[1].portfolio.position.quantity, 1)
        with self.assertRaises(IndexError):
            _ = contexts[0].bars[1]
        self.assertEqual(contexts[0].support_bars, ())
        with self.assertRaisesRegex(ValueError, "aware"):
            run_engine(data, evaluate, support_bars=[replace(support[0], close_time=None)],
                       initial_cash=1000, fee_rate=0, slippage_rate=0)

    def test_invalid_sizing_and_unsupported_execution_fail_explicitly(self):
        data = bars()[:3]
        for quantity in (0, -1, True, D(1), 10000):
            result = run_fixed_signals(data, {data[0].trading_date: FixedSignal("BUY")},
                                       initial_cash=1000, fee_rate=0, size_buy=lambda _, q=quantity: q)
            self.assertEqual((result.orders[0].status, result.fills), ("REJECTED", ()))
        no_sizing = run_fixed_signals(data, {data[0].trading_date: FixedSignal("BUY")}, initial_cash=1000, fee_rate=0)
        self.assertIn("sizing policy", no_sizing.orders[0].reason)
        with self.assertRaisesRegex(ValueError, "Open"):
            run_fixed_signals([data[0], replace(data[1], open=D(0))],
                              {data[0].trading_date: FixedSignal("BUY")}, initial_cash=1000,
                              fee_rate=0, size_buy=size_buy)
        with self.assertRaisesRegex(ValueError, "partial SELL"):
            run_fixed_signals(data, {data[0].trading_date: FixedSignal("BUY", 2),
                                     data[1].trading_date: FixedSignal("SELL", 1)}, initial_cash=1000, fee_rate=0)
        with self.assertRaisesRegex(ValueError, "side"):
            run_fixed_signals(data, {data[0].trading_date: FixedSignal("SHORT", 1)}, initial_cash=1000, fee_rate=0)
        for details in ({"pivot": D(1)}, (("pivot", D("NaN")),), (("pivot", D(1)), ("pivot", D(2)))):
            with self.assertRaises(ValueError):
                FixedSignal("BUY", 1, details=details)


if __name__ == "__main__":
    unittest.main()
