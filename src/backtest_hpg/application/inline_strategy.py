"""Execute supported JSON rules using only completed, available data."""
from bisect import bisect_right
from dataclasses import replace
from datetime import datetime, time, timedelta
from decimal import Decimal
from ..domain import indicators
from ..domain.contract_accounting import ContractAccounting
from ..domain.engine import run_engine
from ..domain.execution import Bracket, ContractExecution, InvalidExecution, NormalizedExecution
from ..domain.expressions import evaluate_expression, MissingValue, STATE_REFS
from ..domain.portfolio import decimal
from ..domain.trading import FixedSignal, OrderResult


def continuous(stamp):
    local = stamp.strftime('%H:%M')
    return '09:00' <= local < '11:30' or '13:00' <= local < '14:30'


def check_runtime(payload):
    """Reject unsupported execution combinations before opening a stored run."""
    if payload['accounting']['model'] == 'contract':
        if payload['trade_data']['resolution'] != '5':
            raise ValueError('UNSUPPORTED_CONTRACT_RESOLUTION: expected 5')
        if decimal(payload['execution']['slippage_rate']) != 0:
            raise ValueError('UNSUPPORTED_CONTRACT_SLIPPAGE: expected 0')
    group = payload['strategy']['exit'].get('intrabar')
    if group:
        actions = [group['conditions'][name] for name in group['priority']]
        if sum(a['type'] == 'protective_stop' for a in actions) != 1:
            raise ValueError('INTRABAR_REQUIRES_ONE_PROTECTIVE_STOP')
        levels = [a['level'] for a in actions if a['type'] == 'target_touch']
        if levels not in ([], ['TP1'], ['TP1', 'TP2']):
            raise ValueError('UNSUPPORTED_TARGET_SEQUENCE')


class IndicatorData:
    def __init__(self, data, payload):
        self.rows, self.times, self.values, self.starts = {}, {}, {}, {}
        for source, rows in (('trade_data', data.bars), ('market_data', data.market_bars)):
            spec = payload.get(source)
            rows = [b for b in rows if spec and (payload['accounting']['model'] != 'contract'
                                                  or spec['resolution'] != '5' or continuous(b.trading_date))]
            self.rows[source] = rows
            self.times[source] = [b.available_at for b in rows]
            starts, start = [], 0
            gaps = [datetime.fromisoformat(s) for s in data.metadata['data_gaps'].get(source, [])]
            for index, bar in enumerate(rows):
                crossed_gap = index and bisect_right(gaps, bar.trading_date) > bisect_right(gaps, rows[index - 1].trading_date)
                if bar.data_gap_before or crossed_gap or (index and bar.contract_code != rows[index - 1].contract_code): start = index
                starts.append(start)
            self.starts[source] = starts
            for column in ('open', 'high', 'low', 'close', 'volume'):
                self.values[f'{source}.{column}'] = (source, [getattr(b, column) for b in rows])
        for name, spec in payload['strategy'].get('indicators', {}).items():
            source, _, column = spec['source'].partition('.')
            rows = self.rows[source]
            boundaries = sorted(set(self.starts[source])) + [len(rows)]
            outputs = {key: [] for key in ({'BB': ('middle', 'upper', 'lower'),
                                          'MACD': ('line', 'signal', 'histogram')}.get(spec['type'], ('value',)))}
            for begin, end in zip(boundaries, boundaries[1:]):
                chunk = rows[begin:end]
                prices = [getattr(bar, column) for bar in chunk] if column else []
                kind = spec['type']
                if kind == 'EMA': values = {'value': indicators.ema_series(prices, spec['period'])}
                elif kind == 'MACD': values = indicators.macd_series(prices, spec['fast_period'], spec['slow_period'], spec['signal_period'])
                elif kind == 'BB':
                    bands = [indicators.bb(prices, spec['period'], i, spec['stddev_multiplier']) for i in range(1, len(chunk) + 1)]
                    values = {key: [b[key] if b else None for b in bands] for key in outputs}
                elif kind in ('HIGHEST', 'LOWEST'):
                    formula = indicators.highest if kind == 'HIGHEST' else indicators.lowest
                    values = {'value': [formula(prices, spec['period'], i) for i in range(1, len(chunk) + 1)]}
                else:
                    values = {'value': [indicators.sma(prices, spec['period'], i) if kind == 'SMA'
                                        else indicators.mfi(chunk, spec['period'], i) for i in range(1, len(chunk) + 1)]}
                for key, values_for_key in values.items(): outputs[key].extend(values_for_key)
            for key, values in outputs.items(): self.values[name if key == 'value' else f'{name}.{key}'] = (source, values)

    def at(self, stamp):
        counts = {source: bisect_right(times, stamp) for source, times in self.times.items()}
        starts = {source: self.starts[source][count - 1] if count else 0 for source, count in counts.items()}
        values = {name: rows[starts[source]:counts[source]] for name, (source, rows) in self.values.items()}
        return values, {source: counts[source] - starts[source] for source in counts}, counts


class InlineExecution(ContractExecution):
    def __init__(self, cash, payload):
        self.spec = payload['strategy']
        self.current_open = self.entry_open = self.last_exit_open = None
        self.entry_details = {}
        self.day = None
        self.day_start = decimal(cash)
        self.entry_count = 0
        accounting = {key: value for key, value in payload['accounting'].items() if key != 'model'}
        super().__init__(cash, ContractAccounting(**accounting),
                         margin_buffer=self.spec['sizing']['margin_buffer'], max_contracts=self.spec['sizing']['max_contracts'])

    def before_open(self, stamp):
        strict_flat = self.spec['exit'].get('allow_overnight') is False
        if self.portfolio.position and self.current_open is not None:
            expected = self.current_open + timedelta(minutes=5)
            if expected.strftime('%H:%M') == '11:30': expected = expected.replace(hour=13, minute=0)
            if stamp != expected: raise InvalidExecution('MISSING_POSITION_EXECUTION_BAR')
        if self.day != stamp.date():
            if strict_flat and self.portfolio.position is not None: raise InvalidExecution('OVERNIGHT_POSITION_INVALID')
            self.day, self.day_start, self.entry_count = stamp.date(), self.portfolio.cash, 0
        if (self.portfolio.position and self.spec['exit'].get('flat_by')
                and stamp.strftime('%H:%M') >= self.spec['exit']['flat_by']):
            raise InvalidExecution('FLAT_DEADLINE_MISSED')
        self.current_open = stamp

    def execute(self, signal, signal_date, fill_date, raw_open):
        is_market = signal_date != (self.entry_fill.fill_date if self.entry_fill else None) or signal.reason not in ('TP1', 'TP2', 'STOP_LOSS', 'TRAILING_STOP')
        if is_market and signal.side == 'CLOSE':
            expected = signal_date.replace(hour=13, minute=0) if signal_date.strftime('%H:%M') == '11:30' else signal_date
            if fill_date != expected: raise InvalidExecution('MISSING_REQUIRED_EXIT_BAR')
        if signal.side != 'CLOSE':
            if self.spec['entry'].get('pending') and fill_date != signal_date:
                raise ValueError('PENDING_EXPIRED')
            windows = self.spec['entry'].get('signal_windows')
            if not continuous(fill_date) or (windows and fill_date.strftime('%H:%M') > windows[-1][1]):
                raise ValueError('ENTRY_OUTSIDE_SESSION_OR_CUTOFF')
            price = decimal(raw_open)
            sizing = self.spec['sizing']
            sign = 1 if signal.side == 'LONG' else -1
            stop_price = price - sign * decimal(sizing['stop_points'])
            stop_price = self.level(stop_price, sign == -1)
            costs = self.portfolio.accounting.costs(price, 1).total + self.portfolio.accounting.costs(stop_price, 1).total
            accounting = self.portfolio.accounting
            risk = decimal(sizing['stop_points']) * accounting.contract_multiplier + costs
            by_risk = int(self.portfolio.cash * decimal(sizing['risk_fraction']) // risk)
            by_margin = int(self.portfolio.cash // (price * accounting.contract_multiplier * accounting.margin_rate * self.margin_buffer))
            quantity = min(by_risk, by_margin, self.max_contracts)
            if quantity < 1: raise ValueError('INSUFFICIENT_RISK_OR_MARGIN_BUDGET')
            signal = replace(signal, quantity=quantity)
            self.bracket = None
            intrabar = self.spec['exit'].get('intrabar')
            if intrabar:
                actions = [intrabar['conditions'][key] for key in intrabar['priority']]
                stop = next(a for a in actions if a['type'] == 'protective_stop')
                targets = []
                for action in actions:
                    if action['type'] != 'target_touch': continue
                    target = evaluate_expression(self.spec['exit']['targets'][signal.side][action['level']], {'position.entry_price': price})
                    q = action['quantity']
                    if isinstance(q, dict):
                        q = 'remaining' if quantity == q['if_initial_quantity_eq'] else evaluate_expression(q['else'], {'position.initial_quantity': quantity})
                    if q != 'remaining' and (q != int(q) or q < 1): raise ValueError('INVALID_TARGET_QUANTITY')
                    targets.append((sign * (target - price), None if q == 'remaining' else int(q)))
                    if q == 'remaining': break
                self.bracket = Bracket(decimal(stop['distance_points']), tuple(targets),
                                       decimal(stop['trailing']['distance_points']) if stop.get('trailing') else None)
        fill, trade = super().execute(signal, signal_date, fill_date, raw_open)
        if signal.side != 'CLOSE':
            self.entry_count += 1
            self.entry_open = self.current_open
            self.entry_details = dict(signal.details)
        elif self.portfolio.position is None:
            self.last_exit_open = self.current_open
            self.entry_details = {}
        return fill, trade


class InlineNormalizedExecution(NormalizedExecution):
    """Run BUY/SELL payloads with the existing normalized ledger."""
    def __init__(self, cash, payload):
        self.spec = payload['strategy']
        self.current_open = self.entry_open = self.last_exit_open = None
        self.day = None
        self.day_start = decimal(cash)
        self.entry_count = 0
        self.entry_details = {}
        sizing = self.spec['sizing']

        def size(context):
            risk = context.fill_price * decimal(sizing['stop_loss_fraction'])
            by_risk = int(context.cash * decimal(sizing['risk_fraction']) // risk)
            by_cash = int(context.cash // (context.fill_price * (1 + context.fee_rate)))
            return min(by_risk, by_cash)

        super().__init__(cash, decimal(payload['accounting']['fee_rate']),
                         decimal(payload['execution']['slippage_rate']), size)

    def before_open(self, stamp):
        if self.day != stamp.date():
            self.day, self.day_start, self.entry_count = stamp.date(), self.portfolio.cash, 0
        self.current_open = stamp

    def execute(self, signal, signal_date, fill_date, raw_open):
        fill, trade = super().execute(signal, signal_date, fill_date, raw_open)
        if signal.side == 'BUY':
            self.entry_count += 1
            self.entry_open = self.current_open
            self.entry_details = dict(signal.details)
        else:
            self.last_exit_open = self.current_open
            self.entry_details = {}
        return fill, trade


def run_inline_strategy(data, payload):
    check_runtime(payload)
    spec = payload['strategy']
    series = IndicatorData(data, payload)
    executor = (InlineExecution(payload['initial_cash'], payload)
                if payload['accounting']['model'] == 'contract'
                else InlineNormalizedExecution(payload['initial_cash'], payload))
    evaluations = []
    gap_times = {source: [datetime.fromisoformat(s) + timedelta(minutes=5) for s in stamps]
                 for source, stamps in data.metadata['data_gaps'].items()}
    required_sources = {i['source'].split('.')[0] for i in spec.get('indicators', {}).values()}
    warmup_sources = required_sources.copy()
    def collect(value):
        if isinstance(value, dict):
            if value.get('ref', '').startswith(('trade_data.', 'market_data.')): required_sources.add(value['ref'].split('.')[0])
            for child in value.values(): collect(child)
        elif isinstance(value, list):
            for child in value: collect(child)
    collect(spec['entry'])

    def evaluate(context):
        bar = context.bars[-1]
        stamp = bar.closed_at
        values, counts, totals = series.at(stamp)
        values.update(dict.fromkeys(STATE_REFS))
        snapshot = context.portfolio.mark(bar.close)
        position = context.portfolio.position
        held = sum(b.trading_date >= executor.entry_open for b in context.bars) if position else 0
        values.update({'clock.local_time': stamp.strftime('%H:%M'), 'account.equity': snapshot.equity,
                       'account.required_margin': getattr(snapshot, 'required_margin', Decimal(0)), 'day.start_equity': executor.day_start,
                       'day.net_pnl': snapshot.equity - executor.day_start, 'day.entry_fill_count': executor.entry_count,
                       'position.entry_price': position.entry_price if position else None,
                       'position.initial_quantity': getattr(position, 'initial_quantity', position.quantity) if position else None,
                       'position.held_bars': held})
        values.update({f'position.entry_{name}': value for name, value in executor.entry_details.items()})
        status, reason, signal = 'EVALUABLE', 'NO_SIGNAL', None
        if position and spec['exit'].get('bar_close'):
            group = spec['exit']['bar_close']
            for name in group['priority']:
                try: matched = evaluate_expression(group['conditions'][name], values, group['conditions'])
                except MissingValue: continue
                if matched:
                    signal, reason = executor.close_signal(name), name
                    break
        if not position:
            windows = spec['entry'].get('signal_windows')
            if bar.trading_date.date() < data.start_date: reason = 'HISTORY_ONLY'
            elif windows and (not continuous(bar.trading_date) or not any(a <= stamp.strftime('%H:%M') <= b for a, b in windows)):
                reason = 'OUTSIDE_ENTRY_WINDOW'
            elif spec['entry'].get('reentry') and executor.last_exit_open is not None and bar.trading_date <= executor.last_exit_open:
                reason = 'REENTRY_WAIT'
            else:
                try:
                    for source in required_sources:
                        n = totals[source]
                        gaps = gap_times.get(source, [])
                        gap_index = bisect_right(gaps, stamp)
                        if gap_index and (not n or gaps[gap_index - 1] > series.times[source][n - 1]):
                            raise MissingValue('DATA_GAP:' + source)
                        if source in (warmup_sources or required_sources) and counts[source] < spec.get('warmup_bars', 0):
                            raise MissingValue('WARMUP:' + source)
                    limits = spec.get('daily_limits')
                    if limits and evaluate_expression(limits['stop_new_entry'], values): reason = 'DAILY_ENTRY_LIMIT'
                    else:
                        matched = [side for side in spec['entry']['any'] if evaluate_expression(spec['entry']['conditions'][side], values, spec['entry']['conditions'])]
                        if len(matched) > 1: reason = 'SIGNAL_CONFLICT'
                        elif matched:
                            details = tuple((name, evaluate_expression(node, values))
                                            for name, node in spec['entry'].get('details', {}).items())
                            reason, signal = 'ENTRY', FixedSignal(matched[0], reason='ENTRY', details=details)
                except MissingValue as error:
                    status, reason = 'UNEVALUABLE', str(error)
        if bar.trading_date.date() >= data.start_date:
            evaluations.append({'time': stamp, 'status': status, 'reason': reason,
                                'market_sample_count': counts['market_data'],
                                'market_available_at': series.times['market_data'][totals['market_data'] - 1] if totals['market_data'] else None,
                                'indicator_times': {name: series.rows[source][totals[source] - 1].trading_date
                                                    for name, (source, _) in series.values.items()
                                                    if totals[source] and not name.startswith(('trade_data.', 'market_data.'))},
                                'indicators': {name: rows[-1] if rows else None for name, rows in values.items()
                                               if name in series.values and not name.startswith(('trade_data.', 'market_data.'))}})
        return signal

    result = run_engine(data.bars, evaluate, initial_cash=payload['initial_cash'], fee_rate=0, slippage_rate=0,
                        support_bars=data.market_bars, record_start=data.start_date, trade_start=data.start_date,
                        execution=lambda cash: executor, on_open=executor.before_open)
    if spec['exit'].get('allow_overnight') is False and result.portfolio.position is not None:
        raise InvalidExecution('END_OF_REPORT_POSITION_REQUIRES_EXIT')
    entry_sides = set(spec['entry']['conditions'])
    orders = tuple(OrderResult(o.signal_date, o.side, 'REJECTED', 'END_OF_REPORT')
                   if o.status == 'PENDING' and o.side in entry_sides else o for o in result.orders)
    if result.portfolio.position and payload['accounting']['model'] == 'contract':
        details = tuple((key, value) for key, value in (('active_stop', executor.active_stop), ('trailing_extreme', executor.extreme))
                        if value is not None)
    else:
        details = tuple(executor.entry_details.items()) if result.portfolio.position else ()
    return replace(result, orders=orders, evaluations=tuple(evaluations), position_details=details)
