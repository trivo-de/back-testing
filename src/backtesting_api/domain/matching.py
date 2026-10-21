"""Simulate OHLC match prices and quantities; executors apply account changes."""
from dataclasses import dataclass
from decimal import Decimal
from .market import BarTime
from .orders import MARKET_TYPES


class MatchBudget:
    """Share simulated quantity across a candle's open and close; consume after accounting."""
    # Initialize the nonnegative simulated matching quantity for a candle.
    def __init__(self, quantity):
        if type(quantity) is not int or quantity < 0:
            raise ValueError('INVALID_CONTINUOUS_MATCH_QUANTITY')
        self.remaining = quantity

    # Deduct a validated fill quantity from the candle's remaining budget.
    def consume(self, quantity):
        if type(quantity) is not int or not 0 <= quantity <= self.remaining:
            raise ValueError('MATCH_RESPONSE_OUT_OF_RANGE')
        self.remaining -= quantity


# Validate a market match price against supplied limits and tick size.
def check_market_price(price, floor_price, ceiling_price):
    if floor_price is None or ceiling_price is None:
        raise ValueError('MISSING_PRICE_LIMITS')
    if any(not isinstance(p, Decimal) or not p.is_finite() or p <= 0 or p % Decimal('.1')
           for p in (floor_price, ceiling_price)) or floor_price > ceiling_price:
        raise ValueError('INVALID_PRICE_LIMITS')
    if (not isinstance(price, Decimal) or not price.is_finite() or price <= 0
            or price % Decimal('.1') or not floor_price <= price <= ceiling_price):
        raise ValueError('INVALID_MARKET_MATCH_PRICE')


# Convert an MTL remainder to a one-tick limit within daily price bounds.
def mtl_limit_price(price, *, buy, floor_price, ceiling_price):
    check_market_price(price, floor_price, ceiling_price)
    return min(price + Decimal('.1'), ceiling_price) if buy else max(price - Decimal('.1'), floor_price)


# Record a simulated match price, time, quantity, and source candle.
@dataclass(frozen=True)
class Match:
    price: Decimal
    time: BarTime
    quantity: int | None
    bar_time: BarTime


# Match a simulated order at the next candle open.
def match_next_open(order, bar, quantity=None):
    order.validate()
    if order.type != 'SIMULATED':
        raise ValueError('ORDER_UNSUPPORTED_BY_NEXT_OPEN')
    return Match(bar.open, bar.trading_date, quantity, bar.trading_date)


# Simulate continuous-session matching using OHLC prices and optional quantity caps.
def match_continuous(order, bar, *, buy, quantity, available_quantity=None,
                     floor_price=None, ceiling_price=None):
    order.validate()
    if order.type == 'SIMULATED':
        return match_next_open(order, bar, quantity)
    if type(quantity) is not int or quantity < 1:
        raise ValueError('ORDER_QUANTITY_REQUIRED')
    if available_quantity is not None and (type(available_quantity) is not int or available_quantity < 0):
        raise ValueError('INVALID_CONTINUOUS_MATCH_QUANTITY')
    if order.type in MARKET_TYPES:
        check_market_price(bar.open, floor_price, ceiling_price)
        if available_quantity is None:
            raise ValueError('MARKET_ORDER_REQUIRES_MATCH_QUANTITY')
        if order.type == 'MOK' and available_quantity < quantity:
            return None
        matched = min(quantity, available_quantity)
        return Match(bar.open, bar.trading_date, matched, bar.trading_date) if matched else None
    if order.type != 'LO':
        raise ValueError('ORDER_UNSUPPORTED_IN_CONTINUOUS_SESSION')
    if available_quantity is not None:
        quantity = min(quantity, available_quantity)
        if not quantity:
            return None
    if (bar.open <= order.limit_price if buy else bar.open >= order.limit_price):
        return Match(bar.open, bar.trading_date, quantity, bar.trading_date)
    if (bar.low <= order.limit_price if buy else bar.high >= order.limit_price):
        return Match(order.limit_price, bar.closed_at, quantity, bar.trading_date)
    return None


# Simulate an ATO or ATC match at the supplied auction observation.
def match_auction(order, *, price, time, bar_time, quantity, quantity_limit=None):
    order.validate()
    if order.type not in ('ATO', 'ATC'):
        raise ValueError('ORDER_UNSUPPORTED_IN_AUCTION')
    if quantity_limit is not None and (type(quantity_limit) is not int or quantity_limit < 0):
        raise ValueError('INVALID_AUCTION_MATCH_QUANTITY')
    matched = quantity if quantity_limit is None else min(quantity, quantity_limit)
    return Match(price, time, matched, bar_time) if matched else None
