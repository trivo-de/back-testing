"""Resolve validated inline data without selecting a strategy by symbol."""
from bisect import bisect_left
from dataclasses import dataclass, replace
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo
from ..domain.market import StrategyBar
from ..infrastructure.market_snapshot import normalize_raw_source


@dataclass(frozen=True)
class InputBar(StrategyBar):
    volume: Decimal | None
    available_at: datetime | None = None
    contract_code: str | None = None
    data_gap_before: bool = False


@dataclass(frozen=True)
class InlineData:
    bars: tuple[InputBar, ...]
    market_bars: tuple[InputBar, ...]
    start_date: date
    end_date: date
    metadata: dict


def _timestamp(value, unit, zone):
    # Integer arithmetic preserves Unix millisecond precision.
    scale = 1000 if unit == 'ms' else 1
    return (datetime(1970, 1, 1, tzinfo=timezone.utc) +
            timedelta(seconds=value // scale, milliseconds=value % scale if scale == 1000 else 0)).astimezone(zone)


def _bars(source):
    zone = ZoneInfo(source['timezone'])
    unit = source['timestamp_unit']
    rows = []
    for row in source['bars']:
        opened = _timestamp(row['time'], unit, zone)
        closed = (_timestamp(row['close_time'], unit, zone) if row.get('close_time') is not None
                  else opened + timedelta(minutes=5))
        available = _timestamp(row['available_at'], unit, zone) if row.get('available_at') is not None else closed
        rows.append(InputBar(opened, *(Decimal(row[name]) for name in ('open', 'high', 'low', 'close')),
                             Decimal(row['volume']) if row.get('volume') is not None else None,
                             close_time=closed, available_at=available))
    return tuple(rows)


def _session_gaps(bars, source, name, policy, first, last):
    if source['resolution'] != '5':
        return bars, []
    zone = ZoneInfo(policy['timezone'])
    calendar = set(map(date.fromisoformat, policy['trading_dates']))
    bounds = policy['calendar_range']
    if first < date.fromisoformat(bounds['start']) or last > date.fromisoformat(bounds['end']):
        raise ValueError('REPORT_OUTSIDE_STATIC_CALENDAR')
    sessions = policy['sessions']
    session = sessions.get(name) or sessions.get(source.get('symbol'))
    if session is None:
        raise ValueError(f'SESSION_POLICY_MISSING:{name}')
    required, optional = session['required_times'], session['optional_times']
    observed = set()
    for bar in bars:
        stamp = bar.trading_date.astimezone(zone)
        if (stamp.date() not in calendar or stamp.second or stamp.microsecond
                or stamp.strftime('%H:%M') not in required + optional
                or bar.closed_at - bar.trading_date != timedelta(minutes=5)):
            raise ValueError(f'UNEXPECTED_BAR:{name}:{stamp.isoformat()}')
        observed.add(stamp)
    expected = sorted(datetime.combine(day, time.fromisoformat(label), zone)
                      for day in calendar if first <= day <= last for label in required)
    gaps = [stamp for stamp in expected if stamp not in observed]
    previous = datetime.combine(first, time.min, zone) - timedelta(microseconds=1)
    resolved = []
    gap_index = 0
    for bar in bars:
        has_gap = False
        while gap_index < len(gaps) and gaps[gap_index] < bar.trading_date:
            has_gap |= gaps[gap_index] > previous
            gap_index += 1
        resolved.append(replace(bar, data_gap_before=has_gap))
        previous = bar.trading_date
    return tuple(resolved), [stamp.isoformat() for stamp in gaps]


def resolve_inline(payload, policy=None):
    """Keep history, trim the report end, and never infer contract identity from prices."""
    payload['trade_data'] = normalize_raw_source(payload['trade_data'])
    if payload.get('market_data'):
        payload['market_data'] = normalize_raw_source(payload['market_data'])
    trade = _bars(payload['trade_data'])
    report = payload.get('report') or {'start_date': trade[0].trading_date.date().isoformat(),
                                     'end_date': trade[-1].trading_date.date().isoformat()}
    start, end = (date.fromisoformat(report[key]) for key in ('start_date', 'end_date'))
    zone = ZoneInfo(payload['trade_data']['timezone'])
    end_exclusive = datetime.combine(end + timedelta(days=1), time.min, zone)
    trade = tuple(bar for bar in trade if bar.trading_date < end_exclusive)
    if not any(start <= bar.trading_date.date() <= end for bar in trade):
        raise ValueError('REPORT_DATA_MISSING')
    market_source = payload.get('market_data')
    market = tuple(bar for bar in _bars(market_source) if bar.available_at < end_exclusive) if market_source else ()
    mapping = payload['trade_data'].get('contract_map', [])
    if mapping:
        expiries = [date.fromisoformat(row['expiry_date']) for row in mapping]
        if any((b.year * 12 + b.month) - (a.year * 12 + a.month) != 1 for a, b in zip(expiries, expiries[1:])):
            raise ValueError('CONTRACT_MAP_MONTH_MISSING')
        # The first row covers its calendar month; earlier months need their own map rows.
        if trade[0].trading_date.date() < expiries[0].replace(day=1) or end > expiries[-1]:
            raise ValueError('CONTRACT_MAP_COVERAGE_MISSING')
        trade = tuple(replace(bar, contract_code=mapping[bisect_left(expiries, bar.trading_date.date())]['contract_code'])
                      for bar in trade)
    gaps = {}
    if mapping:
        if policy is None: raise ValueError('STATIC_SESSION_POLICY_REQUIRED')
        if policy.get('schema_version') != 1 or policy.get('timezone') != 'Asia/Ho_Chi_Minh':
            raise ValueError('SESSION_POLICY_UNSUPPORTED')
        if payload['trade_data']['timezone'] != policy['timezone']:
            raise ValueError('CONTRACT_TIMEZONE_MISMATCH')
        for name, source in (('trade_data', payload['trade_data']), ('market_data', market_source)):
            rows = trade if name == 'trade_data' else market
            if source is None: continue
            rows, gaps[name] = _session_gaps(rows, source, name, policy,
                                           min(start, rows[0].trading_date.astimezone(zone).date()) if rows else start, end)
            if name == 'trade_data': trade = rows
            else: market = rows
    return InlineData(trade, market, start, end, {
        'report_range': {'start': start.isoformat(), 'end': end.isoformat()},
        'symbol': payload['trade_data'].get('symbol'), 'timezone': payload['trade_data']['timezone'],
        'price_unit': payload['trade_data'].get('price_unit'),
        'indicator_specs': payload['strategy'].get('indicators', {}),
        'resolution': payload['trade_data']['resolution'],
        'contract_map': mapping, 'data_gaps': gaps,
        'warmup_bars': {'trade_data': sum(bar.trading_date.date() < start for bar in trade),
                        'market_data': sum(bar.available_at < datetime.combine(start, time.min, zone) for bar in market)},
        'input_origin': 'caller_provided',
        'assumptions': {'five_minute_default': 'close=open+300s; available=close',
                        'alignment': 'distinct market bars with available_at <= decision time',
                        'missing_data': 'reported, never filled', 'price_limit_check': 'not performed; reference price not supplied'},
    })
