"""Fetch completed VNDIRECT five-minute bars for latest or report-bound ranges."""
import calendar
from datetime import date, datetime, time, timedelta
from decimal import Decimal
import hashlib
import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from .market_snapshot import validate_bars
from ..domain.session_matching import phase_at


class AutoFetchError(OSError):
    """The upstream data service could not supply a snapshot."""


class AutoDataFetcher:
    def __init__(self, *, clock=None, opener=None):
        self.clock = clock or (lambda: datetime.now(ZoneInfo('Asia/Ho_Chi_Minh')))
        self.opener = opener or urlopen

    def fetch(self):
        now = self.clock().astimezone(ZoneInfo('Asia/Ho_Chi_Minh')).replace(microsecond=0)
        year, month = divmod(now.year * 12 + now.month - 1 - 6, 12)
        start = now.replace(year=year, month=month + 1,
                            day=min(now.day, calendar.monthrange(year, month + 1)[1]))
        return self._fetch_range(int(start.timestamp()), int(now.timestamp()), now)

    def fetch_by_range(self, start_date, end_date, *, warmup_bars=0, session_policy=None,
                       continuous_only=False, history_start=None):
        """Fetch the report with only its required preceding indicator bars."""
        if isinstance(start_date, str):
            start_date = date.fromisoformat(start_date)
        if isinstance(end_date, str):
            end_date = date.fromisoformat(end_date)
        if start_date > end_date:
            raise ValueError('start_date must be less than or equal to end_date')
        now = self.clock().astimezone(ZoneInfo('Asia/Ho_Chi_Minh')).replace(microsecond=0)
        if end_date > now.date():
            raise ValueError('end_date must be less than or equal to now')
        zone = ZoneInfo('Asia/Ho_Chi_Minh')
        report_start = datetime.combine(start_date, time.min, zone)
        report_unix = int(report_start.timestamp())
        range_start = report_start
        if type(warmup_bars) is not int or warmup_bars < 0:
            raise ValueError('INVALID_WARMUP_BARS')
        if warmup_bars:
            if session_policy is None:
                raise ValueError('WARMUP_SESSION_POLICY_REQUIRED')
            for session in session_policy['sessions'].values():
                slots = sorted(datetime.combine(date.fromisoformat(day), time.fromisoformat(label), zone)
                               for day in session_policy['trading_dates']
                               if day < start_date.isoformat() and (history_start is None or day >= history_start)
                               for label in session['required_times'])
                if continuous_only:
                    slots = [stamp for stamp in slots if phase_at(stamp).startswith('CONTINUOUS')]
                if slots:
                    range_start = min(range_start, slots[-min(warmup_bars, len(slots))])
        range_end = datetime.combine(end_date + timedelta(days=1), time.min,
                                     ZoneInfo('Asia/Ho_Chi_Minh')) - timedelta(seconds=1)
        unix_from = int(range_start.timestamp())
        unix_to = min(int(range_end.timestamp()), int(now.timestamp()))
        sources, metadata = self._fetch_range(unix_from, unix_to, now)
        metadata['warmup_bars_requested'] = warmup_bars
        for name, source in sources.items():
            history = [bar for bar in source['bars'] if bar['time'] + 300 <= report_unix
                       and (not continuous_only or phase_at(datetime.fromtimestamp(bar['time'], zone)).startswith('CONTINUOUS'))]
            history_count = min(warmup_bars, len(history))
            cutoff = history[-history_count]['time'] if history_count else report_unix
            retained = [bar for bar in source['bars'] if bar['time'] >= cutoff]
            if retained:
                source['bars'] = retained
            metadata['sources'][name].update(warmup_count=history_count,
                                              retained_count=len(source['bars']))
        if history_start is not None:
            metadata['history_start_limit'] = history_start
        return sources, metadata

    def _fetch_range(self, unix_from, unix_to, now):
        sources = {}
        metadata = {'provider': 'VNDIRECT', 'fetched_at': now.isoformat(),
                    'from': unix_from, 'to': unix_to, 'resolution': '5',
                    'timezone': 'Asia/Ho_Chi_Minh', 'sources': {}}
        for name, symbol in (('trade_data', 'VN30F1M'), ('market_data', 'VNINDEX')):
            url = 'https://dchart-api.vndirect.com.vn/dchart/history?' + urlencode(
                {'symbol': symbol, 'resolution': '5', 'from': unix_from, 'to': unix_to})
            request = Request(url, headers={'User-Agent': 'backtest-hpg/0.1', 'Accept': '*/*'})
            try:
                with self.opener(request, timeout=60) as response:
                    raw = response.read()
            except HTTPError as error:
                raise AutoFetchError(f'AUTO_FETCH_HTTP_ERROR:{name}:{error.code}') from error
            except (URLError, OSError) as error:
                raise AutoFetchError(f'AUTO_FETCH_NETWORK_ERROR:{name}') from error
            try:
                bars = validate_bars(json.loads(raw, parse_float=Decimal))
                if any(not unix_from <= bar['time'] <= unix_to or bar['time'] % 300 for bar in bars):
                    raise ValueError('timestamps outside request or not on five-minute boundaries')
            except (ValueError, UnicodeError) as error:
                raise ValueError(f'AUTO_FETCH_INVALID_SOURCE:{name}:{error}') from error
            closed = [bar for bar in bars if bar['time'] + 300 <= unix_to]
            if not closed:
                raise ValueError(f'AUTO_FETCH_NO_CLOSED_BARS:{name}')
            sources[name] = {'symbol': symbol, 'resolution': '5', 'timestamp_unit': 's',
                             'timezone': metadata['timezone'], 'bars': [
                                 {key: value if key == 'time' else str(value) for key, value in bar.items()}
                                 for bar in closed]}
            metadata['sources'][name] = {
                'symbol': symbol, 'source_url': url, 'raw_hash': hashlib.sha256(raw).hexdigest(),
                'raw_count': len(bars), 'closed_count': len(closed),
                'excluded_unclosed_count': len(bars) - len(closed),
                'first_time': closed[0]['time'], 'last_time': closed[-1]['time'],
            }
        return sources, metadata
