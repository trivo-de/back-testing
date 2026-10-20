"""Yêu cầu lệnh bất biến và kết quả xử lý; không đọc giá hoặc sửa tài khoản."""
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal
from .market import BarTime

Side = Literal['BUY', 'SELL', 'LONG', 'SHORT', 'CLOSE']
OrderType = Literal['SIMULATED', 'LO', 'ATO', 'ATC']


@dataclass(frozen=True)
class OrderRequest:
    type: OrderType = 'SIMULATED'
    limit_price: Decimal | None = None
    max_execution_bars: int | None = None

    def validate(self):
        if self.type not in ('SIMULATED', 'LO', 'ATO', 'ATC'):
            raise ValueError('UNSUPPORTED_ORDER_TYPE')
        if self.type == 'LO':
            price = self.limit_price
            if not isinstance(price, Decimal) or not price.is_finite() or price <= 0 or price % Decimal('.1'):
                raise ValueError('LIMIT_PRICE_INVALID_OR_OFF_TICK')
        elif self.limit_price is not None:
            raise ValueError('LIMIT_PRICE_REQUIRES_LO')
        if self.max_execution_bars is not None and (
                type(self.max_execution_bars) is not int or self.max_execution_bars < 1):
            raise ValueError('INVALID_MAX_EXECUTION_BARS')

    @property
    def result_type(self):
        # Giữ nhãn kết quả cũ để chạy lại và đối chiếu lịch sử.
        return 'NEXT_OPEN' if self.type == 'SIMULATED' else self.type


@dataclass(frozen=True)
class OrderResult:
    """Kết quả một yêu cầu, kể cả bị từ chối hoặc còn chờ."""
    signal_date: BarTime
    side: Side
    status: Literal['FILLED', 'REJECTED', 'PENDING', 'CANCELED', 'EXPIRED']
    reason: str | None = None
    order_type: str | None = None
    quantity: int | None = None
    limit_price: Decimal | None = None
    events: tuple[dict, ...] = ()
    fill_index: int | None = None
    fill_indices: tuple[int, ...] = ()
    filled_quantity: int = 0
    expired_quantity: int = 0
    remaining_quantity: int | None = None
    position_id: str | None = None
