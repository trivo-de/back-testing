"""Validate inline strategy payloads and expressions without running v1 rules."""
from copy import deepcopy
from decimal import Decimal as D
import json
from pathlib import Path
import unittest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from backtest_hpg.api.app import create_app
from backtest_hpg.api.inline_schemas import InlineRunRequest
from backtest_hpg.application.run_backtest import BacktestService
from backtest_hpg.domain.expressions import evaluate_expression, validate_expression, MissingValue
from test_application_api import MemoryRepository


def sample():
    # Use the tracked example rather than the local data/payload.json file.
    doc = (Path(__file__).parents[1] / 'docs/design/backtest-api-specification.md').read_text(encoding='utf-8')
    return json.loads(doc.split('```json\n', 1)[1].split('```', 1)[0])


class InlineStrategyTest(unittest.TestCase):
    def test_sample_and_new_strategy_without_market_or_template(self):
        payload = sample()
        request = InlineRunRequest.model_validate(payload)
        self.assertEqual(request.strategy.warmup_bars, 150)
        del payload['accounting']['contract_multiplier']
        payload.pop('market_data')
        payload['trade_data'].pop('symbol', None)
        payload['strategy'] = {
            'entry': {'conditions': {'LONG': {'gt': [{'ref': 'trade_data.close'}, 10]}}, 'any': ['LONG']},
            'exit': {'bar_close': {'conditions': {'MY_EXIT': {'lt': [{'ref': 'trade_data.close'}, 9]}},
                     'any': ['MY_EXIT'], 'priority': ['MY_EXIT'], 'quantity': 'remaining', 'fill_policy': 'next_open'}},
            'sizing': payload['strategy']['sizing']}
        request = InlineRunRequest.model_validate(payload)
        self.assertIsNone(request.strategy.warmup_bars)
        self.assertIsNone(request.market_data)
        self.assertEqual(request.accounting.contract_multiplier, 100000)
        self.assertEqual(InlineRunRequest.model_validate(request.model_dump(mode='json', by_alias=True, exclude_none=True)), request)

    def test_bad_combinations_are_rejected(self):
        base = sample()
        mutations = [
            lambda p: p.pop('market_data'),
            lambda p: p['market_data']['bars'][0].pop('volume'),
            lambda p: p['trade_data']['bars'].reverse(),
            lambda p: p['trade_data']['bars'][0].update(high='1'),
            lambda p: p['trade_data']['bars'][0].update(available_at=0),
            lambda p: p['trade_data'].update(resolution='D'),
            lambda p: p['trade_data'].update(timestamp_unit='seconds'),
            lambda p: p['trade_data'].update(timezone='wrong/zone'),
            lambda p: p['accounting'].update(pit_rate='NaN'),
            lambda p: p['accounting'].update(margin_rate=0),
            lambda p: p.update(strategy_id='not-required'),
            lambda p: p['strategy']['entry'].update(require_flat=1),
            lambda p: p['strategy']['entry']['pending'].update(max_execution_bars=True),
            lambda p: p['strategy']['indicators']['ema5'].update(period=True),
            lambda p: p['strategy']['indicators']['ema5'].update(stddev_multiplier=2),
            lambda p: p['strategy']['indicators']['macd'].update(fast_period=30),
            lambda p: p['strategy']['exit']['intrabar'].update(priority=['TP1']),
            lambda p: p['strategy']['exit']['intrabar']['priority'].reverse(),
            lambda p: p['strategy']['entry']['conditions'].update(LONG={'gt': [{'ref': 'position.entry_price'}, 0]}),
            lambda p: p['strategy']['entry']['conditions'].update(LONG={'gt': [{'ref': 'no_such_indicator'}, 0]}),
            lambda p: p['strategy']['entry']['conditions'].update(LONG={'any': ['LONG']}),
            lambda p: p['strategy']['entry']['conditions'].update(LONG={'gt': [{'ref': 'macd.line', 'shift': -1}, 0]}),
            lambda p: p.update(report={'start_date': '2030-01-01', 'end_date': '2020-01-01'}),
            lambda p: p['trade_data']['contract_map'][0].update(expiry_unix=0),
        ]
        for change in mutations:
            with self.subTest(change=mutations.index(change)):
                payload = deepcopy(base)
                change(payload)
                with self.assertRaises(ValidationError): InlineRunRequest.model_validate(payload)

    def test_endpoint_does_not_run_or_store_and_schema_resolves(self):
        repository = MemoryRepository()
        client = TestClient(create_app(BacktestService(repository)))
        response = client.post('/api/backtests/validate', json=sample())
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body['status'], 'STRUCTURE_VALID')
        self.assertFalse(body['runnable'])
        self.assertEqual(client.post('/api/backtests/validate', json=body['payload']).status_code, 200)
        self.assertEqual(client.post('/api/backtests', json=sample()).status_code, 422)
        self.assertEqual(client.post('/api/backtests/validate', json={'strategy': {}}).status_code, 422)
        self.assertEqual(client.post('/api/backtests/validate', content='{bad').status_code, 422)
        document = client.get('/openapi.json').json()
        self.assertIn('InlineRunRequest', document['components']['schemas'])

    def test_expression_types_missing_data_and_available_prefix(self):
        rule = {'all': [{'gt': [{'ref': 'macd.line'}, {'ref': 'macd.line', 'shift': 1}]},
                        {'gte': [{'ref': 'clock.local_time'}, '09:05']}]}
        values = {'macd.line': [D('1'), D('2')], 'clock.local_time': '09:05'}
        self.assertTrue(evaluate_expression(rule, values))
        self.assertTrue(evaluate_expression({'any': ['ENTRY']}, values, {'ENTRY': rule}))
        self.assertEqual(evaluate_expression({'floor': [{'div': [5, 2]}]}, {}), 2)
        self.assertEqual(evaluate_expression({'sub': [.3, .1]}, {}), D('.2'))
        for bad in ({'all': [1]}, {'gt': [1, '14:20']}, {'eval': ['import os']},
                    {'div': [1, 0]}, {'ref': 'macd.line', 'shift': True},
                    {'ref': 'macd.line', 'shift': -1}, {'ref': 'clock.local_time', 'shift': 0}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                validate_expression(bad, set(values))
        for history in ([D('1')], [D('1'), None]):
            with self.assertRaises(MissingValue):
                evaluate_expression(rule, {**values, 'macd.line': history})
        # Future values affect evaluation only after they enter the available series.
        history = [D('1'), D('2'), D('-999')]
        self.assertTrue(evaluate_expression(rule, {**values, 'macd.line': history[:2]}))
        self.assertFalse(evaluate_expression(rule, {**values, 'macd.line': history}))
        deep = 1
        for _ in range(34): deep = {'add': [deep, 1]}
        with self.assertRaisesRegex(ValueError, 'TOO_DEEP'): validate_expression(deep, set())
        wide = {'all': [{'gt': [1, 0]}] * 1400}
        with self.assertRaisesRegex(ValueError, 'TOO_LARGE'): validate_expression(wide, set())
