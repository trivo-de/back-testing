from copy import deepcopy
from decimal import Decimal
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).parent))

from fastapi.testclient import TestClient
from pydantic import ValidationError

from backtesting_api.api.app import create_app
from backtesting_api.api.inline_schemas import InlineRunRequest
from backtesting_api.application.inline_data import resolve_inline
from backtesting_api.application.inline_strategy import run_inline_strategy
from backtesting_api.application.run_backtest import BacktestService
from test_inline_strategy import sample


def make_raw(times, base=1000):
    return {
        's': 'ok',
        't': list(times),
        'o': [f'{base}.10' for _ in times],
        'h': [f'{base + 2}.00' for _ in times],
        'l': [f'{base - 1}.00' for _ in times],
        'c': [f'{base}.50' for _ in times],
        'v': [1000 for _ in times],
    }


class RawDataInputTest(unittest.TestCase):
    def test_auto_fetch_data_is_rejected_as_extra_field(self):
        base = sample()
        base['auto_fetch_data'] = True
        with self.assertRaises(ValidationError):
            InlineRunRequest.model_validate(base)

    def test_raw_trade_data_and_market_data_are_parsed_into_bars(self):
        base = sample()
        timestamps = [1773799200 + i * 300 for i in range(160)]
        base['trade_data'] = make_raw(timestamps, 1200)
        base['market_data'] = make_raw(timestamps, 1250)

        validated = InlineRunRequest.model_validate(base)
        self.assertEqual(len(validated.trade_data.bars), 160)
        self.assertEqual(validated.trade_data.resolution, '5')
        self.assertEqual(validated.trade_data.bars[0].open, Decimal('1200.10'))
        self.assertEqual(validated.trade_data.bars[0].high, Decimal('1202.00'))
        self.assertEqual(validated.trade_data.bars[0].low, Decimal('1199.00'))
        self.assertEqual(validated.trade_data.bars[0].close, Decimal('1200.50'))
        self.assertEqual(validated.trade_data.bars[0].volume, Decimal('1000'))
        self.assertEqual(validated.market_data.bars[0].open, Decimal('1250.10'))

    def test_raw_data_with_nested_or_metadata(self):
        base = sample()
        timestamps = [1773799200 + i * 300 for i in range(160)]
        base['trade_data'] = {
            'symbol': 'VN30F1M',
            'resolution': '5',
            'bars': make_raw(timestamps, 1300),
        }
        base['market_data'] = {
            'symbol': 'VNINDEX',
            'raw': make_raw(timestamps, 1280),
        }
        validated = InlineRunRequest.model_validate(base)
        self.assertEqual(validated.trade_data.symbol, 'VN30F1M')
        self.assertEqual(validated.trade_data.bars[0].open, Decimal('1300.10'))
        self.assertEqual(validated.market_data.symbol, 'VNINDEX')
        self.assertEqual(validated.market_data.bars[0].open, Decimal('1280.10'))

    def test_raw_data_validation_errors(self):
        base = sample()
        timestamps = [1773799200 + i * 300 for i in range(10)]

        # Status not ok
        bad_status = deepcopy(base)
        bad_status['trade_data'] = make_raw(timestamps)
        bad_status['trade_data']['s'] = 'error'
        with self.assertRaisesRegex(ValidationError, 'Invalid snapshot status'):
            InlineRunRequest.model_validate(bad_status)

        # Unequal array lengths
        unequal = deepcopy(base)
        unequal['trade_data'] = make_raw(timestamps)
        unequal['trade_data']['o'].pop()
        with self.assertRaisesRegex(ValidationError, 'Empty or unequal OHLCV arrays'):
            InlineRunRequest.model_validate(unequal)

        # Non-increasing timestamps
        non_increasing = deepcopy(base)
        non_increasing['trade_data'] = make_raw([1000, 1000, 1005])
        with self.assertRaisesRegex(ValidationError, 'Timestamps must be strictly increasing Unix seconds'):
            InlineRunRequest.model_validate(non_increasing)

        # Invalid OHLC range (low > high)
        bad_range = deepcopy(base)
        bad_range['trade_data'] = make_raw([1773799200])
        bad_range['trade_data']['l'] = ['2000.0']
        bad_range['trade_data']['h'] = ['1000.0']
        with self.assertRaisesRegex(ValidationError, 'Invalid OHLCV range'):
            InlineRunRequest.model_validate(bad_range)

    def test_resolve_inline_supports_raw_data_directly(self):
        base = sample()
        timestamps = [1773799200 + i * 300 for i in range(160)]
        base['trade_data'] = make_raw(timestamps, 1200)
        base['market_data'] = make_raw(timestamps, 1250)

        data = resolve_inline(base)
        self.assertEqual(len(data.bars), 160)
        self.assertEqual(len(data.market_bars), 160)
        self.assertEqual(data.bars[0].open, Decimal('1200.10'))

    def test_api_validate_and_run_with_raw_payload(self):
        import tempfile
        from pathlib import Path
        from backtesting_api.infrastructure.file_repository import FileRunRepository
        from test_inline_runtime import approved_payload

        def to_raw(bars):
            return {
                's': 'ok',
                't': [b['time'] for b in bars],
                'o': [b['open'] for b in bars],
                'h': [b['high'] for b in bars],
                'l': [b['low'] for b in bars],
                'c': [b['close'] for b in bars],
                'v': [b.get('volume', '100') for b in bars],
            }

        with tempfile.TemporaryDirectory() as directory:
            repository = FileRunRepository(Path(directory), Path('unused'))
            service = BacktestService(repository, inline_runner=run_inline_strategy)
            client = TestClient(create_app(service))

            p = approved_payload()
            # Convert trade_data bars to raw fields
            p['trade_data'] = {**p['trade_data'], **to_raw(p['trade_data'].pop('bars'))}
            # Convert market_data bars to raw fields
            p['market_data'] = {**p['market_data'], **to_raw(p['market_data'].pop('bars'))}

            # Validate endpoint
            validate_res = client.post('/api/backtests/validate', json=p)
            self.assertEqual(validate_res.status_code, 200)
            self.assertEqual(validate_res.json()['status'], 'STRUCTURE_VALID')
            self.assertTrue(validate_res.json()['runnable'])

            # Run endpoint
            run_res = client.post('/api/backtests', json=p)
            self.assertEqual(run_res.status_code, 201, run_res.text)
            self.assertIn('run_id', run_res.json()['metadata'])



if __name__ == '__main__':
    unittest.main()
