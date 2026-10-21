"""HNX session simulation on OHLC; auction prices are caller-provided facts."""
from dataclasses import dataclass, replace
from datetime import datetime, time, timedelta
from decimal import Decimal
from itertools import groupby
from .engine import DecisionContext
from .execution import InvalidExecution
from .results import BacktestResult, EquityPoint, Summary
from .trading import SignalRecord
from .orders import MARKET_TYPES, OrderRequest, OrderResult
from .multi_execution import MultiContractExecution
from .matching import MatchBudget, check_market_price, mtl_limit_price, match_continuous, match_auction as auction_match


# Classify a timestamp using the project's configured HNX session windows.
def phase_at(stamp):
    local = stamp.time()
    if time(8, 45) <= local < time(9): return 'ATO'
    if time(9) <= local < time(11, 30): return 'CONTINUOUS_AM'
    if time(11, 30) <= local < time(13): return 'LUNCH'
    if time(13) <= local < time(14, 30): return 'CONTINUOUS_PM'
    if time(14, 30) <= local < time(14, 45): return 'ATC'
    return 'CLOSED'


# Carry a sourced auction observation and its availability timestamp.
@dataclass(frozen=True)
class AuctionEvent:
    contract_code: str
    match_time: datetime
    available_at: datetime
    status: str
    price: Decimal | None
    source: str


def run_session_engine(bars, signal_provider, executor, *, support_bars=(), record_start=None,
                       trade_start=None, auction_events=(), on_execution=None,
                       max_execution_bars=1, entry_cutoff=None, on_open=None,
                       auction_entry=False, auction_match_quantity=None, require_end_flat=False,
                       continuous_match_quantity=None, price_limits=None):
    """Match pending intents in submission order; preserve per-position links."""
    multi = isinstance(executor, MultiContractExecution)
    finite = continuous_match_quantity is not None
    if finite: MatchBudget(continuous_match_quantity)
    price_limits = price_limits or {}
    all_bars = tuple(bars)
    auction_bars = {(bar.trading_date.date(), bar.trading_date.time()): bar for bar in all_bars
                    if bar.trading_date.time() in (time(9), time(14, 45))}
    bars = tuple(b for b in bars if phase_at(b.trading_date).startswith('CONTINUOUS'))
    if not bars: raise ValueError('NO_CONTINUOUS_BARS')
    if any(b.closed_at - b.trading_date != timedelta(minutes=5) for b in bars):
        raise ValueError('SESSION_MATCHING_REQUIRES_FIVE_MINUTE_BARS')
    if auction_match_quantity is not None and (type(auction_match_quantity) is not int or auction_match_quantity < 0):
        raise ValueError('INVALID_AUCTION_MATCH_QUANTITY')
    auctions = {a.match_time.date(): a for a in auction_events}
    initial_cash = executor.portfolio.cash
    signals, orders, fills, trades, equity, completed, support = [], [], [], [], [], [], []
    pending = {}
    support_index = 0

    # Update order status, fill links, remaining quantity, and lifecycle events.
    def finish(index, signal, status, stamp, reason=None, fill=None, trade=None):
        old = orders[index]
        if finite and fill is not None and old.quantity is None:
            old = replace(old, quantity=fill.quantity, requested_quantity=fill.quantity)
        phase = (old.order_type if old.order_type in ('ATO', 'ATC') else
                 'CONTINUOUS_PM' if stamp.time() == time(14, 30) and status != 'REJECTED' else
                 'CONTINUOUS_AM' if stamp.time() == time(11, 30) and status != 'REJECTED' else phase_at(stamp))
        remaining = old.remaining_quantity if old.remaining_quantity is not None else old.quantity
        filled_quantity, fill_indices = old.filled_quantity, old.fill_indices
        events = old.events
        if fill is not None:
            if remaining is not None and fill.quantity > remaining: raise InvalidExecution('ORDER_FILL_QUANTITY_EXCEEDED')
            fill_indices += (len(fills),)
            filled_quantity += fill.quantity
            remaining = remaining - fill.quantity if remaining is not None else None
            fills.append(fill)
            if status != 'FILLED':
                events += ({'time': stamp, 'status': 'partially_filled', 'reason': None, 'phase': phase,
                            'filled_quantity': filled_quantity, 'expired_quantity': old.expired_quantity,
                            'remaining_quantity': remaining},)
        expired_quantity = old.expired_quantity
        canceled_quantity, rejected_quantity = old.canceled_quantity, old.rejected_quantity
        if status in ('REJECTED', 'CANCELED', 'EXPIRED') and remaining is not None:
            if finite and old.order_type not in ('ATO', 'ATC', 'NEXT_OPEN', 'PROTECTIVE'):
                if status == 'CANCELED': canceled_quantity += remaining
                elif status == 'REJECTED': rejected_quantity += remaining
                else: expired_quantity += remaining
            else:
                expired_quantity += remaining
            remaining = 0
        if status != 'PENDING' or fill is None:
            event = {'time': stamp, 'status': status.lower(), 'reason': reason, 'phase': phase,
                    'filled_quantity': filled_quantity, 'expired_quantity': expired_quantity,
                    'remaining_quantity': remaining}
            if finite:
                event.update(canceled_quantity=canceled_quantity, rejected_quantity=rejected_quantity)
            events += (event,)
        orders[index] = replace(old, status=status, reason=reason, events=events,
                                fill_index=fill_indices[0] if fill_indices else old.fill_index,
                                fill_indices=fill_indices, filled_quantity=filled_quantity,
                                expired_quantity=expired_quantity, canceled_quantity=canceled_quantity,
                                rejected_quantity=rejected_quantity, remaining_quantity=remaining)
        if trade is not None: trades.append(trade)
        if on_execution: on_execution(signal, orders[index], fill)

    # Record and validate order intent before adding it to the pending queue.
    def submit(signal, stamp):
        index = len(orders)
        signals.append(SignalRecord(stamp, signal.side, signal.reason, signal.details, signal.position_id))
        orders.append(OrderResult(stamp, signal.side, 'PENDING', order_type=signal.order.result_type,
                                  quantity=signal.quantity, limit_price=signal.order.limit_price, position_id=signal.position_id,
                                  events=({'time': stamp, 'status': 'submitted', 'reason': None,
                                           'phase': phase_at(stamp)},)))
        try:
            signal.order.validate()
            if signal.order.type in MARKET_TYPES and not finite:
                raise ValueError('MARKET_ORDER_REQUIRES_MATCH_QUANTITY')
            executor.validate(signal)
            if signal.order.result_type == 'ATO' and (signal.side not in ('LONG', 'SHORT') or phase_at(stamp) != 'ATO'):
                raise ValueError('ATO_ENTRY_REQUIRES_PREOPEN_SUBMISSION')
            if signal.order.result_type == 'ATC' and (signal.side != 'CLOSE' or phase_at(stamp) != 'ATC'):
                raise ValueError('ATC_CLOSE_REQUIRES_1430_SUBMISSION')
            lunch_exit = signal.order.result_type == 'NEXT_OPEN' and signal.side == 'CLOSE' and stamp.time() == time(11, 30)
            if signal.order.result_type not in ('ATO', 'ATC') and not phase_at(stamp).startswith('CONTINUOUS') and not lunch_exit:
                raise ValueError('ORDER_OUTSIDE_CONTINUOUS_SESSION')
            reference_price = completed[-1].close if signal.order.type in (*MARKET_TYPES, 'ATO') and completed else None
            signal = (executor.prepare_order(signal, reference_price, pending=tuple(p[1] for p in pending.values()))
                      if multi else executor.prepare_order(signal, reference_price))
        except ValueError as error:
            finish(index, signal, 'REJECTED', stamp, str(error))
            return None
        submitted = {**orders[index].events[0], 'filled_quantity': 0,
                     'expired_quantity': 0, 'remaining_quantity': signal.quantity}
        orders[index] = replace(orders[index], quantity=signal.quantity, remaining_quantity=signal.quantity,
                                requested_quantity=signal.requested_quantity or signal.quantity,
                                reference_price=signal.reference_price, effective_order_type=signal.order.result_type,
                                events=(submitted,))
        return (index, signal, stamp, 0)

    # Apply a simulated auction match and update its order and portfolio records.
    def match_auction(index, signal, stamp, match_time, price, bar_time):
        # Match an auction order.
        match = auction_match(signal.order, price=price, time=match_time, bar_time=bar_time,
                              quantity=signal.quantity, quantity_limit=auction_match_quantity)
        if match is None:
            finish(index, signal, 'EXPIRED', match_time, 'AUCTION_NO_MATCH')
            return False
        try:
            fill, trade = executor.execute(replace(signal, quantity=match.quantity), stamp, match.time, match.price)
        except InvalidExecution:
            raise
        except ValueError as error:
            finish(index, signal, 'REJECTED', match_time, str(error))
            return False
        fill = replace(fill, bar_time=match.bar_time)
        partial = match.quantity < signal.quantity
        finish(index, signal, 'EXPIRED' if partial else 'FILLED', match_time,
               'AUCTION_REMAINDER_EXPIRED' if partial else None, fill, trade)
        return True

    # Report whether the executor holds any open position.
    def has_position():
        return bool(executor.portfolio.quantity if multi else executor.portfolio.position)

    # Schedule pending orders for the current candle and position state.
    def pending_at_bar(bar):
        waiting = tuple(pending.values())
        if not multi:
            return [(bar.trading_date, item) for item in waiting]
        timed = []
        for item in waiting:
            signal = item[1]
            matched_at = bar.trading_date if signal.order.type in (*MARKET_TYPES, 'ATO') else bar.closed_at
            if signal.order.type not in (*MARKET_TYPES, 'ATO', 'ATC'):
                position = executor.portfolio.lot(signal.position_id)
                buy = signal.side == 'LONG' or (signal.side == 'CLOSE' and position.sign == -1)
                match = match_continuous(signal.order, bar, buy=buy, quantity=signal.quantity)
                if match is not None:
                    matched_at = match.time
            timed.append((matched_at, item))
        # Process candidate matches in chronological order.
        return sorted(timed, key=lambda row: row[0])

    # Apply intrabar protection and reconcile affected pending orders.
    def protect(bar, intrabar_entries, phase=None):
        protections = (executor.intrabar(bar, intrabar_entries=intrabar_entries, phase=phase) if multi
                       else executor.intrabar(bar, entry_intrabar=bool(intrabar_entries)))
        for signal, fill, trade in protections:
            for index, waiting, stamp, _ in tuple(pending.values()):
                if not multi or (waiting.position_id == signal.position_id and
                                 (waiting.side == 'CLOSE' or finite and orders[index].filled_quantity)):
                    finish(index, waiting, 'CANCELED', fill.fill_date, 'POSITION_CHANGED')
                    pending.pop(index)
            index = len(orders)
            signals.append(SignalRecord(fill.signal_date, signal.side, signal.reason, signal.details, signal.position_id))
            orders.append(OrderResult(fill.signal_date, signal.side, 'PENDING', order_type='PROTECTIVE',
                                      quantity=fill.quantity, position_id=signal.position_id))
            finish(index, signal, 'FILLED', fill.fill_date, signal.reason, fill, trade)

    # Evaluate available strategy signals and submit them at the decision timestamp.
    def decide(stamp, *, preopen=False):
        proposed = signal_provider(DecisionContext(
            tuple(completed), tuple(support), executor.portfolio, bool(pending),
            stamp if preopen else None, tuple(p[1] for p in pending.values())))
        if proposed is None or (trade_start is not None and stamp.date() < trade_start):
            return
        if not multi and pending:
            if proposed.side != 'CLOSE': return
            for index, waiting, _, _ in tuple(pending.values()):
                if waiting.side == 'CLOSE': return
                finish(index, waiting, 'CANCELED', stamp, 'POSITION_CHANGED')
                pending.pop(index)
        candidates = proposed if multi and isinstance(proposed, (tuple, list)) else (proposed,)
        for signal in candidates:
            if finite and signal.side == 'CLOSE':
                for index, waiting, _, _ in tuple(pending.values()):
                    if waiting.side != 'CLOSE' and waiting.position_id == signal.position_id:
                        finish(index, waiting, 'CANCELED', stamp, 'POSITION_CHANGED')
                        pending.pop(index)
            waiting = submit(signal, stamp)
            if waiting is not None:
                pending[waiting[0]] = waiting

    # Group consecutive candles by their recorded trading date.
    for day, day_rows in groupby(bars, key=lambda b: b.trading_date.date()):
        rows = tuple(day_rows)
        if auction_entry and completed and (multi or (not has_position() and not pending)) and (
                trade_start is None or day >= trade_start):
            decision_time = datetime.combine(day, time(8, 45), rows[0].trading_date.tzinfo)
            while support_index < len(support_bars) and support_bars[support_index].available_at <= decision_time:
                support.append(support_bars[support_index])
                support_index += 1
            if on_open is not None: on_open(decision_time)
            decide(decision_time, preopen=True)
        for bar in rows:
            if on_open is not None: on_open(bar.trading_date)
            intrabar_entries = set()
            open_protected = False
            budget = MatchBudget(continuous_match_quantity) if finite else None
            for matched_at, (index, signal, stamp, age) in pending_at_bar(bar):
                if multi and not open_protected and matched_at > bar.trading_date:
                    protect(bar, intrabar_entries, 'open')
                    open_protected = True
                if index not in pending:
                    continue
                lunch_exit = signal.order.result_type == 'NEXT_OPEN' and signal.side == 'CLOSE'
                expired = (bar.trading_date.date() != stamp.date() or (not lunch_exit and (
                           stamp.time() == time(11, 30)
                           or (stamp.time() < time(11, 30) and bar.trading_date.time() >= time(13)))))
                cutoff = (signal.order.result_type not in ('ATO', 'ATC') and signal.side != 'CLOSE' and entry_cutoff
                          and bar.trading_date.strftime('%H:%M') > entry_cutoff)
                if expired or cutoff:
                    finish(index, signal, 'CANCELED', stamp if expired else bar.trading_date,
                           'SESSION_BOUNDARY' if expired else 'ENTRY_CUTOFF')
                    pending.pop(index)
                elif signal.order.result_type == 'ATO':
                    if bar.trading_date.date() != stamp.date() or bar.trading_date.time() != time(9):
                        raise InvalidExecution('MISSING_ATO_MATCH_BAR')
                    match_auction(index, signal, stamp, bar.trading_date, bar.open, bar.trading_date)
                    pending.pop(index)
                elif signal.order.result_type != 'ATC':
                    expected = completed[-1].closed_at
                    if expected.time() == time(11, 30): expected = expected.replace(hour=13, minute=0)
                    if bar.trading_date != expected:
                        raise InvalidExecution('MISSING_PENDING_EXECUTION_BAR')
                    position = executor.portfolio.lot(signal.position_id) if multi else executor.portfolio.position
                    buy = signal.side == 'LONG' or (signal.side == 'CLOSE' and position.sign == -1)
                    bounds = {}
                    if orders[index].order_type in MARKET_TYPES:
                        limit = price_limits.get((bar.trading_date.date(), getattr(bar, 'contract_code', None)))
                        if limit is None: raise InvalidExecution('MISSING_PRICE_LIMITS')
                        floor, ceiling, available, _ = limit
                        if available > bar.trading_date: raise InvalidExecution('INVALID_PRICE_LIMITS')
                        check_market_price(bar.open, floor, ceiling)
                        bounds = {'floor_price': floor, 'ceiling_price': ceiling}
                    match = match_continuous(signal.order, bar, buy=buy, quantity=signal.quantity,
                                             available_quantity=budget.remaining if budget and signal.order.type != 'SIMULATED' else None,
                                             **bounds)
                    if match is not None:
                        fixed = signal.order.type != 'SIMULATED'
                        at_open = (signal.order.type != 'LO' or
                                   (bar.open <= signal.order.limit_price if buy else bar.open >= signal.order.limit_price))
                        expected_price = bar.open if at_open else signal.order.limit_price
                        if finite and (fixed and (type(match.quantity) is not int or not 0 < match.quantity <= signal.quantity)
                                or budget is not None and signal.order.type != 'SIMULATED' and match.quantity > budget.remaining
                                or match.bar_time != bar.trading_date
                                or match.time != (bar.trading_date if at_open else bar.closed_at)
                                or match.price != expected_price
                                or not isinstance(match.price, Decimal) or not match.price.is_finite()
                                or match.price <= 0 or match.price % Decimal('.1')):
                            raise InvalidExecution('MATCH_RESPONSE_OUT_OF_RANGE')
                        if bounds: check_market_price(match.price, floor, ceiling)
                        fill_time = match.time
                        remaining = signal.quantity - match.quantity if fixed else 0
                        try:
                            fill_signal = replace(signal, quantity=match.quantity) if fixed else signal
                            options = ({'continuation': bool(orders[index].filled_quantity) and signal.side != 'CLOSE',
                                        'order_quantity': orders[index].quantity} if finite and signal.order.type != 'SIMULATED' else {})
                            fill, trade = executor.execute(fill_signal, stamp, fill_time, match.price, **options)
                        except InvalidExecution:
                            raise
                        except ValueError as error:
                            finish(index, signal, 'REJECTED', fill_time, str(error))
                        else:
                            if ((fill.price, fill.fill_date) != (match.price, match.time)
                                    or fixed and fill.quantity != match.quantity):
                                raise InvalidExecution('MATCH_RESPONSE_OUT_OF_RANGE')
                            if budget and signal.order.type != 'SIMULATED': budget.consume(fill.quantity)
                            fill = replace(fill, bar_time=bar.trading_date)
                            status = 'FILLED' if not remaining else 'CANCELED' if signal.order.type == 'MAK' else 'PENDING'
                            finish(index, signal, status, fill_time,
                                   'MARKET_REMAINDER_CANCELED' if status == 'CANCELED' else None, fill=fill, trade=trade)
                            if signal.side != 'CLOSE' and fill_time == bar.closed_at:
                                intrabar_entries.add(signal.position_id)
                            if status == 'PENDING':
                                signal = replace(signal, quantity=remaining)
                                if signal.order.type == 'MTL':
                                    converted = mtl_limit_price(match.price, buy=buy, **bounds)
                                    signal = replace(signal, order=OrderRequest('LO', converted, signal.order.max_execution_bars))
                                    old = orders[index]
                                    orders[index] = replace(old, effective_order_type='LO', converted_limit_price=converted,
                                        events=old.events + ({'time': fill_time, 'status': 'converted_to_limit',
                                            'phase': phase_at(fill_time), 'limit_price': converted,
                                            'remaining_quantity': remaining},))
                                    pending[index] = (index, signal, stamp, 0)
                                    continue
                                age += 1
                                if age < (signal.order.max_execution_bars or max_execution_bars):
                                    pending[index] = (index, signal, stamp, age)
                                    continue
                                finish(index, signal, 'EXPIRED', bar.closed_at, 'MAX_EXECUTION_BARS')
                        pending.pop(index)
                    else:
                        if signal.order.type in MARKET_TYPES:
                            finish(index, signal, 'CANCELED', bar.trading_date,
                                   'MOK_NOT_FULL' if signal.order.type == 'MOK' else 'MARKET_NO_COUNTERPARTY')
                            pending.pop(index)
                            continue
                        age += 1
                        if age >= (signal.order.max_execution_bars or max_execution_bars):
                            finish(index, signal, 'EXPIRED', bar.closed_at, 'MAX_EXECUTION_BARS')
                            pending.pop(index)
                        else:
                            pending[index] = (index, signal, stamp, age)
            if multi and not open_protected:
                protect(bar, intrabar_entries, 'open')
            protect(bar, intrabar_entries, 'close' if multi else None)
            if record_start is None or day >= record_start:
                equity.append(EquityPoint(bar.closed_at, executor.portfolio.mark(bar.close)))
            completed.append(bar)
            while support_index < len(support_bars) and support_bars[support_index].available_at <= bar.closed_at:
                support.append(support_bars[support_index])
                support_index += 1
            # The cancellation is a predeclared client policy at the session boundary.
            if pending and bar.closed_at.time() in (time(11, 30), time(14, 30)):
                for index, signal, _, _ in tuple(pending.values()):
                    finish(index, signal, 'CANCELED', bar.closed_at, 'BEFORE_ATC' if bar.closed_at.time() == time(14, 30) else 'LUNCH')
                pending.clear()
            decide(bar.closed_at)

        last = rows[-1]
        auction_mark = None
        for index, signal, stamp, _ in tuple(pending.values()):
            if signal.order.result_type != 'ATC':
                continue
            if last.closed_at.time() != time(14, 30):
                raise InvalidExecution('MISSING_ATC_DECISION_BAR')
            auction_bar = auction_bars.get((day, time(14, 45)))
            auction = auctions.get(day)
            if auction_bar is not None:
                if auction_bar.contract_code != last.contract_code: raise InvalidExecution('ATC_CONTRACT_MISMATCH')
                match_time, price, bar_time = auction_bar.trading_date, auction_bar.close, auction_bar.trading_date
                status = 'matched'
            elif auction is not None:
                if auction.contract_code != last.contract_code: raise InvalidExecution('ATC_CONTRACT_MISMATCH')
                match_time, price, bar_time, status = auction.match_time, auction.price, auction.match_time, auction.status
            else:
                raise InvalidExecution('MISSING_ATC_MATCH_BAR')
            if not stamp < match_time: raise InvalidExecution('ATC_SUBMITTED_TOO_LATE')
            if status == 'no_match':
                finish(index, signal, 'EXPIRED', match_time, 'AUCTION_NO_MATCH')
                matched = False
            else:
                matched = match_auction(index, signal, stamp, match_time, price, bar_time)
            if matched:
                auction_mark = (match_time, price)
            pending.pop(index)
        if auction_mark and (record_start is None or day >= record_start):
            equity.append(EquityPoint(auction_mark[0], executor.portfolio.mark(auction_mark[1])))
        if require_end_flat and has_position() and (
                last.closed_at.time() == time(14, 30) or day != bars[-1].trading_date.date()):
            raise InvalidExecution('END_OF_DAY_POSITION_REQUIRES_EXIT')
        if pending and (last.closed_at.time() in (time(11, 30), time(14, 30)) or day != bars[-1].trading_date.date()):
            for index, signal, _, _ in tuple(pending.values()):
                finish(index, signal, 'CANCELED', last.closed_at, 'SESSION_BOUNDARY')
            pending.clear()
    for index, signal, _, _ in pending.values():
        finish(index, signal, 'EXPIRED', bars[-1].closed_at, 'END_OF_REPORT')
    if not equity: raise ValueError('Report range contains no bars')
    portfolio, final = executor.portfolio, equity[-1].snapshot
    summary = Summary(initial_cash, final.equity, portfolio.realized_pnl, final.unrealized_pnl,
                      (final.equity - initial_cash) / initial_cash)
    return BacktestResult(portfolio, tuple(signals), tuple(orders), tuple(fills), tuple(trades), tuple(equity), summary)
