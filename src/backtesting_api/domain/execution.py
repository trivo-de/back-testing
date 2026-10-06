from dataclasses import dataclass, replace
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
from .portfolio import Portfolio, decimal
from .contract_accounting import ContractPortfolio, Costs
from .trading import Fill, FixedSignal, Trade
from .market import BarTime


class InvalidExecution(ValueError):
    """Abort a run when a required execution event cannot be simulated faithfully."""


@dataclass(frozen=True)
class BuyContext:
    cash: Decimal
    fill_price: Decimal
    fee_rate: Decimal


class NormalizedExecution:
    """Preserve v0 calculations and event ordering."""
    def __init__(self, initial_cash, fee_rate, slippage_rate, size_buy=None):
        self.portfolio = Portfolio.open(initial_cash)
        self.fee_rate = fee_rate
        self.slippage_rate = slippage_rate
        self.size_buy = size_buy
        self.entry_fill = None

    def validate(self, signal):
        position = self.portfolio.position
        if signal.side not in ('BUY', 'SELL'):
            raise ValueError('signal side must be BUY or SELL')
        if signal.side == 'BUY' and position is not None:
            raise ValueError('BUY signal requires a flat portfolio')
        if signal.side == 'SELL' and position is None:
            raise ValueError('SELL signal requires an open position')
        if signal.side == 'SELL' and signal.quantity is not None:
            if type(signal.quantity) is not int or signal.quantity != position.quantity:
                raise ValueError('partial SELL is unsupported; exit the full position')

    def close_signal(self, reason):
        return FixedSignal('SELL', reason=reason)

    def execute(self, signal, signal_date, fill_date, raw_open):
        portfolio = self.portfolio
        price = raw_open * (1 + self.slippage_rate) if signal.side == 'BUY' else raw_open * (1 - self.slippage_rate)
        quantity = signal.quantity
        if signal.side == 'SELL':
            quantity = portfolio.position.quantity
        elif quantity is None:
            if self.size_buy is None:
                raise ValueError('BUY requires quantity or a sizing policy')
            quantity = self.size_buy(BuyContext(portfolio.cash, price, self.fee_rate))
        updated = portfolio.buy(quantity, price, self.fee_rate) if signal.side == 'BUY' else portfolio.sell(price, self.fee_rate)
        fill = Fill(signal_date, fill_date, signal.side, price, quantity, updated.fees - portfolio.fees)
        trade = None
        if signal.side == 'BUY':
            self.entry_fill = fill
        else:
            entry = self.entry_fill
            assert entry is not None
            trade = Trade(entry.fill_date, fill_date, quantity, entry.price, price,
                          entry.fee + fill.fee, updated.realized_pnl - portfolio.realized_pnl)
            self.entry_fill = None
        self.portfolio = updated
        return fill, trade

    def intrabar(self, bar):
        return ()


@dataclass(frozen=True)
class ContractFill(Fill):
    costs: Costs
    direction: str
    bar_time: BarTime | None = None


@dataclass(frozen=True)
class ContractTrade(Trade):
    direction: str
    allocated_entry_cost: Decimal


@dataclass(frozen=True)
class Bracket:
    """Measure stop/target distances from the actual fill; quantity=None closes the remainder."""
    stop_distance: Decimal
    targets: tuple[tuple[Decimal, int | None], ...] = ()
    trailing_distance: Decimal | None = None

    def __post_init__(self):
        object.__setattr__(self, 'stop_distance', decimal(self.stop_distance))
        object.__setattr__(self, 'targets', tuple((decimal(d), q) for d, q in self.targets))
        if self.trailing_distance is not None:
            object.__setattr__(self, 'trailing_distance', decimal(self.trailing_distance))
        if (self.stop_distance <= 0 or any(d <= 0 or (q is not None and (type(q) is not int or q < 1)) for d, q in self.targets)
                or any(a[0] > b[0] for a, b in zip(self.targets, self.targets[1:]))
                or any(q is None for _, q in self.targets[:-1])
                or (self.trailing_distance is not None and (self.trailing_distance <= 0 or not self.targets))):
            raise ValueError('INVALID_BRACKET')


class ContractExecution:
    def __init__(self, initial_cash, accounting, *, margin_buffer=Decimal('1.1'),
                 max_contracts=5, bracket=None):
        self.portfolio = ContractPortfolio.open(initial_cash, accounting)
        self.margin_buffer = decimal(margin_buffer)
        self.max_contracts = max_contracts
        if self.margin_buffer < 1 or type(max_contracts) is not int or max_contracts < 1:
            raise ValueError('INVALID_EXECUTION_LIMITS')
        self.bracket = bracket
        self.entry_fill = None
        self.active_stop = None
        self.target_index = 0
        self.extreme = None

    def validate(self, signal):
        p = self.portfolio.position
        if signal.side not in ('LONG', 'SHORT', 'CLOSE'):
            raise ValueError('signal side must be LONG, SHORT or CLOSE')
        if signal.side in ('LONG', 'SHORT') and p is not None:
            raise ValueError('ENTRY_REQUIRES_FLAT_PORTFOLIO')
        if signal.side == 'CLOSE' and p is None:
            raise ValueError('EXIT_REQUIRES_POSITION')
        if signal.quantity is not None and (type(signal.quantity) is not int or signal.quantity < 1
                or (signal.side == 'CLOSE' and signal.quantity > p.quantity)):
            raise ValueError('INVALID_QUANTITY')

    def close_signal(self, reason):
        return FixedSignal('CLOSE', reason=reason)

    @staticmethod
    def level(price, upward):
        return (price / Decimal('.1')).to_integral_value(
            rounding=ROUND_CEILING if upward else ROUND_FLOOR) * Decimal('.1')

    def execute(self, signal, signal_date, fill_date, raw_open):
        self.validate(signal)
        price = decimal(raw_open)
        if price != self.level(price, True): raise ValueError('FILL_OFF_TICK')
        p = self.portfolio.position
        if signal.side != 'CLOSE':
            if self.bracket:
                if (any(d >= price for d, _ in self.bracket.targets) and signal.side == 'SHORT') or (
                        signal.side == 'LONG' and self.bracket.stop_distance >= price):
                    raise ValueError('NONPOSITIVE_BRACKET_LEVEL')
                if signal.quantity is not None and sum(q or 0 for _, q in self.bracket.targets) > signal.quantity:
                    raise ValueError('TARGET_QUANTITY_EXCEEDS_POSITION')
            updated, costs = self.portfolio.enter(signal.side, signal.quantity, price,
                            margin_buffer=self.margin_buffer, max_contracts=self.max_contracts)
            fill = ContractFill(signal_date, fill_date, signal.side, price, signal.quantity, costs.total, costs, signal.side, fill_date)
            self.entry_fill = fill
            self.target_index, self.extreme = 0, None
            self.active_stop = (self.level(price - updated.position.sign * self.bracket.stop_distance,
                                          signal.side == 'SHORT') if self.bracket else None)
            trade = None
        else:
            quantity = p.quantity if signal.quantity is None else signal.quantity
            updated, costs, allocated, net = self.portfolio.exit(quantity, price)
            fill = ContractFill(signal_date, fill_date, signal.side, price, quantity, costs.total, costs, p.direction, fill_date)
            trade = ContractTrade(self.entry_fill.fill_date, fill_date, quantity, p.entry_price, price,
                                  allocated + costs.total, net, p.direction, allocated)
            if updated.position is None:
                self.entry_fill, self.active_stop, self.extreme = None, None, None
        self.portfolio = updated
        return fill, trade

    def intrabar(self, bar):
        p = self.portfolio.position
        if p is None or self.bracket is None: return ()
        if not hasattr(bar, 'high') or not hasattr(bar, 'low'):
            raise ValueError('BRACKET_REQUIRES_OHLC')
        high, low, opened = map(decimal, (bar.high, bar.low, bar.open))
        if not 0 < low <= min(opened, decimal(bar.close)) <= max(opened, decimal(bar.close)) <= high:
            raise ValueError('INVALID_OHLC')
        events = []
        stop_hit = low <= self.active_stop if p.sign == 1 else high >= self.active_stop
        if stop_hit:
            gap = opened <= self.active_stop if p.sign == 1 else opened >= self.active_stop
            price = opened if gap else self.active_stop
            initial_stop = self.level(p.entry_price - p.sign * self.bracket.stop_distance, p.sign == -1)
            reason = 'TRAILING_STOP' if self.active_stop != initial_stop else 'STOP_LOSS'
            signal = self.close_signal(reason)
            created = self.entry_fill.fill_date
            fill, trade = self.execute(signal, created, bar.trading_date if gap else bar.closed_at, price)
            return ((signal, replace(fill, bar_time=bar.trading_date), trade),)
        trailing_was_active = self.extreme is not None
        while self.target_index < len(self.bracket.targets) and self.portfolio.position is not None:
            distance, quantity = self.bracket.targets[self.target_index]
            target = self.level(p.entry_price + p.sign * distance, p.sign == 1)
            if not (high >= target if p.sign == 1 else low <= target): break
            quantity = min(quantity, self.portfolio.position.quantity) if quantity is not None else None
            signal = FixedSignal('CLOSE', quantity, reason=f'TP{self.target_index + 1}')
            gap = opened >= target if p.sign == 1 else opened <= target
            fill, trade = self.execute(signal, self.entry_fill.fill_date,
                                       bar.trading_date if gap else bar.closed_at, target)
            events.append((signal, replace(fill, bar_time=bar.trading_date), trade))
            self.target_index += 1
            if self.target_index == 1 and self.portfolio.position and self.bracket.trailing_distance is not None:
                self.extreme = target
        if self.portfolio.position is not None and self.extreme is not None:
            # Seed the first TP with its target price, excluding that bar's High/Low.
            if trailing_was_active:
                self.extreme = max(self.extreme, high) if p.sign == 1 else min(self.extreme, low)
            candidate = self.level(self.extreme - p.sign * self.bracket.trailing_distance, p.sign == -1)
            # Update after processing this bar; the new stop takes effect on the next bar.
            self.active_stop = max(self.active_stop, candidate) if p.sign == 1 else min(self.active_stop, candidate)
        return tuple(events)
