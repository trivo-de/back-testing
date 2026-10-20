"""Quy tắc giá/lượng khớp OHLC; việc áp dụng vào tài khoản thuộc executor."""
from dataclasses import dataclass
from decimal import Decimal
from .market import BarTime


@dataclass(frozen=True)
class Match:
    price: Decimal
    time: BarTime
    quantity: int | None
    bar_time: BarTime


def match_next_open(order, bar, quantity=None):
    order.validate()
    if order.type != 'SIMULATED':
        raise ValueError('ORDER_UNSUPPORTED_BY_NEXT_OPEN')
    return Match(bar.open, bar.trading_date, quantity, bar.trading_date)


def match_continuous(order, bar, *, buy, quantity):
    order.validate()
    if order.type == 'SIMULATED':
        return match_next_open(order, bar, quantity)
    if order.type != 'LO':
        raise ValueError('ORDER_UNSUPPORTED_IN_CONTINUOUS_SESSION')
    if (bar.open <= order.limit_price if buy else bar.open >= order.limit_price):
        return Match(bar.open, bar.trading_date, quantity, bar.trading_date)
    if (bar.low <= order.limit_price if buy else bar.high >= order.limit_price):
        return Match(order.limit_price, bar.closed_at, quantity, bar.trading_date)
    return None


def match_auction(order, *, price, time, bar_time, quantity, quantity_limit=None):
    order.validate()
    if order.type not in ('ATO', 'ATC'):
        raise ValueError('ORDER_UNSUPPORTED_IN_AUCTION')
    if quantity_limit is not None and (type(quantity_limit) is not int or quantity_limit < 0):
        raise ValueError('INVALID_AUCTION_MATCH_QUANTITY')
    matched = quantity if quantity_limit is None else min(quantity, quantity_limit)
    return Match(price, time, matched, bar_time) if matched else None
