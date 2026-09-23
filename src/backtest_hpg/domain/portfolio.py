"""Immutable cash, position, fee, and P/L accounting."""

from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal

# Numeric normalization
def decimal(value: Decimal | int | str) -> Decimal:
    """Convert supported numeric input to a finite Decimal."""

    result = Decimal(str(value))
    if not result.is_finite():
        raise ValueError("value must be finite")
    return result

@dataclass(frozen=True)
class Position:
    """One long position with its entry cost; strategy state lives elsewhere."""

    quantity: int
    entry_price: Decimal
    entry_fee: Decimal

    @property
    def cost_basis(self) -> Decimal:
        # Return entry value including the entry fee.
        return self.entry_price * self.quantity + self.entry_fee

@dataclass(frozen=True)
class PortfolioSnapshot:
    """Mark-to-market portfolio values at one daily Close."""

    cash: Decimal
    quantity: int
    market_value: Decimal
    unrealized_pnl: Decimal
    equity: Decimal

@dataclass(frozen=True)
class Portfolio:
    """Immutable single-position ledger used by the execution engine."""

    cash: Decimal
    position: Position | None = None
    realized_pnl: Decimal = Decimal("0")
    fees: Decimal = Decimal("0")

    @classmethod
    def open(cls, initial_cash: Decimal | int | str) -> Portfolio:
        """Create an empty portfolio with validated positive cash."""

        cash = decimal(initial_cash)
        if cash <= Decimal("0"):
            raise ValueError("initial_cash must be > 0")
        return cls(cash=cash)

    def buy(
        self,
        quantity: int,
        fill_price: Decimal | int | str,
        fee_rate: Decimal | int | str,
    ) -> Portfolio:
        """Apply one full BUY fill and return the updated portfolio."""

        if self.position is not None:
            raise ValueError("cannot buy while holding a position")
        if type(quantity) is not int or quantity < 1:
            raise ValueError("quantity must be a positive integer")
        price, rate = decimal(fill_price), decimal(fee_rate)
        if price <= Decimal("0") or rate < Decimal("0"):
            raise ValueError("fill_price must be > 0 and fee_rate must be >= 0")
        fee = price * quantity * rate
        cost = price * quantity + fee
        if cost > self.cash:
            raise ValueError("insufficient cash")
        return Portfolio(self.cash - cost, Position(quantity, price, fee), self.realized_pnl, self.fees + fee)

    def sell(self, fill_price: Decimal | int | str, fee_rate: Decimal | int | str) -> Portfolio:
        """Close the current position and realize P/L after fees."""

        if self.position is None:
            raise ValueError("cannot sell without a position")
        price, rate = decimal(fill_price), decimal(fee_rate)
        if price <= Decimal("0") or rate < Decimal("0"):
            raise ValueError("fill_price must be > 0 and fee_rate must be >= 0")
        fee = price * self.position.quantity * rate
        proceeds = price * self.position.quantity - fee
        pnl = proceeds - self.position.cost_basis
        return Portfolio(self.cash + proceeds, None, self.realized_pnl + pnl, self.fees + fee)

    def mark(self, close: Decimal | int | str) -> PortfolioSnapshot:
        """Value cash and any open position at the supplied Close."""

        price = decimal(close)
        if price <= Decimal("0"):
            raise ValueError("close must be > 0")
        if self.position is None:
            return PortfolioSnapshot(self.cash, 0, Decimal("0"), Decimal("0"), self.cash)
        market_value = price * self.position.quantity
        unrealized = market_value - self.position.cost_basis
        return PortfolioSnapshot(
            self.cash,
            self.position.quantity,
            market_value,
            unrealized,
            self.cash + market_value,
        )
