from dataclasses import dataclass, replace
from decimal import Decimal, ROUND_HALF_UP
from .portfolio import decimal


def money(value):
    return decimal(value).quantize(Decimal('1'), rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class Costs:
    exchange_fee: Decimal
    clearing_fee: Decimal
    broker_fee: Decimal
    pit: Decimal

    @property
    def total(self):
        return self.exchange_fee + self.clearing_fee + self.broker_fee + self.pit


@dataclass(frozen=True)
class ContractAccounting:
    margin_rate: Decimal
    pit_rate: Decimal
    exchange_fee_per_contract: Decimal
    clearing_fee_per_contract: Decimal
    broker_fee_per_contract: Decimal
    contract_multiplier: Decimal = Decimal('100000')

    def __post_init__(self):
        for name in self.__dataclass_fields__:
            object.__setattr__(self, name, decimal(getattr(self, name)))
        if (self.contract_multiplier <= 0 or not 0 < self.margin_rate <= 1
                or not 0 <= self.pit_rate <= 1 or min(self.exchange_fee_per_contract,
                    self.clearing_fee_per_contract, self.broker_fee_per_contract) < 0):
            raise ValueError('INVALID_CONTRACT_ACCOUNTING')

    def costs(self, price, quantity):
        check_fill(price, quantity)
        return Costs(*(money(rate * quantity) for rate in (self.exchange_fee_per_contract,
                     self.clearing_fee_per_contract, self.broker_fee_per_contract)),
                     money(decimal(price) * self.contract_multiplier * quantity * self.margin_rate / 2 * self.pit_rate))


def check_fill(price, quantity):
    if decimal(price) <= 0 or type(quantity) is not int or quantity < 1:
        raise ValueError('INVALID_FILL_PRICE_OR_QUANTITY')


@dataclass(frozen=True)
class ContractPosition:
    direction: str
    quantity: int
    initial_quantity: int
    entry_price: Decimal
    entry_cost: Decimal
    remaining_entry_cost: Decimal

    @property
    def sign(self):
        return 1 if self.direction == 'LONG' else -1


@dataclass(frozen=True)
class ContractSnapshot:
    cash: Decimal
    quantity: int
    unrealized_pnl: Decimal
    equity: Decimal
    required_margin: Decimal
    available_cash: Decimal


@dataclass(frozen=True)
class ContractPortfolio:
    cash: Decimal
    accounting: ContractAccounting
    position: ContractPosition | None = None
    realized_pnl: Decimal = Decimal('0')
    fees: Decimal = Decimal('0')

    @classmethod
    def open(cls, initial_cash, accounting):
        cash = decimal(initial_cash)
        if cash <= 0: raise ValueError('initial_cash must be > 0')
        return cls(cash, accounting)

    def enter(self, direction, quantity, price, *, margin_buffer=Decimal('1.1'), max_contracts=5):
        check_fill(price, quantity)
        price, buffer = decimal(price), decimal(margin_buffer)
        if direction not in ('LONG', 'SHORT') or self.position is not None:
            raise ValueError('ENTRY_REQUIRES_DIRECTION_AND_FLAT_PORTFOLIO')
        if type(max_contracts) is not int or max_contracts < 1 or quantity > max_contracts or buffer < 1:
            raise ValueError('INVALID_QUANTITY_OR_MARGIN_BUFFER')
        costs = self.accounting.costs(price, quantity)
        required = price * quantity * self.accounting.contract_multiplier * self.accounting.margin_rate
        if self.cash - costs.total < required * buffer:
            raise ValueError('INSUFFICIENT_MARGIN_AFTER_COSTS')
        position = ContractPosition(direction, quantity, quantity, price, costs.total, costs.total)
        return replace(self, cash=self.cash - costs.total, position=position, fees=self.fees + costs.total), costs

    def exit(self, quantity, price):
        check_fill(price, quantity)
        p = self.position
        if p is None or quantity > p.quantity: raise ValueError('INVALID_EXIT_QUANTITY')
        costs = self.accounting.costs(price, quantity)
        allocated = (p.remaining_entry_cost if quantity == p.quantity else
                     min(p.remaining_entry_cost, money(p.entry_cost * quantity / p.initial_quantity)))
        gross = money(p.sign * (decimal(price) - p.entry_price) * self.accounting.contract_multiplier * quantity)
        net = gross - allocated - costs.total
        position = None if quantity == p.quantity else replace(
            p, quantity=p.quantity - quantity, remaining_entry_cost=p.remaining_entry_cost - allocated)
        return (replace(self, cash=self.cash + gross - costs.total, position=position,
                        realized_pnl=self.realized_pnl + net, fees=self.fees + costs.total), costs, allocated, net)

    def mark(self, price):
        price = decimal(price)
        if price <= 0: raise ValueError('mark must be > 0')
        p, multiplier = self.position, self.accounting.contract_multiplier
        unrealized = money(p.sign * (price - p.entry_price) * multiplier * p.quantity) if p else Decimal('0')
        margin = money(price * multiplier * p.quantity * self.accounting.margin_rate) if p else Decimal('0')
        equity = self.cash + unrealized
        return ContractSnapshot(self.cash, p.quantity if p else 0, unrealized, equity, margin, equity - margin)
