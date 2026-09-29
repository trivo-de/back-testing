"""Frozen inputs and full responses before the inline-payload engine upgrade."""
from datetime import date, datetime
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import unittest
from uuid import UUID

from backtest_hpg.application.contracts import RunConfig
from backtest_hpg.application.result_mapper import result_to_dict
from backtest_hpg.config import CANSLIM_BREAKOUT_V0
from backtest_hpg.domain.market import Bar, StrategyBar
from backtest_hpg.domain.strategies.canslim_breakout_v0 import run


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


class V0BaselineSnapshotTest(unittest.TestCase):
    def test_frozen_daily_and_intraday_responses(self):
        data = json.loads((Path(__file__).parent / 'fixtures/v0-baseline.json').read_text(encoding='utf-8'))
        for case in data['cases']:
            with self.subTest(symbol=case['symbol']):
                inputs = case['input']
                self.assertEqual(digest(inputs), case['input_sha256'])
                self.assertEqual(digest(case['response']), case['response_sha256'])
                def bar(row, cls):
                    values = dict(row)
                    for key, value in values.items():
                        if value is None:
                            continue
                        if key in ('trading_date', 'close_time'):
                            values[key] = datetime.fromisoformat(value) if 'T' in value or ' ' in value else date.fromisoformat(value)
                        else:
                            values[key] = Decimal(value)
                    return cls(**values)
                bars = [bar(row, StrategyBar) for row in inputs['bars']]
                market = [bar(row, Bar) for row in inputs['market_bars']]
                config = dict(inputs['config'])
                for field in ('start_date', 'end_date'):
                    config[field] = date.fromisoformat(config[field])
                result = run(bars, market_bars=market or None, **inputs['args'])
                response = result_to_dict(UUID(int=1), {}, RunConfig(**config), result,
                                          strategy_parameters=CANSLIM_BREAKOUT_V0.parameters())
                self.assertEqual(response, case['response'])
                self.assertEqual(digest(response), case['response_sha256'])
