"""Run the price-only contract using available source samples and explicit fills."""
from bisect import bisect_left, bisect_right
from dataclasses import asdict, replace
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo
from .inline_data import InlineData, _bars, _session_gaps
from .inline_strategy import IndicatorData, continuous
from ..domain.expressions import MissingValue, evaluate_expression
from ..domain.price_portfolio import PriceBook
from ..domain.portfolio import decimal


def resolve_price_data(sources, payload, policy, fetch_metadata):
    """Keep normalized source facts, pin calendar coverage and annotate known gaps."""
    if (policy.get('schema_version') != 1 or policy.get('timezone') != 'Asia/Ho_Chi_Minh'
            or not policy.get('sessions', {}).get('trade_data', {}).get('required_times')):
        raise ValueError('CALENDAR_REQUIRED')
    trade = _bars(sources['trade_data'])
    market = _bars(sources['market_data']) if sources.get('market_data') else ()
    if not trade:
        raise ValueError('REPORT_DATA_MISSING')
    zone = ZoneInfo(policy['timezone'])
    start = date.fromisoformat(payload['from']) if payload.get('from') else datetime.fromtimestamp(fetch_metadata['from'], zone).date()
    end = date.fromisoformat(payload['to']) if payload.get('to') else datetime.fromtimestamp(fetch_metadata['to'], zone).date()
    if start < date.fromisoformat(policy['calendar_range']['start']) or end > date.fromisoformat(policy['calendar_range']['end']):
        raise ValueError('CALENDAR_REQUIRED')
    cutoff = min(datetime.combine(end + timedelta(days=1), time.min, zone) - timedelta(microseconds=1),
                 datetime.fromtimestamp(fetch_metadata['to'], zone))
    trade = tuple(bar for bar in trade if bar.available_at <= cutoff)
    market = tuple(bar for bar in market if bar.available_at <= cutoff)
    if any(bar.available_at != bar.closed_at for bar in trade):
        raise ValueError('PRIMARY_AVAILABILITY_DELAY_UNSUPPORTED')
    mapping = sources['trade_data'].get('contract_map', [])
    expiries = [date.fromisoformat(row['expiry_date']) for row in mapping]
    warnings = []
    if (expiries and trade and trade[0].trading_date.date() >= expiries[0].replace(day=1)
            and end <= expiries[-1]):
        trade = tuple(replace(bar, contract_code=mapping[bisect_left(expiries, bar.trading_date.date())]['contract_code']) for bar in trade)
    else:
        warnings.append('CONTRACT_IDENTITY_UNCONFIRMED')
    gaps = {}
    for name, rows in (('trade_data', trade), ('market_data', market)):
        if not rows:
            gaps[name] = []
            continue
        rows, gaps[name] = _session_gaps(rows, sources[name], name, policy,
                                       min(start, rows[0].trading_date.date()), end, start)
        coverage_begin = datetime.fromtimestamp(fetch_metadata['from'], zone)
        gaps[name] = [stamp for stamp in gaps[name]
                      if coverage_begin <= datetime.fromisoformat(stamp)
                      and datetime.fromisoformat(stamp) + timedelta(minutes=5) <= cutoff]
        if name == 'trade_data':
            trade = rows
        else:
            market = rows
    report_rows = [bar for bar in trade if start <= bar.trading_date.date() <= end and continuous(bar.trading_date)]
    dates = [bar.trading_date.date() for bar in report_rows]
    if not dates:
        raise ValueError('REPORT_DATA_MISSING')
    if dates[0] > start or dates[-1] < end:
        warnings.append('PARTIAL_REPORT_COVERAGE')
    metadata = {'symbol': payload['symbol'], 'timezone': policy['timezone'], 'resolution': '5',
                'report_range': {'start': start.isoformat(), 'end': end.isoformat()},
                'available_range': {'start': dates[0].isoformat(), 'end': dates[-1].isoformat(),
                                    'first_open': report_rows[0].trading_date.isoformat(),
                                    'last_close': report_rows[-1].closed_at.isoformat()},
                'input_origin': 'auto_fetch', 'auto_fetch': fetch_metadata, 'data_gaps': gaps,
                'warnings': warnings, 'contract_mapping_assumption': 'expiry_inclusive' if not warnings or warnings == ['PARTIAL_REPORT_COVERAGE'] else None}
    return InlineData(trade, market, start, end, metadata)


class PriceProtection:
    """Keep fixed entry levels and a trailing threshold effective before the next Close."""
    def __init__(self, price, direction, risk):
        """Validate all initial levels against the actual fill before opening the book."""
        self.sign = 1 if direction == 'LONG' else -1
        self.stop = (price * (1 - self.sign * decimal(risk['sl']) / 100) if 'sl' in risk
                     else risk.get('stop_price'))
        self.targets = []
        self.trailing_pct = decimal(risk.get('trailing', risk.get('trailing_after_tp1', 0)))
        self.after_tp1 = 'trailing_after_tp1' in risk
        self.extreme = self.trailing_price = None
        if self.stop is not None:
            self.check_level(self.stop, price, favorable=False)
        targets = risk.get('targets', [])
        if 'tp' in risk:
            targets = [{'pct': risk['tp'], 'quantity': 'remaining'}]
        previous = Decimal(0)
        for index, target in enumerate(targets):
            level = (price * (1 + self.sign * decimal(target['pct']) / 100)
                     if 'pct' in target else target['price'])
            self.check_level(level, price, favorable=True)
            distance = self.sign * (level - price)
            if distance < previous:
                raise ValueError('TARGETS_OUT_OF_ORDER')
            previous = distance
            self.targets.append({'price': level, 'quantity': target['quantity'], 'done': False,
                                 'reason': 'TAKE_PROFIT' if 'tp' in risk else f'TP{index + 1}'})
        if self.trailing_pct:
            # Even deferred trailing must be capable of producing a positive level.
            self.check_level(self.trail_level(price), price, favorable=False)
            if not self.after_tp1:
                self.activate(price)

    def check_level(self, level, origin, *, favorable):
        """Reject nonpositive, nonfinite or wrong-side absolute and percentage levels."""
        level = decimal(level)
        distance = self.sign * (level - origin)
        if level <= 0 or (distance <= 0 if favorable else distance >= 0):
            raise ValueError('INVALID_PROTECTION_LEVEL')

    def trail_level(self, price):
        """Convert the configured percentage from an actual favorable Close or fill seed."""
        return price * (1 - self.sign * self.trailing_pct / 100)

    def activate(self, price):
        """Start deferred trailing only from its actual activation fill."""
        self.extreme = price
        self.trailing_price = self.trail_level(price)

    def advance(self, close):
        """Tighten after evaluating the old level, never widen the active threshold."""
        if self.extreme is None:
            return
        self.extreme = max(self.extreme, close) if self.sign == 1 else min(self.extreme, close)
        level = self.trail_level(self.extreme)
        self.trailing_price = max(self.trailing_price, level) if self.sign == 1 else min(self.trailing_price, level)

    def touched(self, close, level, *, favorable=False):
        """Test only the current Close against a previously effective threshold."""
        return level is not None and (self.sign * (close - level) >= 0 if favorable
                                      else self.sign * (close - level) <= 0)


def run_price_strategy(data, spec, sources, policy):
    """Match one active order, then evaluate Close decisions without future samples."""
    series = IndicatorData(data, {**sources, 'strategy': spec}, price_only=True)
    book = PriceBook()
    signals, orders, fills, trades, evaluations, history = [], [], [], [], [], []
    pending = None
    position_sequence = entry_index = day_count = 0
    day = None
    day_realized = Decimal(0)
    closed_pnl = []
    position_realized = Decimal(0)
    peak = drawdown = Decimal(0)
    entry_fill_id = None
    previous = None
    protection = None
    rows = series.rows['trade_data']
    required_sources = {indicator['source'].split('.')[0] for indicator in spec['indicators'].values()}
    gap_times = {source: [datetime.fromisoformat(stamp) + timedelta(minutes=5) for stamp in stamps]
                 for source, stamps in data.metadata.get('data_gaps', {}).items()}

    def collect_sources(value):
        """Include direct entry references without requiring unused market columns."""
        if isinstance(value, dict):
            name = value.get('ref', '').split('.')[0]
            if name in ('trade_data', 'market_data'):
                required_sources.add(name)
            for child in value.values():
                collect_sources(child)
        elif isinstance(value, list):
            for child in value:
                collect_sources(child)

    collect_sources(spec['entry'])
    collect_sources(spec['daily_limits'])
    end_label = max(label for label in policy['sessions']['trade_data']['required_times']
                    if continuous(datetime.combine(data.start_date, time.fromisoformat(label))))
    final_close = (datetime.combine(data.start_date, time.fromisoformat(end_label)) + timedelta(minutes=5)).time()
    close_at_day_end = spec.get('session_end_action') == 'close_at_close'

    def finish(order, status, reason, stamp):
        """End an order once and keep the reason and terminal event time."""
        order.update(status=status, reason=reason, end_time=stamp)

    def fill(order, price, stamp, bar, phase, index):
        """Apply a matched fill before publishing links and portfolio effects."""
        nonlocal position_sequence, entry_index, day_count, position_realized, entry_fill_id, protection
        fill_id = f'f{len(fills) + 1}'
        if order['action'] == 'OPEN':
            position_sequence += 1
            position_id = f'p{position_sequence}'
            next_protection = PriceProtection(price, order['direction'], order['protection'])
            book.open(position_id, order['direction'], price, order['quantity'])
            protection = next_protection
            entry_index, entry_fill_id, position_realized = index, fill_id, Decimal(0)
            day_count += 1
        else:
            position = book.position
            position_id = position.position_id
            pnl = book.close(price, order['quantity'])
            position_realized += pnl
            trades.append({'position_id': position_id, 'entry_fill_id': entry_fill_id, 'exit_fill_id': fill_id,
                           'entry_price': position.entry_price, 'exit_price': price, 'quantity': order['quantity'],
                           'realized_pnl': pnl, 'reason': order['reason']})
            if book.position is None:
                closed_pnl.append(position_realized)
        order['position_id'] = position_id
        finish(order, 'FILLED', order['reason'], stamp)
        fills.append({'fill_id': fill_id, 'order_id': order['order_id'], 'position_id': position_id,
                      'side': order['side'], 'direction': order['direction'], 'quantity': order['quantity'],
                      'price': price, 'fill_time': stamp, 'fill_phase': phase, 'bar_time': bar.trading_date})

    def submit(action, direction, reason, values, bar, index, *, protective=False):
        """Pin limit and quantity at the signal, then fill immediately or queue LO."""
        nonlocal pending
        opening = reason == 'ENTRY'
        quantity = spec['quantity'] if opening else action.get('quantity', 'remaining')
        if quantity == 'remaining':
            quantity = book.position.remaining_quantity
        if not opening and quantity > book.position.remaining_quantity:
            raise ValueError('INVALID_CLOSE_QUANTITY_OR_PRICE')
        config = {'type': 'IMMEDIATE'} if protective else action['order']
        limit = evaluate_expression(config['limit_price'], values) if config['type'] == 'LO' else None
        if limit is not None and limit <= 0:
            raise ValueError('INVALID_LIMIT_PRICE')
        signal_id, order_id = f's{len(signals) + 1}', f'o{len(orders) + 1}'
        order = {'order_id': order_id, 'signal_id': signal_id, 'position_id': book.position.position_id if book.position else None,
                 'action': 'OPEN' if opening else 'CLOSE', 'direction': direction,
                 'side': 'BUY' if (direction == 'LONG') == opening else 'SELL', 'quantity': quantity,
                 'type': config['type'], 'created_at': bar.closed_at, 'status': 'PENDING', 'reason': reason}
        if limit is not None:
            order.update(limit_price=limit, max_execution_bars=3, time_in_force='DAY', execution_bars=0)
        if opening:
            risk = {**spec['risk']}
            if 'stop_price' in risk:
                risk['stop_price'] = evaluate_expression(risk['stop_price'], values)
            risk['targets'] = []
            for target in spec['risk'].get('targets', []):
                pinned = {**target}
                if 'price' in target:
                    pinned['price'] = evaluate_expression(target['price'], values)
                if isinstance(target['quantity'], dict):
                    quantity_value = evaluate_expression(target['quantity'], {'position.initial_quantity': spec['quantity']})
                    if quantity_value != int(quantity_value) or quantity_value < 1:
                        raise ValueError('INVALID_TARGET_QUANTITY')
                    pinned['quantity'] = int(quantity_value)
                risk['targets'].append(pinned)
            order['protection'] = risk
        signals.append({'signal_id': signal_id, 'decision_time': bar.closed_at, 'direction': direction,
                        'action': 'OPEN' if opening else 'CLOSE', 'reason': reason})
        orders.append(order)
        if config['type'] == 'IMMEDIATE':
            fill(order, bar.close, bar.closed_at, bar, 'decision_close', index)
        else:
            pending = order

    for index, bar in enumerate(rows):
        stamp = bar.closed_at
        if bar.trading_date.date() < data.start_date or bar.trading_date.date() > data.end_date:
            continue
        if not history:
            history.append({'time': bar.trading_date, **book.mark(bar.open)})
        if day != bar.trading_date.date():
            if book.position is not None:
                raise ValueError('MISSING_POSITION_EXECUTION_BAR' if close_at_day_end else 'REQUIRED_EXIT_NOT_FILLED')
            if pending:
                finish(pending, 'EXPIRED', 'END_OF_DAY', datetime.combine(day, final_close, stamp.tzinfo))
                pending = None
            day, day_count, day_realized = bar.trading_date.date(), 0, book.realized_pnl
        changed = previous is not None and previous.contract_code != bar.contract_code
        if changed and book.position is not None:
            raise ValueError('OPEN_POSITION_AT_CONTRACT_CHANGE')
        if bar.data_gap_before and book.position is not None:
            raise ValueError('MISSING_POSITION_EXECUTION_BAR')
        if pending and (changed or bar.data_gap_before):
            finish(pending, 'CANCELED', 'CONTRACT_CHANGED' if changed else 'EXECUTION_DATA_GAP', bar.trading_date)
            pending = None
        closed_here = False
        if pending:
            windows = spec['signal_windows']
            if pending['action'] == 'OPEN' and windows and not any(a <= bar.trading_date.strftime('%H:%M') <= b for a, b in windows):
                finish(pending, 'CANCELED', 'ENTRY_OUTSIDE_WINDOW', bar.trading_date)
                pending = None
            else:
                pending['execution_bars'] += 1
                buy, limit = pending['side'] == 'BUY', pending['limit_price']
                price = bar.open if (bar.open <= limit if buy else bar.open >= limit) else (
                    limit if (bar.low <= limit if buy else bar.high >= limit) else None)
                if price is not None:
                    is_open = price == bar.open
                    closed_here = pending['action'] == 'CLOSE'
                    fill(pending, price, bar.trading_date if is_open else stamp, bar,
                         'open' if is_open else 'intrabar_assumed', index)
                    pending = None
                elif pending['execution_bars'] == 3:
                    finish(pending, 'EXPIRED', 'MAX_EXECUTION_BARS', stamp)
                    pending = None
        values, counts, totals = series.at(stamp)
        for source, gaps in gap_times.items():
            gap_index = bisect_right(gaps, stamp)
            count = totals.get(source, 0)
            if gap_index and (not count or gaps[gap_index - 1] > series.times[source][count - 1]):
                # A known missing slot invalidates stale values until that source resumes.
                for name, (owner, _) in series.values.items():
                    if owner == source:
                        values[name] = []
        values.update({'clock.local_time': stamp.strftime('%H:%M'), 'day.net_pnl': book.realized_pnl - day_realized,
                       'day.entry_fill_count': day_count, 'position.entry_price': book.position.entry_price if book.position else None,
                       'position.initial_quantity': book.position.initial_quantity if book.position else None,
                       'position.held_bars': index - entry_index + 1 if book.position else None})
        reason, status = 'NO_SIGNAL', 'EVALUABLE'
        try:
            position = book.position
            if close_at_day_end and stamp.time() == final_close:
                # The scheduled boundary is known before this candle; never infer it from future rows.
                if pending:
                    finish(pending, 'EXPIRED', 'END_OF_DAY', stamp)
                    pending = None
                if position is not None:
                    submit({}, position.direction, 'END_OF_DAY', values, bar, index, protective=True)
                reason = 'END_OF_DAY'
            elif position is not None:
                direction = position.direction
                activated_trailing = False
                if protection.touched(bar.close, protection.stop):
                    if pending:
                        finish(pending, 'CANCELED', 'POSITION_CHANGED', stamp)
                        pending = None
                    submit({}, direction, 'STOP_LOSS', values, bar, index, protective=True)
                    closed_here = True
                    reason = 'STOP_LOSS'
                else:
                    for target in protection.targets:
                        if book.position is None or target['done'] or not protection.touched(bar.close, target['price'], favorable=True):
                            continue
                        if pending:
                            finish(pending, 'CANCELED', 'POSITION_CHANGED', stamp)
                            pending = None
                        submit({'quantity': target['quantity']}, direction, target['reason'], values, bar, index, protective=True)
                        target['done'] = True
                        closed_here, reason = True, target['reason']
                        if target['reason'] == 'TP1' and protection.after_tp1 and book.position is not None:
                            protection.activate(bar.close)
                            activated_trailing = True
                    if book.position is not None:
                        triggered = not activated_trailing and protection.touched(bar.close, protection.trailing_price)
                        if triggered:
                            reason = 'TRAILING_STOP'
                            if pending is None:
                                action = spec['exit'].get(direction, {'order': spec['order']})
                                submit({'order': action['order']}, direction, reason, values, bar, index)
                                closed_here = True
                        else:
                            protection.advance(bar.close)
                if book.position is not None and pending is None and reason != 'TRAILING_STOP':
                    values['day.net_pnl'] = book.realized_pnl - day_realized
                    action = spec['exit'].get(direction)
                    if action and evaluate_expression(action['condition'], values):
                        submit(action, direction, 'EXIT', values, bar, index)
                        closed_here = True
                        reason = 'EXIT'
            elif not closed_here and pending is None:
                windows = spec['signal_windows']
                if windows and not any(a <= stamp.strftime('%H:%M') <= b for a, b in windows):
                    reason = 'OUTSIDE_ENTRY_WINDOW'
                elif spec['daily_limits'] and evaluate_expression(spec['daily_limits']['stop_new_entry'], values):
                    reason = 'DAILY_ENTRY_LIMIT'
                else:
                    for source in required_sources:
                        gaps = gap_times.get(source, [])
                        gap_index = bisect_right(gaps, stamp)
                        count = totals[source]
                        if gap_index and (not count or gaps[gap_index - 1] > series.times[source][count - 1]):
                            raise MissingValue('DATA_GAP:' + source)
                        if counts[source] < spec['warmup_bars']:
                            raise MissingValue('WARMUP:' + source)
                    matched = [direction for direction, action in spec['entry'].items()
                               if evaluate_expression(action['condition'], values)]
                    if len(matched) > 1:
                        reason = 'SIGNAL_CONFLICT'
                    elif matched:
                        reason = 'ENTRY'
                        submit(spec['entry'][matched[0]], matched[0], reason, values, bar, index)
        except MissingValue as error:
            if book.position is not None:
                raise ValueError('MISSING_POSITION_MANAGEMENT_DATA: ' + error.name) from error
            status, reason = 'UNEVALUABLE', str(error)
        evaluations.append({'decision_time': stamp, 'status': status, 'reason': reason})
        if book.position and ((spec['flat_by'] and stamp.strftime('%H:%M') >= spec['flat_by']) or stamp.time() >= final_close):
            raise ValueError('REQUIRED_EXIT_NOT_FILLED')
        if pending and stamp.time() >= final_close:
            finish(pending, 'EXPIRED', 'END_OF_DAY', stamp)
            pending = None
        point = book.mark(bar.close)
        peak = max(peak, point['total_pnl'])
        drawdown = max(drawdown, peak - point['total_pnl'])
        history.append({'time': stamp, **point})
        previous = bar
    if pending:
        finish(pending, 'EXPIRED', 'END_OF_REPORT', history[-1]['time'])
    observation = data.metadata.get('auto_fetch', {}).get('to')
    if observation is not None and book.position is not None:
        available_end = datetime.fromtimestamp(observation, rows[-1].trading_date.tzinfo)
        if any(rows[-1].closed_at < gap <= available_end for gap in gap_times.get('trade_data', [])):
            raise ValueError('MISSING_POSITION_EXECUTION_BAR')
    summary = {**book.mark(rows[-1].close), 'pnl_unit': 'point_quantity', 'max_drawdown': drawdown,
               'closed_positions': len(closed_pnl), 'open_positions': int(book.position is not None),
               'winning_positions': sum(p > 0 for p in closed_pnl), 'losing_positions': sum(p < 0 for p in closed_pnl),
               'breakeven_positions': sum(p == 0 for p in closed_pnl),
               'win_rate': Decimal(sum(p > 0 for p in closed_pnl)) / len(closed_pnl) if closed_pnl else None}
    position = {**asdict(book.position), 'stop_price': protection.stop,
                'target_price': protection.targets[0]['price'] if len(protection.targets) == 1 else None,
                'targets': protection.targets, 'trailing_price': protection.trailing_price,
                'trailing_extreme': protection.extreme} if book.position else None
    return {'summary': summary, 'open_position': position,
            'pnl_history': history, 'signals': signals, 'orders': orders, 'fills': fills,
            'trades': trades, 'evaluations': evaluations}
