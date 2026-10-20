from copy import deepcopy
import json
from pathlib import Path
import unittest

from backtesting_api.api.inline_schemas import InlineRunRequest
from backtesting_api.application.inline_data import resolve_inline
from backtesting_api.application.inline_strategy import run_inline_strategy
from backtesting_api.application.order_config import strategy_orders, order_configuration
from backtesting_api.application.run_backtest import _warmup_bars
from test_auto_fetch_data import automatic_payload
from test_inline_pipeline import normalized, payload
from test_session_matching import POLICY, ato_payload, session_payload


def modern(p):
    p = deepcopy(p)
    entries, exits = strategy_orders(p)
    entry = p['strategy']['entry']
    entry['actions'] = entries
    for key in ('limit_price', 'pending'):
        entry.pop(key, None)
    close = p['strategy']['exit'].get('bar_close')
    if close is not None:
        close['actions'] = {name: {'order': action['order']} for name, action in exits.items()}
        close.pop('fill_policy', None)
        close.pop('limit_price', None)
    p['execution'].pop('entry_fill_policy')
    p['execution'].setdefault('matching_model', 'next_open')
    return p


def execute(p):
    p = normalized(p)
    return run_inline_strategy(resolve_inline(p, POLICY), p)


class OrderStrategyTest(unittest.TestCase):
    def test_documented_order_payloads_validate_without_fetching_data(self):
        for filename, opening_type, closing_type in (('lo-auto.json', 'LO', 'SIMULATED'),
                                                      ('ato-atc-partial-auto.json', 'ATO', 'ATC')):
            p = json.loads((Path(__file__).parents[1] / 'docs/examples/orders' / filename).read_text(encoding='utf-8'))
            normalized(p)
            entries, closes = strategy_orders(p)
            with self.subTest(filename=filename):
                self.assertEqual({action['order']['type'] for action in entries.values()}, {opening_type})
                self.assertEqual({action['order']['type'] for action in closes.values()}, {closing_type})
                self.assertTrue(p['auto_fetch_data'])

    def test_effective_configuration_records_sources_without_mutating_payload(self):
        legacy = session_payload()
        legacy['strategy']['entry']['pending'] = {'max_execution_bars': 2}
        original = deepcopy(legacy)
        old = order_configuration(legacy)
        new = order_configuration(modern(legacy))
        self.assertEqual(legacy, original)
        self.assertEqual(old['entry']['LONG']['order'], new['entry']['LONG']['order'])
        self.assertEqual(old['entry']['LONG']['source'], 'execution.entry_fill_policy')
        self.assertEqual(new['entry']['LONG']['source'], 'strategy.entry.actions.LONG.order')
        self.assertEqual(old['entry']['LONG']['pending_source'], 'strategy.entry.pending')
        shared = modern(legacy)
        shared['strategy']['entry']['order'] = shared['strategy']['entry']['actions']['LONG'].pop('order')
        self.assertEqual(order_configuration(shared)['entry']['LONG']['source'], 'strategy.entry.order')

    def test_legacy_and_new_orders_have_identical_execution(self):
        normalized_payload = automatic_payload()
        normalized_payload.update(auto_fetch_data=False, trade_data=payload()['trade_data'])
        combined = session_payload(atc=True)
        combined['execution']['entry_fill_policy'] = 'next_open'
        combined['strategy']['entry'].pop('limit_price')
        for p in (normalized_payload, payload(), session_payload(), ato_payload(2),
                  session_payload(atc=True), combined):
            with self.subTest(execution=p['execution'], accounting=p['accounting']['model']):
                converted = modern(p)
                self.assertEqual(execute(p), execute(converted))
                self.assertEqual(execute(converted), execute(converted))

    def test_named_entry_uses_its_direction_and_order(self):
        p = modern(session_payload())
        entry = p['strategy']['entry']
        entry['conditions']['A'] = entry['conditions'].pop('LONG')
        entry['actions']['A'] = entry['actions'].pop('LONG')
        entry['any'] = ['A']
        result = execute(p)
        self.assertEqual(result.orders[0].order_type, 'LO')
        self.assertEqual(result.orders[0].side, 'LONG')

    def test_next_open_pending_lifetime_survives_conversion_on_a_gap(self):
        p = payload()
        p['strategy']['exit'].pop('allow_overnight', None)
        p['strategy']['exit'].pop('flat_by', None)
        p['trade_data']['bars'][1]['time'] += 300
        p['trade_data']['bars'][2]['time'] += 300
        old, new = execute(p), execute(modern(p))
        self.assertEqual(old, new)
        self.assertEqual((new.orders[0].status, new.orders[0].reason), ('REJECTED', 'PENDING_EXPIRED'))

    def test_single_position_priority_selects_first_matching_branch(self):
        p = modern(session_payload())
        entry = p['strategy']['entry']
        entry['conditions']['B'] = deepcopy(entry['conditions']['LONG'])
        entry['actions']['B'] = {'side': 'SHORT', 'order': {'type': 'LO', 'limit_price': {'ref': 'trade_data.close'}}}
        entry['any'] = ['LONG', 'B']
        entry['priority'] = ['B', 'LONG']
        entry.pop('on_conflict', None)
        p['strategy']['exit'].pop('intrabar', None)
        p['strategy']['exit']['targets'] = {}
        p['strategy']['exit']['bar_close'] = {'conditions': {'END': {'gte': [{'ref': 'position.held_bars'}, 1]}},
                                             'any': ['END'], 'priority': ['END'], 'quantity': 'remaining',
                                             'order': {'type': 'SIMULATED'}}
        self.assertEqual(execute(p).fills[0].direction, 'SHORT')
        entry['on_conflict'] = 'SIGNAL_CONFLICT'
        self.assertFalse(execute(p).fills)

    def test_rejects_unknown_order_mismatches_and_missing_refs(self):
        p = modern(session_payload())
        mutations = (
            lambda v: v['strategy']['entry']['actions']['LONG']['order'].update(type='MARKET'),
            lambda v: v['strategy']['entry']['actions']['LONG']['order'].pop('limit_price'),
            lambda v: v['execution'].update(matching_model='next_open'),
            lambda v: v['execution'].update(entry_fill_policy='ato'),
            lambda v: v['strategy']['entry']['actions']['LONG']['order'].update(limit_price={'ref': 'unknown'}),
            lambda v: v['strategy']['entry']['actions']['LONG']['order'].update(type='ATC', limit_price=None),
        )
        for mutation in mutations:
            changed = deepcopy(p)
            mutation(changed)
            with self.subTest(payload=changed['strategy']['entry']), self.assertRaises(ValueError):
                InlineRunRequest.model_validate(changed)

    def test_nested_price_refs_contribute_to_warmup_and_source_validation(self):
        p = modern(session_payload())
        p['strategy']['entry']['actions']['LONG']['order']['limit_price'] = {'ref': 'market_data.close', 'shift': 7}
        self.assertEqual(_warmup_bars(p['strategy']), 8)
        with self.assertRaisesRegex(ValueError, 'MISSING_REQUIRED_DATA: market_data'):
            normalized(p)
