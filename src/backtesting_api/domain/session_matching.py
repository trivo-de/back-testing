"""HNX session simulation on OHLC; auction prices are caller-provided facts."""
from dataclasses import dataclass, replace
from datetime import datetime, time, timedelta
from decimal import Decimal
from itertools import groupby
from .engine import DecisionContext
from .execution import InvalidExecution
from .results import BacktestResult, EquityPoint, Summary
from .trading import OrderResult, SignalRecord


def phase_at(stamp):
    local = stamp.time()
    if time(8, 45) <= local < time(9): return 'ATO'
    if time(9) <= local < time(11, 30): return 'CONTINUOUS_AM'
    if time(11, 30) <= local < time(13): return 'LUNCH'
    if time(13) <= local < time(14, 30): return 'CONTINUOUS_PM'
    if time(14, 30) <= local < time(14, 45): return 'ATC'
    return 'CLOSED'


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
                       auction_entry=False, auction_match_quantity=None, require_end_flat=False):
    """One position and one pending intent, with stable signal/order/fill links."""
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
    pending = None
    support_index = 0

    def finish(index, signal, status, stamp, reason=None, fill=None, trade=None):
        old = orders[index]
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
        if status in ('REJECTED', 'CANCELED', 'EXPIRED') and remaining is not None:
            expired_quantity += remaining
            remaining = 0
        events += ({'time': stamp, 'status': status.lower(), 'reason': reason, 'phase': phase,
                    'filled_quantity': filled_quantity, 'expired_quantity': expired_quantity,
                    'remaining_quantity': remaining},)
        orders[index] = replace(old, status=status, reason=reason, events=events,
                                fill_index=fill_indices[0] if fill_indices else old.fill_index,
                                fill_indices=fill_indices, filled_quantity=filled_quantity,
                                expired_quantity=expired_quantity, remaining_quantity=remaining)
        if trade is not None: trades.append(trade)
        if on_execution: on_execution(signal, orders[index], fill)

    def submit(signal, stamp):
        index = len(orders)
        signals.append(SignalRecord(stamp, signal.side, signal.reason, signal.details))
        orders.append(OrderResult(stamp, signal.side, 'PENDING', order_type=signal.order_type,
                                  quantity=signal.quantity, limit_price=signal.limit_price,
                                  events=({'time': stamp, 'status': 'submitted', 'reason': None,
                                           'phase': phase_at(stamp)},)))
        try:
            executor.validate(signal)
            if signal.order_type == 'ATO' and (signal.side not in ('LONG', 'SHORT') or phase_at(stamp) != 'ATO'):
                raise ValueError('ATO_ENTRY_REQUIRES_PREOPEN_SUBMISSION')
            if signal.order_type == 'ATC' and (signal.side != 'CLOSE' or phase_at(stamp) != 'ATC'):
                raise ValueError('ATC_CLOSE_REQUIRES_1430_SUBMISSION')
            lunch_exit = signal.order_type == 'NEXT_OPEN' and signal.side == 'CLOSE' and stamp.time() == time(11, 30)
            if signal.order_type not in ('ATO', 'ATC') and not phase_at(stamp).startswith('CONTINUOUS') and not lunch_exit:
                raise ValueError('ORDER_OUTSIDE_CONTINUOUS_SESSION')
            reference_price = completed[-1].close if signal.order_type == 'ATO' and completed else None
            signal = executor.prepare_order(signal, reference_price)
        except ValueError as error:
            finish(index, signal, 'REJECTED', stamp, str(error))
            return None
        submitted = {**orders[index].events[0], 'filled_quantity': 0,
                     'expired_quantity': 0, 'remaining_quantity': signal.quantity}
        orders[index] = replace(orders[index], quantity=signal.quantity, remaining_quantity=signal.quantity,
                                events=(submitted,))
        return (index, signal, stamp, 0)

    def match_auction(index, signal, stamp, match_time, price, bar_time):
        # shortcut: giới hạn cố định cho từng lệnh; nâng cấp khi hợp đồng dữ liệu thanh khoản được duyệt.
        matched = signal.quantity if auction_match_quantity is None else min(signal.quantity, auction_match_quantity)
        if matched == 0:
            finish(index, signal, 'EXPIRED', match_time, 'AUCTION_NO_MATCH')
            return False
        try:
            fill, trade = executor.execute(replace(signal, quantity=matched), stamp, match_time, price)
        except InvalidExecution:
            raise
        except ValueError as error:
            finish(index, signal, 'REJECTED', match_time, str(error))
            return False
        fill = replace(fill, bar_time=bar_time)
        partial = matched < signal.quantity
        finish(index, signal, 'EXPIRED' if partial else 'FILLED', match_time,
               'AUCTION_REMAINDER_EXPIRED' if partial else None, fill, trade)
        return True

    for day, day_rows in groupby(bars, key=lambda b: b.trading_date.date()):
        rows = tuple(day_rows)
        if auction_entry and completed and executor.portfolio.position is None and pending is None and (
                trade_start is None or day >= trade_start):
            decision_time = datetime.combine(day, time(8, 45), rows[0].trading_date.tzinfo)
            while support_index < len(support_bars) and support_bars[support_index].available_at <= decision_time:
                support.append(support_bars[support_index])
                support_index += 1
            if on_open is not None: on_open(decision_time)
            signal = signal_provider(DecisionContext(tuple(completed), tuple(support), executor.portfolio,
                                                     pending is not None, decision_time))
            if signal is not None:
                pending = submit(signal, decision_time)
        for bar in rows:
            if on_open is not None: on_open(bar.trading_date)
            intrabar_entry = False
            if pending:
                index, signal, stamp, age = pending
                lunch_exit = signal.order_type == 'NEXT_OPEN' and signal.side == 'CLOSE'
                expired = (bar.trading_date.date() != stamp.date() or (not lunch_exit and (
                           stamp.time() == time(11, 30)
                           or (stamp.time() < time(11, 30) and bar.trading_date.time() >= time(13)))))
                cutoff = (signal.order_type not in ('ATO', 'ATC') and signal.side != 'CLOSE' and entry_cutoff
                          and bar.trading_date.strftime('%H:%M') > entry_cutoff)
                if expired or cutoff:
                    finish(index, signal, 'CANCELED', stamp if expired else bar.trading_date,
                           'SESSION_BOUNDARY' if expired else 'ENTRY_CUTOFF')
                    pending = None
                elif signal.order_type == 'ATO':
                    if bar.trading_date.date() != stamp.date() or bar.trading_date.time() != time(9):
                        raise InvalidExecution('MISSING_ATO_MATCH_BAR')
                    match_auction(index, signal, stamp, bar.trading_date, bar.open, bar.trading_date)
                    pending = None
                elif signal.order_type != 'ATC':
                    expected = completed[-1].closed_at
                    if expected.time() == time(11, 30): expected = expected.replace(hour=13, minute=0)
                    if bar.trading_date != expected:
                        raise InvalidExecution('MISSING_PENDING_EXECUTION_BAR')
                    price, fill_time = None, bar.trading_date
                    if signal.order_type == 'NEXT_OPEN':
                        price = bar.open
                    else:
                        buy = signal.side == 'LONG' or (signal.side == 'CLOSE' and executor.portfolio.position.sign == -1)
                        if (bar.open <= signal.limit_price if buy else bar.open >= signal.limit_price):
                            price = bar.open
                        elif (bar.low <= signal.limit_price if buy else bar.high >= signal.limit_price):
                            price, fill_time = signal.limit_price, bar.closed_at
                    if price is not None:
                        try:
                            fill, trade = executor.execute(signal, stamp, fill_time, price)
                        except InvalidExecution:
                            raise
                        except ValueError as error:
                            finish(index, signal, 'REJECTED', fill_time, str(error))
                        else:
                            fill = replace(fill, bar_time=bar.trading_date)
                            finish(index, signal, 'FILLED', fill_time, fill=fill, trade=trade)
                            intrabar_entry = signal.side != 'CLOSE' and fill_time == bar.closed_at
                        pending = None
                    else:
                        age += 1
                        if age >= max_execution_bars:
                            finish(index, signal, 'EXPIRED', bar.closed_at, 'MAX_EXECUTION_BARS')
                            pending = None
                        else:
                            pending = (index, signal, stamp, age)
            for signal, fill, trade in executor.intrabar(bar, entry_intrabar=intrabar_entry):
                if pending:
                    index, waiting, stamp, _ = pending
                    finish(index, waiting, 'CANCELED', fill.fill_date, 'POSITION_CHANGED')
                    pending = None
                index = len(orders)
                signals.append(SignalRecord(fill.signal_date, signal.side, signal.reason, signal.details))
                orders.append(OrderResult(fill.signal_date, signal.side, 'PENDING', order_type='PROTECTIVE',
                                          quantity=fill.quantity))
                finish(index, signal, 'FILLED', fill.fill_date, signal.reason, fill, trade)
            if record_start is None or day >= record_start:
                equity.append(EquityPoint(bar.closed_at, executor.portfolio.mark(bar.close)))
            completed.append(bar)
            while support_index < len(support_bars) and support_bars[support_index].available_at <= bar.closed_at:
                support.append(support_bars[support_index])
                support_index += 1
            # The cancellation is a predeclared client policy at the session boundary.
            if pending and bar.closed_at.time() in (time(11, 30), time(14, 30)):
                index, signal, _, _ = pending
                finish(index, signal, 'CANCELED', bar.closed_at, 'BEFORE_ATC' if bar.closed_at.time() == time(14, 30) else 'LUNCH')
                pending = None
            signal = signal_provider(DecisionContext(tuple(completed), tuple(support), executor.portfolio, pending is not None))
            if signal and (trade_start is None or day >= trade_start) and pending is None:
                pending = submit(signal, bar.closed_at)

        last = rows[-1]
        if pending and pending[1].order_type == 'ATC':
            index, signal, stamp, _ = pending
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
                if record_start is None or day >= record_start:
                    equity.append(EquityPoint(match_time, executor.portfolio.mark(price)))
            pending = None
        if require_end_flat and executor.portfolio.position and (
                last.closed_at.time() == time(14, 30) or day != bars[-1].trading_date.date()):
            raise InvalidExecution('END_OF_DAY_POSITION_REQUIRES_EXIT')
        if pending and (last.closed_at.time() in (time(11, 30), time(14, 30)) or day != bars[-1].trading_date.date()):
            index, signal, _, _ = pending
            finish(index, signal, 'CANCELED', last.closed_at, 'SESSION_BOUNDARY')
            pending = None
    if pending:
        index, signal, _, _ = pending
        finish(index, signal, 'EXPIRED', bars[-1].closed_at, 'END_OF_REPORT')
    if not equity: raise ValueError('Report range contains no bars')
    portfolio, final = executor.portfolio, equity[-1].snapshot
    summary = Summary(initial_cash, final.equity, portfolio.realized_pnl, final.unrealized_pnl,
                      (final.equity - initial_cash) / initial_cash)
    return BacktestResult(portfolio, tuple(signals), tuple(orders), tuple(fills), tuple(trades), tuple(equity), summary)
