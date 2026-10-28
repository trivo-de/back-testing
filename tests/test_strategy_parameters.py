"""Ensure catalogue entries describe the same vocabulary that actually executes."""
from copy import deepcopy
import unittest
from fastapi.testclient import TestClient
from backtesting_api.api.app import create_app
from backtesting_api.api.price_schemas import PriceRunRequest
from backtesting_api.application.strategy_parameters import strategy_parameters
from backtesting_api.domain.expressions import COMPARE, NUMERIC, CROSS
from backtesting_api.domain.strategy_terms import ALIASES
from test_price_strategy import bars, run, request


class StrategyParametersTest(unittest.TestCase):
    """Test discovery, contract parity and execution for every published alias/operator."""
    def test_endpoint_schema_defaults_and_examples(self):
        """Keep the catalogue tied to model schemas and explicit non-null examples."""
        response = TestClient(create_app()).get('/api/strategy-parameters')
        self.assertEqual(response.status_code, 200)
        catalog = response.json()
        self.assertEqual(catalog['request_schema'], PriceRunRequest.model_json_schema(by_alias=True))
        self.assertEqual(catalog['defaults']['quantity'], 1)
        self.assertFalse(catalog['defaults']['allow_overnight'])
        self.assertEqual(catalog['defaults']['session_end_action'], 'close_at_close')
        self.assertEqual(catalog['default_profile_version'], 'price-only-v2')
        for item in catalog['parameters']:
            self.assertIsNotNone(item['example'], item['id'])
            self.assertTrue(item['name'])
            self.assertIn('scope', item)
            self.assertIn('unit', item)
        for example in catalog['examples']:
            PriceRunRequest.model_validate(example['payload'])
        specs = {item['id']: item for item in catalog['aliases']}
        self.assertEqual(specs['macd12_26_9']['minimum_samples'], 34)
        self.assertEqual(specs['market.mfi14']['minimum_samples'], 15)
        for prefix in ('', 'market.'):
            for alias, spec in ALIASES.items():
                self.assertEqual(specs[prefix + alias]['parameters'], spec)

    def test_every_alias_output_compiles_and_executes(self):
        """Exercise distinct trade/market sources and every BB/MACD output."""
        rows = bars([('100', '101', '99', '100')] * 80)
        for alias in strategy_parameters()['aliases']:
            outputs = alias['outputs'] or [None]
            for output in outputs:
                identifier = alias['id'] + ('.' + output if output else '')
                condition = {'all': [{'left': identifier, 'op': 'above', 'right': 0}, {'gt': [0, 1]}]}
                with self.subTest(alias=identifier):
                    result = run(request(entry={'long': condition}), rows, rows)
                    self.assertEqual(result['evaluations'][-1]['status'], 'EVALUABLE')
                    self.assertFalse(result['fills'])

    def test_every_operator_example_compiles_and_executes(self):
        """Evaluate published expression examples, rather than testing names alone."""
        rows = bars([('100', '101', '99', '100')] * 80)
        published = strategy_parameters()['operators']
        self.assertEqual({item['id'] for item in published},
                         {*COMPARE, *NUMERIC, *CROSS, 'above', 'below', 'all', 'any', 'floor', 'range', 'ref'})
        for item in published:
            example = deepcopy(item['example'])
            boolean = item['id'] in {*COMPARE, *CROSS, 'above', 'below', 'all', 'any', 'range'}
            candidate = example if boolean else {'gt': [example, -1000000]}
            with self.subTest(operator=item['id']):
                value = request(entry={'long': {'all': [candidate, {'gt': [0, 1]}]}})
                result = run(value, rows, rows)
                self.assertEqual(result['evaluations'][-1]['status'], 'EVALUABLE')
                self.assertFalse(result['fills'])
