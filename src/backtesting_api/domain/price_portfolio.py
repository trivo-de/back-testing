"""Track one position and exact price-times-quantity P&L without an account."""
from dataclasses import dataclass, replace
from decimal import Decimal
from .portfolio import decimal


@dataclass(frozen=True)
class PricePosition:
    """Keep the original basis and remaining quantity through partial closes."""
    position_id: str
    direction: str
    entry_price: Decimal
    initial_quantity: int
    remaining_quantity: int


class PriceBook:
    """Apply fills independently from signal generation and OHLC matching."""
    def __init__(self):
        """Start flat with zero realized points and no monetary balance."""
        self.position = None
        self.realized_pnl = Decimal(0)

    def open(self, position_id, direction, price, quantity):
        """Open a validated LONG or SHORT without adding to another position."""
        price = decimal(price)
        if self.position is not None or direction not in ('LONG', 'SHORT'):
            raise ValueError('INVALID_POSITION_ENTRY')
        if price <= 0 or type(quantity) is not int or quantity < 1:
            raise ValueError('INVALID_POSITION_FILL')
        self.position = PricePosition(position_id, direction, price, quantity, quantity)

    def close(self, price, quantity):
        """Realize only the closed quantity and retain the original entry basis."""
        price = decimal(price)
        position = self.position
        if (position is None or price <= 0 or type(quantity) is not int
                or not 1 <= quantity <= position.remaining_quantity):
            raise ValueError('INVALID_CLOSE_QUANTITY_OR_PRICE')
        sign = 1 if position.direction == 'LONG' else -1
        pnl = sign * (price - position.entry_price) * quantity
        self.realized_pnl += pnl
        remaining = position.remaining_quantity - quantity
        self.position = replace(position, remaining_quantity=remaining) if remaining else None
        return pnl

    def mark(self, price):
        """Combine cumulative realized legs with only the quantity still open."""
        price = decimal(price)
        if price <= 0:
            raise ValueError('INVALID_MARK_PRICE')
        position = self.position
        unrealized = (Decimal(0) if position is None else
                      (1 if position.direction == 'LONG' else -1) *
                      (price - position.entry_price) * position.remaining_quantity)
        return {'realized_pnl': self.realized_pnl, 'unrealized_pnl': unrealized,
                'total_pnl': self.realized_pnl + unrealized}
