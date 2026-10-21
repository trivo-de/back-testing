"""Resolve validated inline data without selecting a strategy by symbol."""
from bisect import bisect_left
from dataclasses import dataclass, field, replace
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo
from ..domain.market import StrategyBar
from ..domain.session_matching import AuctionEvent, phase_at
from ..infrastructure.market_snapshot import normalize_raw_source
from .order_config import order_configuration, strategy_orders


# Carry a strategy candle with volume, availability, and contract identity.
@dataclass(frozen=True)
class InputBar(StrategyBar):
    volume: Decimal | None
    available_at: datetime | None = None
    contract_code: str | None = None
    data_gap_before: bool = False


# Carry resolved candles, report bounds, and source metadata into execution.
@dataclass(frozen=True)
class InlineData:
    bars: tuple[InputBar, ...]
    market_bars: tuple[InputBar, ...]
    start_date: date
    end_date: date
    metadata: dict
    auction_events: tuple[AuctionEvent, ...] = ()
    price_limits: dict = field(default_factory=dict)


# Convert Unix seconds or milliseconds into the source timezone.
def _timestamp(value, unit, zone):
    # Integer arithmetic preserves Unix millisecond precision.
    scale = 1000 if unit == 'ms' else 1
    return (datetime(1970, 1, 1, tzinfo=timezone.utc) +
            timedelta(seconds=value // scale, milliseconds=value % scale if scale == 1000 else 0)).astimezone(zone)


# Convert source rows into immutable candles without filling missing values.
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


# Detect missing session slots and mark indicator continuity boundaries.
def _session_gaps(bars, source, name, policy, first, last, report_start):
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
        # History may start mid-session; report dates still require full-session checks.
    required_from = datetime.combine(report_start, time.min, zone)
    if bars: required_from = min(required_from, bars[0].trading_date.astimezone(zone))
    gaps = [stamp for stamp in expected if stamp >= required_from and stamp not in observed]
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


def resolve_inline(payload, policy=None, *, derive_contract_dates=False):
    """Keep history, trim the report end, and never infer contract identity from prices."""
    payload['trade_data'] = normalize_raw_source(payload['trade_data'])
    if payload.get('market_data'):
        payload['market_data'] = normalize_raw_source(payload['market_data'])
    trade = _bars(payload['trade_data'])
    report = payload.get('report') or {'start_date': trade[0].trading_date.date().isoformat(),
                                     'end_date': trade[-1].trading_date.date().isoformat()}
    start, end = (date.fromisoformat(report[key]) for key in ('start_date', 'end_date'))
    if start > end:
        raise ValueError('INVALID_REPORT_RANGE')
    first, last = trade[0].trading_date.date(), trade[-1].trading_date.date()
    mapping = payload['trade_data'].get('contract_map', [])
    session = payload['execution'].get('matching_model') == 'hnx_sessions_v1'
    if mapping or session:
        if policy is None: raise ValueError('STATIC_SESSION_POLICY_REQUIRED')
        if policy.get('schema_version') != 1 or policy.get('timezone') != 'Asia/Ho_Chi_Minh':
            raise ValueError('SESSION_POLICY_UNSUPPORTED')
        if payload['trade_data']['timezone'] != policy['timezone']:
            raise ValueError('CONTRACT_TIMEZONE_MISMATCH')
        bounds = policy['calendar_range']
        if start < date.fromisoformat(bounds['start']) or end > date.fromisoformat(bounds['end']):
            raise ValueError('REPORT_OUTSIDE_STATIC_CALENDAR')
    report_dates = [bar.trading_date.date() for bar in trade if start <= bar.trading_date.date() <= end]
    if not report_dates:
        raise ValueError(f'REPORT_DATA_MISSING:requested={start}..{end};available={first}..{last}')
    zone = ZoneInfo(payload['trade_data']['timezone'])
    end_exclusive = datetime.combine(end + timedelta(days=1), time.min, zone)
    trade = tuple(bar for bar in trade if bar.trading_date < end_exclusive)
    market_source = payload.get('market_data')
    market = tuple(bar for bar in _bars(market_source) if bar.available_at < end_exclusive) if market_source else ()
    contract_dates = payload['trade_data'].get('contract_dates', [])
    if derive_contract_dates and not mapping:
        raise ValueError('CONTRACT_MAP_COVERAGE_MISSING')
    if session and not derive_contract_dates:
        codes = {date.fromisoformat(row['date']): row['contract_code'] for row in contract_dates}
        if any(bar.trading_date.date() not in codes for bar in trade):
            raise ValueError('CONTRACT_DATES_COVERAGE_MISSING')
        trade = tuple(replace(bar, contract_code=codes[bar.trading_date.date()]) for bar in trade)
    elif mapping:
        expiries = [date.fromisoformat(row['expiry_date']) for row in mapping]
        if any((b.year * 12 + b.month) - (a.year * 12 + a.month) != 1 for a, b in zip(expiries, expiries[1:])):
            raise ValueError('CONTRACT_MAP_MONTH_MISSING')
        # The first row covers its calendar month; earlier months need their own map rows.
        if trade[0].trading_date.date() < expiries[0].replace(day=1) or end > expiries[-1]:
            raise ValueError('CONTRACT_MAP_COVERAGE_MISSING')
        trade = tuple(replace(bar, contract_code=mapping[bisect_left(expiries, bar.trading_date.date())]['contract_code'])
                      for bar in trade)
        if session:
            codes = {bar.trading_date.date(): bar.contract_code for bar in trade}
            contract_dates = [{'date': day.isoformat(), 'contract_code': code} for day, code in sorted(codes.items())]
            payload['trade_data']['contract_dates'] = contract_dates
    gaps = {}
    if mapping or session:
        for name, source in (('trade_data', payload['trade_data']), ('market_data', market_source)):
            rows = trade if name == 'trade_data' else market
            if source is None: continue
            rows, gaps[name] = _session_gaps(rows, source, name, policy,
                                           min(start, rows[0].trading_date.astimezone(zone).date()) if rows else start, end, start)
            if name == 'trade_data': trade = rows
            else: market = rows
    auctions = []
    source = payload['trade_data']
    for row in source.get('auctions', []):
        matched = _timestamp(row['match_time'], source['timestamp_unit'], zone)
        if not start <= matched.date() <= end: continue
        available = _timestamp(row['available_at'], source['timestamp_unit'], zone)
        if policy and matched.date().isoformat() not in policy['trading_dates']:
            raise ValueError('AUCTION_OUTSIDE_TRADING_CALENDAR')
        if session and codes.get(matched.date()) != row['contract_code']:
            raise ValueError('ATC_CONTRACT_MISMATCH')
        auctions.append(AuctionEvent(row['contract_code'], matched, available, row['status'],
                                     Decimal(row['price']) if row.get('price') is not None else None, row['source']))
    price_limits = {}
    previous_limit = None
    for row in source.get('price_limits', []):
        key = (date.fromisoformat(row['trading_date']), row['contract_code'])
        if previous_limit is not None and key <= previous_limit:
            raise ValueError('INVALID_PRICE_LIMITS')
        previous_limit = key
        try:
            available = _timestamp(row['available_at'], 's', zone)
        except (OverflowError, ValueError, OSError):
            raise ValueError('INVALID_PRICE_LIMITS') from None
        if key[0] != available.date() or (session and codes.get(key[0]) != key[1]):
            raise ValueError('INVALID_PRICE_LIMITS')
        price_limits[key] = (Decimal(row['floor_price']), Decimal(row['ceiling_price']), available, row['source'])
    entry_orders, close_orders = strategy_orders(payload)
    uses_market = any(a['order']['type'] in ('MTL', 'MOK', 'MAK') for a in (*entry_orders.values(), *close_orders.values()))
    if uses_market:
        if start < date(2025, 5, 5) or end > date(2026, 10, 20):
            raise ValueError('MARKET_RULES_OUTSIDE_VERIFIED_RANGE')
        for bar in trade:
            if not start <= bar.trading_date.date() <= end or not phase_at(bar.trading_date).startswith('CONTINUOUS'):
                continue
            key = (bar.trading_date.date(), bar.contract_code)
            if key not in price_limits: raise ValueError('MISSING_PRICE_LIMITS')
            if price_limits[key][2] > bar.trading_date: raise ValueError('INVALID_PRICE_LIMITS')
    metadata = {
        'report_range': {'start': start.isoformat(), 'end': end.isoformat()},
        'available_range': {'start': report_dates[0].isoformat(), 'end': report_dates[-1].isoformat()},
        'symbol': payload['trade_data'].get('symbol'), 'timezone': payload['trade_data']['timezone'],
        'price_unit': payload['trade_data'].get('price_unit'),
        'indicator_specs': payload['strategy'].get('indicators', {}),
        'order_configuration': order_configuration(payload),
        'resolution': payload['trade_data']['resolution'],
        'contract_map': mapping, 'data_gaps': gaps,
        'warmup_bars': {'trade_data': sum(bar.trading_date.date() < start for bar in trade),
                        'market_data': sum(bar.available_at < datetime.combine(start, time.min, zone) for bar in market)},
        'input_origin': 'caller_provided',
        'assumptions': {'five_minute_default': 'close=open+300s; available=close',
                        'alignment': 'distinct market bars with available_at <= decision time',
                        'missing_data': 'reported, never filled', 'price_limit_check': 'not performed; reference price not supplied'},
    }
    if session:
        provider = source['provenance']['provider']
        auction_quantity = payload['execution'].get('auction_match_quantity')
        metadata.update(matching_model='hnx_sessions_v1', matching_rules_version='hnx-sessions-v2-ato-atc-partial',
                        contract_dates=contract_dates, provenance=source['provenance'],
                        auction_sources=sorted({provider, *(a.source for a in auctions)}),
                        auction_match_quantity=auction_quantity)
        metadata['assumptions'].update(
            quantity_fill=('full auction quantity; no queue/liquidity model' if auction_quantity is None else
                           f'fixed auction cap of {auction_quantity} contracts per order; no volume/queue model'),
            lo_fill='Open if better or equal, otherwise limit on OHLC touch',
            intrabar_lo_entry='stop active on entry bar; profit targets from next bar',
            lo_cancellation='client policy: no lunch crossing; cancel before ATC',
            auction_price='ATO uses 09:00 Open; ATC uses 14:45 Close; stored legacy ATC events remain readable',
            ato_sizing='quantity frozen at 08:45 from the latest completed continuous Close; margin rechecked at 09:00 Open',
            auction_remainder='unmatched quantity expires at the auction match time',
            auction_availability='ATO Open is available at 09:00; ATC Close uses the 14:45 bar available_at')
        if payload['strategy']['sizing'].get('pyramiding'):
            metadata['matching_rules_version'] = 'hnx-sessions-v3-multi-lot'
            metadata['assumptions'].update(
                multi_position='independent entry lots; reduce-only close per position_id; held plus pending opens reserve max_contracts',
                multi_bar_order='pending Open fills, Open protections, pending Close-time touches, Close-time protections; submission/lot order breaks ties',
                multi_protection='Open targets precede later intrabar stops; trailing updates after Close; one-position legacy precedence unchanged')
        continuous_quantity = payload['execution'].get('continuous_match_quantity')
        if continuous_quantity is not None:
            metadata.update(matching_rules_version='hnx-sessions-v4-market-orders',
                            continuous_match_quantity=continuous_quantity, price_limits=source.get('price_limits', []))
            metadata['assumptions'].update(
                quantity_fill=f'fixed shared cap of {continuous_quantity} contracts per bar/contract across Open and Close; submission order within each event',
                market_price='next continuous bar Open; quantity frozen from completed signal Close; margin rechecked at fill',
                mtl_remainder='LO from last fill +/- 0.1 within supplied daily limits; eligible from following bar',
                price_limit_check='supplied daily floor/ceiling required for MTL/MOK/MAK; no inferred bounds',
                repeated_entry='same order only: weighted cost basis; first fill anchors protection/holding time; one daily entry count',
                protective_quantity='existing stop/TP fills bypass the fixed cap; auctions retain their per-order cap')
    return InlineData(trade, market, start, end, metadata, tuple(auctions), price_limits)
