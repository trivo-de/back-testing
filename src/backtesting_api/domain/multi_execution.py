"""Apply existing per-position execution rules to a shared contract account."""

from dataclasses import dataclass, replace

from .contract_accounting import ContractBook


# Expose one lot through the shared book's portfolio interface.
@dataclass(frozen=True)
class LotAccount:
    book: ContractBook
    position_id: str

    # Return the cash shared by all lots.
    @property
    def cash(self):
        return self.book.cash

    # Return the book's contract accounting parameters.
    @property
    def accounting(self):
        return self.book.accounting

    # Return the position belonging to this lot.
    @property
    def position(self):
        return self.book.lot(self.position_id)

    # Return accumulated fees across the shared book.
    @property
    def fees(self):
        return self.book.fees

    # Return realized profit across the shared book.
    @property
    def realized_pnl(self):
        return self.book.realized_pnl

    # Mark the shared book at the supplied price.
    def mark(self, price):
        return self.book.mark(price)

    # Apply a lot entry and return the updated account with its costs.
    def enter(self, direction, quantity, price, **limits):
        book, costs = self.book.enter(self.position_id, direction, quantity, price, **limits)
        return replace(self, book=book), costs

    # Apply a lot exit and return its updated account and profit allocation.
    def exit(self, quantity, price):
        book, costs, allocated, net = self.book.exit(self.position_id, quantity, price)
        return replace(self, book=book), costs, allocated, net


# Coordinate per-lot executors against a shared contract book.
class MultiContractExecution:
    # Create the shared book and retain the supplied per-lot executor factory.
    def __init__(self, initial_cash, execution_factory):
        self.initial_cash = initial_cash
        self.execution_factory = execution_factory
        template = execution_factory(initial_cash)
        self.portfolio = ContractBook.open(initial_cash, template.portfolio.accounting)
        self.max_contracts = template.max_contracts
        self.lots = {}
        self.current_open = None

    # Select or create the executor for a validated position identifier.
    def _executor(self, signal, *, continuation=False):
        key = signal.position_id
        if not isinstance(key, str) or not key:
            raise ValueError('INVALID_POSITION_ID')
        if signal.side == 'CLOSE':
            if self.portfolio.lot(key) is None:
                raise ValueError('EXIT_REQUIRES_POSITION')
            executor = self.lots[key]
        else:
            if key in self.lots and not continuation:
                raise ValueError('INVALID_POSITION_ID')
            if signal.order.type not in ('LO', 'ATO', 'MTL', 'MOK', 'MAK'):
                raise ValueError('MULTI_ENTRY_REQUIRES_LO_OR_ATO')
            if any(p.direction != signal.side for _, p in self.portfolio.positions):
                raise ValueError('OPPOSITE_POSITION_EXISTS')
            if continuation and key not in self.lots:
                raise ValueError('ENTRY_CONTINUATION_EXCEEDS_ORDER')
            executor = self.lots[key] if continuation else self.execution_factory(self.initial_cash)
            if not continuation and self.current_open is not None and hasattr(executor, 'before_open'):
                executor.before_open(self.current_open)
        executor.portfolio = LotAccount(self.portfolio, key)
        return executor

    # Validate the signal with its selected lot executor.
    def validate(self, signal):
        self._executor(signal).validate(signal)

    # Prepare a lot order while enforcing pending-order and shared sizing limits.
    def prepare_order(self, signal, reference_price=None, *, pending=()):
        executor = self._executor(signal)
        executor.validate(signal)
        if any(waiting.position_id == signal.position_id for waiting in pending):
            raise ValueError('POSITION_ORDER_PENDING')
        if signal.side != 'CLOSE':
            opening = [waiting for waiting in pending if waiting.side != 'CLOSE']
            if any(waiting.side != signal.side for waiting in opening):
                raise ValueError('OPPOSITE_ORDER_PENDING')
            if any(type(waiting.quantity) is not int or waiting.quantity < 1 for waiting in opening):
                raise ValueError('PENDING_ENTRY_QUANTITY_REQUIRED')
            capacity = self.max_contracts - self.portfolio.quantity - sum(waiting.quantity for waiting in opening)
            if capacity < 1:
                raise ValueError('MAX_CONTRACTS_RESERVED')
        if hasattr(executor, 'prepare_order'):
            signal = executor.prepare_order(signal, reference_price)
        if signal.side == 'CLOSE' and signal.quantity is None:
            signal = replace(signal, quantity=executor.portfolio.position.quantity)
        if type(signal.quantity) is not int or signal.quantity < 1:
            raise ValueError('ORDER_QUANTITY_REQUIRED')
        signal = replace(signal, requested_quantity=signal.requested_quantity or signal.quantity)
        if signal.side != 'CLOSE':
            signal = replace(signal, quantity=min(signal.quantity, capacity))
        executor.validate(signal)
        return signal

    # Advance existing lot executors before the next candle opens.
    def before_open(self, stamp):
        for key, executor in self.lots.items():
            executor.portfolio = LotAccount(self.portfolio, key)
            if hasattr(executor, 'before_open'):
                executor.before_open(stamp)
        self.current_open = stamp

    # Execute a lot fill and synchronize the resulting shared book.
    def execute(self, signal, signal_date, fill_date, price, *, continuation=False, order_quantity=None):
        executor = self._executor(signal, continuation=continuation)
        fill, trade = executor.execute(signal, signal_date, fill_date, price,
                                      continuation=continuation, order_quantity=order_quantity)
        self.portfolio = executor.portfolio.book
        self.lots[signal.position_id] = executor
        return (replace(fill, position_id=signal.position_id),
                replace(trade, position_id=signal.position_id) if trade is not None else None)

    # Apply intrabar protection for each lot and synchronize shared accounting.
    def intrabar(self, bar, *, intrabar_entries=(), phase=None):
        events = []
        for key, executor in self.lots.items():
            executor.portfolio = LotAccount(self.portfolio, key)
            for signal, fill, trade in executor.intrabar(bar, entry_intrabar=key in intrabar_entries, phase=phase):
                events.append((replace(signal, position_id=key), replace(fill, position_id=key),
                               replace(trade, position_id=key)))
            self.portfolio = executor.portfolio.book
        return tuple(events)
