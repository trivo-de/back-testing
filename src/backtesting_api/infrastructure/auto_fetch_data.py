"""Fetch a six-calendar-month snapshot of completed VNDIRECT five-minute bars."""
import calendar
from datetime import datetime
from decimal import Decimal
import hashlib
import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from .market_snapshot import validate_bars


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
        unix_from, unix_to = int(start.timestamp()), int(now.timestamp())
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
