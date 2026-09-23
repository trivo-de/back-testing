from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import json
import unittest
from uuid import UUID

from backtest_hpg.application.contracts import RunConfig
from backtest_hpg.application.result_mapper import result_to_dict
from backtest_hpg.config import CANSLIM_BREAKOUT_V0
from backtest_hpg.domain.market import Bar, StrategyBar
from backtest_hpg.domain.strategies.canslim_breakout_v0 import run as run_strategy


D = Decimal


def strategy_bars() -> list[StrategyBar]:
    start = date(2025, 1, 1)
    bars = [StrategyBar(start + timedelta(days=i), D(90), D(100), D(80), D(90), D(1000), D(100)) for i in range(203)]
    bars[200] = StrategyBar(bars[200].trading_date, D(100), D(101), D(99), D(101), D(1500), D(101))
    bars[201] = StrategyBar(bars[201].trading_date, D(102), D(121), D(100), D(120), D(1000), D(101))
    bars[202] = StrategyBar(bars[202].trading_date, D(122), D(123), D(121), D(122), D(1000), D(101))
    return bars


class StrategyBacktestTest(unittest.TestCase):
    def test_pre_refactor_response_baselines(self):
        # Captured before R1/R2, with fixed run ID and complete legacy response.
        cases = [
            (203, 10000, "2f8e1632ee476503d75f0067f309cd5289d4726dab9092ebc68f7cc717151d5d"),
            (202, 10000, "0218c5197d0a64eb1863454c2dbe10ccfe89c9a09b83d0978b7f5935fba696df"),
            (201, 10000, "5df060ddd5953fa0707544655619e0ff5ad3f612fad240300b849522bdde9df7"),
            (203, 1, "622024037da6196b6a6b4fcf2392b2ed30f3b43f703c5605f776e7922115b48b"),
        ]
        for count, cash, expected in cases:
            with self.subTest(count=count, cash=cash):
                bars = strategy_bars()[:count]
                config = RunConfig("fixture", "1", "HPG", bars[0].trading_date, bars[-1].trading_date,
                                   "canslim_breakout_v0", cash, "0.001", "0.002")
                result = run_strategy(bars, initial_cash=cash, fee_rate="0.001", slippage_rate="0.002")
                response = result_to_dict(UUID(int=1), {}, config, result,
                                          strategy_parameters=CANSLIM_BREAKOUT_V0.parameters())
                self.assertEqual(hashlib.sha256(json.dumps(response, sort_keys=True).encode()).hexdigest(), expected)

        daily = strategy_bars()
        start = datetime(2026, 3, 18, 9, tzinfo=timezone(timedelta(hours=7)))
        bars = [replace(b, trading_date=start + timedelta(minutes=5*i), index_close=None,
                        close_time=start + timedelta(minutes=5*(i+1))) for i, b in enumerate(daily)]
        market = [Bar(b.trading_date, daily[i].index_close, daily[i].index_close, b.close_time)
                  for i, b in enumerate(bars)]
        config = RunConfig("fixture", "1", "VN30F1M", start.date(), bars[-1].trading_date.date(),
                           "canslim_breakout_v0", 10000, "0.001", "0.002")
        result = run_strategy(bars, market_bars=market, initial_cash=10000, fee_rate="0.001", slippage_rate="0.002")
        response = result_to_dict(UUID(int=1), {}, config, result,
                                  strategy_parameters=CANSLIM_BREAKOUT_V0.parameters())
        self.assertEqual(hashlib.sha256(json.dumps(response, sort_keys=True).encode()).hexdigest(),
                         "55c2bb1fa30a9a27de63049acf818eb2f2db0fc611c45a6e9b49d45891d05add")

    def test_strategy_sizing_slippage_and_next_open(self):
        bars = strategy_bars()
        result = run_strategy(bars, initial_cash=10_000, fee_rate="0.001", slippage_rate="0.002")
        self.assertEqual([(signal.side, signal.reason) for signal in result.signals], [("BUY", "ALL_ENTRY_RULES_PASS"), ("SELL", "TAKE_PROFIT")])
        self.assertEqual((result.fills[0].fill_date, result.fills[0].price, result.fills[0].quantity), (bars[201].trading_date, D("102.204"), 27))
        self.assertEqual((result.fills[1].fill_date, result.fills[1].price), (bars[202].trading_date, D("121.756")))
        self.assertEqual((result.portfolio.cash, result.trades[0].net_pnl), (D("10521.857080"), D("521.857080")))

    def test_results_through_t_do_not_depend_on_future_bars(self):
        bars = strategy_bars()
        full = run_strategy(bars, initial_cash=10_000, fee_rate="0.001", slippage_rate="0.002")
        self.assertEqual(full, run_strategy(bars, initial_cash=10_000, fee_rate="0.001", slippage_rate="0.002"))
        truncated = run_strategy(bars[:201], initial_cash=10_000, fee_rate="0.001", slippage_rate="0.002")
        cutoff = bars[200].trading_date
        self.assertEqual(tuple(x for x in full.signals if x.signal_date <= cutoff), truncated.signals)
        self.assertEqual(tuple(x for x in full.equity_history if x.trading_date <= cutoff), truncated.equity_history)
        self.assertEqual((truncated.orders[-1].status, truncated.fills), ("PENDING", ()))
        open_position = run_strategy(bars[:202], initial_cash=10_000, fee_rate="0.001", slippage_rate="0.002")
        self.assertEqual(open_position.portfolio.position.quantity, 27)
        self.assertEqual((open_position.summary.final_equity, open_position.summary.unrealized_pnl), (D("10477.732492"), D("477.732492")))
        self.assertEqual(open_position.orders[-1].status, "PENDING")


if __name__ == "__main__":
    unittest.main()
