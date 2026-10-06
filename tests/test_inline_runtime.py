"""Approved v1 formulas and timing on synthetic, reproducible price series."""
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta
from decimal import Decimal as D
from pathlib import Path
import io
import json
import os
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import urlsplit
from fastapi.testclient import TestClient
from backtesting_api.api.app import create_app
from backtesting_api.application.inline_data import resolve_inline
from backtesting_api.application.inline_strategy import run_inline_strategy, InlineExecution, IndicatorData
from backtesting_api.application.run_backtest import BacktestService
from backtesting_api.domain import indicators
from backtesting_api.domain.trading import FixedSignal
from backtesting_api.infrastructure.file_repository import FileRunRepository
from test_inline_pipeline import ZONE, candle, normalized, payload
from test_inline_strategy import sample
from test_contract_execution import bar


def day_bars(day, price=1000):
    return [candle(datetime(2026, 3, day, minute // 60, minute % 60, tzinfo=ZONE),
                   str(price), str(price + 1), str(price - 1), str(price))
            for lo, hi in ((540, 690), (780, 870)) for minute in range(lo, hi, 5)]


def approved_payload():
    p = sample()
    p['initial_cash'] = '500000000'
    p['trade_data'] = {'resolution': '5', 'bars': day_bars(26)}
    rows = [dict(row, volume='100') for day in (23, 24, 25, 26) for row in day_bars(day)]
    rows[149].update(open='1002', high='1003', low='1001', close='1002')
    p['market_data'] = {'resolution': '5', 'bars': rows}
    p['trade_data']['bars'][6].update(high='1013', close='1012')
    return normalized(p)


def always_payload():
    p = payload()
    p['initial_cash'] = '500000000'
    p['trade_data']['bars'] = day_bars(25)
    return normalized(p)


class InlineRuntimeTest(unittest.TestCase):
    def test_formulas_and_seed(self):
        self.assertEqual(indicators.ema([1, 2, 3, 4], 3, 2), None)
        self.assertEqual(indicators.ema([1, 2, 3, 4], 3, 3), 2)
        self.assertEqual(indicators.ema([1, 2, 3, 4], 3, 4), 3)
        bands = indicators.bb([1, 3], 2, 2, 2)
        self.assertEqual(bands, {'middle': 2, 'upper': 4, 'lower': 0})
        macd = indicators.macd(list(range(1, 41)), 40)
        self.assertEqual(macd['line'], D(7))
        self.assertEqual(macd['histogram'], macd['line'])
        self.assertEqual(macd['signal'], 7)
        flat = [bar(i) for i in range(15)]
        self.assertIsNone(indicators.mfi(flat, 14, 14))
        self.assertEqual(indicators.mfi(flat, 14, 15), 50)
        rising = [replace(b, high=D(1001+i), low=D(999+i), close=D(1000+i)) for i, b in enumerate(flat)]
        self.assertEqual(indicators.mfi(rising, 14, 15), 100)
        self.assertEqual(indicators.mfi(rising[::-1], 14, 15), 0)

    def test_150_includes_current_market_bar_and_partial_targets(self):
        p = approved_payload()
        data = resolve_inline(p)
        result = run_inline_strategy(data, p)
        self.assertEqual(result.evaluations[4]['market_sample_count'], 149)
        self.assertEqual(result.evaluations[4]['status'], 'UNEVALUABLE')
        self.assertEqual(result.evaluations[5]['market_sample_count'], 150)
        self.assertEqual(result.signals[0].side, 'LONG')
        self.assertEqual(result.signals[0].signal_date.strftime('%H:%M'), '09:30')
        self.assertEqual([f.quantity for f in result.fills[:3]], [5, 2, 3])
        self.assertEqual([f.price for f in result.fills[:3]], [1000, 1006, 1012])
        self.assertEqual(result.evaluations[6]['reason'], 'REENTRY_WAIT')
        self.assertEqual(result, run_inline_strategy(data, p))

    def test_future_market_and_report_tail_do_not_change_past(self):
        p = approved_payload()
        full = run_inline_strategy(resolve_inline(p), p)
        altered = deepcopy(p)
        for row in altered['market_data']['bars'][160:]: row.update(open='999', close='999', high='1000', low='998')
        changed = run_inline_strategy(resolve_inline(altered), altered)
        self.assertEqual(full.evaluations[:16], changed.evaluations[:16])
        cut = deepcopy(p)
        cut['trade_data']['bars'] = cut['trade_data']['bars'][:8]
        cut['market_data']['bars'] = cut['market_data']['bars'][:152]
        short = run_inline_strategy(resolve_inline(cut), cut)
        self.assertEqual(short.fills, full.fills[:len(short.fills)])
        self.assertEqual(short.equity_history, full.equity_history[:8])

    def test_market_gap_reset_excludes_auction_and_preserves_rollover_history(self):
        p = approved_payload()
        data = resolve_inline(p)
        market = list(data.market_bars)
        market[148] = replace(market[148], data_gap_before=True)
        reset = replace(data, market_bars=tuple(market))
        series = IndicatorData(reset, p)
        _, counts, _ = series.at(market[149].available_at)
        self.assertEqual(counts['market_data'], 2)
        original = IndicatorData(data, p)
        rolled = replace(data, bars=tuple(replace(b, contract_code='SECOND' if i > 5 else 'FIRST') for i, b in enumerate(data.bars)))
        self.assertEqual(original.values['ema5'], IndicatorData(rolled, p).values['ema5'])
        auction = replace(market[0], trading_date=market[0].trading_date.replace(hour=8, minute=45),
                          close_time=market[0].closed_at.replace(hour=8, minute=50), available_at=market[0].available_at.replace(hour=8, minute=50))
        with_auction = IndicatorData(replace(data, market_bars=(auction, *data.market_bars)), p)
        self.assertEqual(original.values['ema5'], with_auction.values['ema5'])

    def test_forced_exit_priority_missing_bar_and_end_of_report(self):
        p = always_payload()
        p['strategy']['entry']['signal_windows'] = [['14:00', '14:00']]
        result = run_inline_strategy(resolve_inline(p), p)
        self.assertEqual(result.fills[0].fill_date.strftime('%H:%M'), '14:00')
        self.assertEqual(result.fills[-1].fill_date.strftime('%H:%M'), '14:20')
        self.assertEqual(result.signals[-1].reason, 'FORCED_EXIT')
        bad = deepcopy(p)
        bad['trade_data']['bars'] = [b for b in bad['trade_data']['bars'] if datetime.fromtimestamp(b['time'], ZONE).strftime('%H:%M') != '14:20']
        with self.assertRaisesRegex(ValueError, 'MISSING_.*BAR'):
            run_inline_strategy(resolve_inline(bad), bad)
        cut = deepcopy(p)
        cut['trade_data']['bars'] = cut['trade_data']['bars'][:-4]
        with self.assertRaisesRegex(ValueError, 'REQUIRES_EXIT'):
            run_inline_strategy(resolve_inline(cut), cut)
        pending = always_payload()
        pending['trade_data']['bars'] = pending['trade_data']['bars'][:1]
        result = run_inline_strategy(resolve_inline(pending), pending)
        self.assertEqual(result.orders[-1].reason, 'END_OF_REPORT')
        self.assertEqual(result.fills, ())

    def test_daily_entry_limit_conflict_and_sizing_without_future_prices(self):
        p = always_payload()
        for row in p['trade_data']['bars']: row.update(high='1013', close='1012')
        result = run_inline_strategy(resolve_inline(p), p)
        self.assertEqual(sum(f.side == 'LONG' for f in result.fills), 3)
        self.assertTrue(any(e['reason'] == 'DAILY_ENTRY_LIMIT' for e in result.evaluations))
        conflict = deepcopy(p)
        conflict['strategy']['entry']['conditions']['SHORT'] = conflict['strategy']['entry']['conditions']['LONG']
        conflict['strategy']['entry']['any'].append('SHORT')
        conflict['strategy']['exit']['targets']['SHORT'] = sample()['strategy']['exit']['targets']['SHORT']
        result = run_inline_strategy(resolve_inline(conflict), conflict)
        self.assertEqual(result.fills, ())
        self.assertEqual(result.evaluations[0]['reason'], 'SIGNAL_CONFLICT')
        execution = InlineExecution('100000000', p)
        stamp = datetime(2026, 3, 25, 9, 5, tzinfo=ZONE)
        execution.before_open(stamp)
        fill, _ = execution.execute(FixedSignal('LONG'), stamp, stamp, D(1000))
        self.assertEqual(fill.quantity, 1)
        self.assertEqual(fill.price, 1000)

    def test_real_runner_api_and_reload(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = FileRunRepository(Path(directory), Path('unused'))
            service = BacktestService(repository, inline_runner=run_inline_strategy)
            client = TestClient(create_app(service))
            p = approved_payload()
            ready = client.post('/api/backtests/validate', json=p)
            self.assertTrue(ready.json()['runnable'])
            response = client.post('/api/backtests', json=p)
            self.assertEqual(response.status_code, 201, response.text)
            body = response.json()
            self.assertTrue(body['fills'])
            self.assertTrue(body['evaluations'])
            reloaded = client.get('/api/backtests/' + body['metadata']['run_id'])
            self.assertEqual(reloaded.json(), body)
            p['execution']['slippage_rate'] = '.01'
            self.assertEqual(client.post('/api/backtests/validate', json=p).status_code, 422)

    def test_results_notebook_uses_the_json_payload_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payload_path = root / 'payload.json'
            payload_path.write_text(json.dumps(approved_payload()), encoding='utf-8')
            repository = FileRunRepository(root / 'store', root / 'unused')
            client = TestClient(create_app(BacktestService(repository, inline_runner=run_inline_strategy)))

            def open_api(request, timeout=120):
                url = request if isinstance(request, str) else request.full_url
                route = urlsplit(url).path
                response = (client.get(route) if isinstance(request, str)
                            else client.request(request.get_method(), route, content=request.data,
                                                headers={'Content-Type': 'application/json'}))
                body = io.BytesIO(json.dumps(response.json()).encode())
                if response.status_code >= 400:
                    raise HTTPError(url, response.status_code, 'API error', {}, body)
                return body

            notebook = json.loads(Path('notebooks/backtest-results.ipynb').read_text(encoding='utf-8'))
            namespace = {}
            with patch.dict(os.environ, {'BACKTEST_PAYLOAD': str(payload_path)}), \
                    patch('urllib.request.urlopen', side_effect=open_api), \
                    patch('IPython.display.display'):
                for index, cell in enumerate(notebook['cells']):
                    if cell['cell_type'] == 'code':
                        exec(compile(''.join(cell['source']), f'notebook-cell-{index}', 'exec'), namespace)
            self.assertEqual(namespace['result'], namespace['reloaded_result'])
            self.assertEqual(namespace['payload']['trade_data']['resolution'], '5')

    def test_time_stop_counts_entry_bar_and_lunch_is_not_a_bar(self):
        p = always_payload()
        p['strategy']['entry']['signal_windows'] = [['11:20', '11:20']]
        result = run_inline_strategy(resolve_inline(p), p)
        self.assertEqual(result.fills[0].fill_date.strftime('%H:%M'), '11:20')
        self.assertEqual(result.fills[-1].fill_date.strftime('%H:%M'), '14:20')
        self.assertEqual(result.signals[-1].reason, 'FORCED_EXIT')
        p['strategy']['entry']['signal_windows'] = [['09:05', '09:05']]
        result = run_inline_strategy(resolve_inline(p), p)
        self.assertEqual(result.fills[-1].fill_date.strftime('%H:%M'), '10:35')
        self.assertEqual(result.signals[-1].reason, 'TIME_STOP')

    def test_approved_short_and_daily_loss_cutoff(self):
        p = approved_payload()
        row = p['market_data']['bars'][149]
        row.update(open='998', high='999', low='997', close='998')
        p['trade_data']['bars'][6].update(high='1001', low='987', close='988')
        result = run_inline_strategy(resolve_inline(p), p)
        self.assertEqual([f.side for f in result.fills[:3]], ['SHORT', 'CLOSE', 'CLOSE'])
        self.assertEqual([f.price for f in result.fills[:3]], [1000, 994, 988])
        p = always_payload()
        p['initial_cash'] = '100000000'
        p['trade_data']['bars'][2].update(open='970', high='971', low='969', close='970')
        result = run_inline_strategy(resolve_inline(p), p)
        self.assertEqual(sum(f.side == 'LONG' for f in result.fills), 1)
        self.assertTrue(any(e['reason'] == 'DAILY_ENTRY_LIMIT' for e in result.evaluations))

    def test_canslim_v0_tree_matches_the_frozen_intraday_result(self):
        document = json.loads((Path(__file__).parent / 'fixtures/v0-baseline.json').read_text(encoding='utf-8'))
        case = next(item for item in document['cases'] if item['symbol'] == 'VN30F1M')

        def rows(values, market=False):
            result = []
            for row in values:
                opened = datetime.fromisoformat(row['trading_date'])
                closed = datetime.fromisoformat(row['close_time'])
                close = row['close']
                result.append({'time': int(opened.timestamp()), 'close_time': int(closed.timestamp()),
                               'available_at': int(closed.timestamp()), 'open': row['open'],
                               'high': close if market else row['high'],
                               'low': close if market else row['low'], 'close': close,
                               **({} if market else {'volume': row['volume']})})
            return result

        strategy = {
            'indicators': {
                'market_sma': {'type': 'SMA', 'source': 'market_data.close', 'period': 200},
                'pivot': {'type': 'HIGHEST', 'source': 'trade_data.high', 'period': 65},
                'base_low': {'type': 'LOWEST', 'source': 'trade_data.low', 'period': 65},
                'average_volume': {'type': 'SMA', 'source': 'trade_data.volume', 'period': 50},
            },
            'entry': {
                'conditions': {'BUY': {'all': [
                    {'gt': [{'ref': 'market_data.close'}, {'ref': 'market_sma'}]},
                    {'lte': [{'div': [{'sub': [{'ref': 'pivot', 'shift': 1}, {'ref': 'base_low', 'shift': 1}]},
                                      {'ref': 'pivot', 'shift': 1}]}, .35]},
                    {'gt': [{'ref': 'trade_data.close'}, {'ref': 'pivot', 'shift': 1}]},
                    {'lte': [{'ref': 'trade_data.close'}, {'mul': [{'ref': 'pivot', 'shift': 1}, 1.05]}]},
                    {'gt': [{'ref': 'average_volume', 'shift': 1}, 0]},
                    {'gte': [{'ref': 'trade_data.volume'},
                             {'mul': [{'ref': 'average_volume', 'shift': 1}, 1.5]}]},
                ]}},
                'any': ['BUY'], 'require_flat': True, 'require_no_pending': True,
                'details': {'pivot': {'ref': 'pivot', 'shift': 1}},
            },
            'exit': {'bar_close': {
                'conditions': {
                    'STOP_LOSS': {'lte': [{'ref': 'trade_data.close'},
                                          {'mul': [{'ref': 'position.entry_price'}, .93]}]},
                    'TAKE_PROFIT': {'gte': [{'ref': 'trade_data.close'},
                                           {'mul': [{'ref': 'position.entry_pivot'}, 1.20]}]},
                },
                'any': ['STOP_LOSS', 'TAKE_PROFIT'], 'priority': ['STOP_LOSS', 'TAKE_PROFIT'],
                'quantity': 'remaining', 'fill_policy': 'next_open',
            }},
            'sizing': {'type': 'fixed_fractional', 'risk_fraction': '.02',
                       'stop_loss_fraction': '.07'},
        }
        request = normalized({
            'trade_data': {'resolution': '5', 'symbol': 'VN30F1M', 'bars': rows(case['input']['bars'])},
            'market_data': {'resolution': '5', 'bars': rows(case['input']['market_bars'], market=True)},
            'strategy': strategy,
            'execution': {'entry_fill_policy': 'next_open', 'slippage_rate': '.002'},
            'accounting': {'model': 'normalized', 'fee_rate': '.001'},
            'initial_cash': '10000',
            'report': {'start_date': case['input']['config']['start_date'],
                       'end_date': case['input']['config']['end_date']},
        })
        result = run_inline_strategy(resolve_inline(request), request)
        expected = case['response']
        self.assertEqual([(fill.price, fill.quantity) for fill in result.fills],
                         [(D(fill['fill_price']), fill['quantity']) for fill in expected['fills']])
        self.assertEqual(result.summary.final_equity, D(expected['summary']['final_equity']))
        self.assertEqual(result.summary.realized_pnl, D(expected['summary']['realized_pnl']))
        self.assertEqual(dict(result.signals[0].details)['pivot'], D(expected['signals'][0]['pivot']))
        with tempfile.TemporaryDirectory() as directory:
            repository = FileRunRepository(Path(directory), Path('unused'))
            client = TestClient(create_app(BacktestService(repository, inline_runner=run_inline_strategy)))
            response = client.post('/api/backtests', json=request)
            self.assertEqual(response.status_code, 201, response.text)
            body = response.json()
            self.assertEqual(body['metadata']['accounting_profile'], 'normalized_v0')
            self.assertEqual([(D(fill['fill_price']), fill['quantity']) for fill in body['fills']],
                             [(fill.price, fill.quantity) for fill in result.fills])
