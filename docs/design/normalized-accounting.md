# Tính tiền normalized

`accounting.model: "normalized"` dùng `Portfolio` và
`InlineNormalizedExecution`. Đây là mô hình mua/bán theo đơn vị giá đầu vào;
quantity không được diễn giải thành số hợp đồng phái sinh.

Chiến lược khai báo trong JSON; bộ chạy không tự áp dụng một bộ CANSLIM cũ.
Cấu trúc theo [đặc tả API](backtest-api-specification.md).

## 1. Phạm vi

- Một vị thế mua; hướng mở BUY, hướng đóng SELL.
- Sizing `fixed_fractional`; chỉ thoát toàn bộ sau điều kiện Close, khớp tại
  Open kế tiếp. Không hỗ trợ stop/target trong nến hoặc đóng từng phần.
- Dữ liệu giao dịch hỗ trợ `"5"` và `"D"`; nến ngày phải khai báo thời điểm
  đóng/khả dụng. Không tự gộp dữ liệu trong ngày thành nến ngày.
- `initial_cash > 0`, `fee_rate >= 0`, `0 <= slippage_rate < 1`.

## 2. Khớp và số lượng

```text
buy_fill  = Open × (1 + slippage_rate)
sell_fill = Open × (1 - slippage_rate)

risk_per_unit = buy_fill × stop_loss_fraction
qty_risk = floor(cash_before_fill × risk_fraction / risk_per_unit)
qty_cash = floor(cash_before_fill / (buy_fill × (1 + fee_rate)))
quantity = min(qty_risk, qty_cash)
```

Tính số lượng tại Open thực thi, khi tài khoản đang không có vị thế.
Quantity < 1 hoặc không đủ tiền thì từ chối lệnh, vẫn giữ tín hiệu.
`stop_loss_fraction` chỉ phục vụ sizing, không tự tạo điều kiện cắt lỗ.

## 3. Sổ tiền

```text
buy_fee = quantity × buy_fill × fee_rate
cost_basis = quantity × buy_fill + buy_fee
cash_after_buy = cash_before_buy - cost_basis

market_value = quantity × Close
unrealized_pnl = market_value - cost_basis
equity = cash + market_value

sell_fee = quantity × sell_fill × fee_rate
net_proceeds = quantity × sell_fill - sell_fee
realized_pnl = net_proceeds - cost_basis
cash_after_sell = cash_before_sell + net_proceeds
```

Lãi/lỗ chưa chốt chưa trừ phí bán dự kiến. Sau SELL toàn bộ, vị thế bằng rỗng
và equity bằng cash. Không trừ tổng phí thêm lần nữa khỏi P/L đã bao gồm phí.
Các phép tính dùng Decimal; kết quả JSON giữ số thập phân bằng chuỗi.

[Ví dụ số và kiểm thử](../testing/normalized-accounting-test-cases.md) đối chiếu
các công thức này với `tests/test_execution_accounting.py`.
