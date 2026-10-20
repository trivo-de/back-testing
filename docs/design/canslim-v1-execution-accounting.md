# Thực thi và tính tiền hợp đồng

Chế độ tùy chọn [khớp theo phiên HNX](hnx-session-matching.md) bổ sung LO liên tục,
ATO mở và ATC đóng, tái sử dụng cùng cách tính tiền/phí/ký quỹ. Thứ tự `next_open` bên dưới vẫn
áp dụng cho mẫu CANSLIM hiện tại; không tự chuyển giờ thoát của mẫu sang ATC.

Luồng JSON hiện tại dùng `InlineExecution` → `ContractExecution` →
`ContractPortfolio`. Long/short, đóng từng phần, stop/target/trailing, sizing
tại Open, phí/thuế và ký quỹ đã được triển khai.

Với `sizing.pyramiding: true`, `InlineMultiExecution` dùng `ContractBook` cho
tiền chung và bộ thực thi riêng mỗi `position_id`. Giá vốn và phân bổ phí mở
thuộc từng lần mở; đóng `remaining` chỉ giảm phần đang xét. Cách tính phí và
lãi/lỗ từng phần tái sử dụng `ContractPortfolio`, rồi cộng về tài khoản chung.
Hạn mức hợp đồng tính cả đang giữ và mở đang chờ; ký quỹ tổng được kiểm tra
lại khi thực khớp. LO chốt lượng tại giá giới hạn; ATO dùng Close liên tục đã
hoàn tất trước 08:45. Chế độ này chỉ nhận LO/ATO mở với model HNX; thứ tự
Open/Close ở [tài liệu phiên](hnx-session-matching.md#1-bật-chế-độ).

Các giá trị 6/12 điểm, tối đa 5 hợp đồng, ký quỹ 17% và dự phòng 1,10 thuộc
[mẫu CANSLIM v1](../strategies/canslim-v1-rules.md). API lấy giá trị thực tế
từ JSON, theo [đặc tả API](backtest-api-specification.md); không tự thêm quy tắc
margin breach, giờ thoát hoặc time-stop nếu chưa khai báo biểu thức.

## 1. Thứ tự và giá khớp

1. Open: thực thi tín hiệu đang chờ từ Close trước.
2. Nếu còn vị thế, xét stop/trailing trước TP1 rồi TP2 trong nến.
3. Close: ghi tài khoản, đánh giá điều kiện thoát theo
   `exit.bar_close.priority`, hoặc điều kiện mở khi không có vị thế.
4. Tín hiệu sau Close chờ Open hợp lệ kế tiếp.

Stop/target được tạo ngay sau khớp Open và có thể bị chạm trong chính nến vào.
Không dùng High/Low/Close tương lai để tính quantity hoặc kiểm tra tiền mở lệnh.

| Tình huống | Giá khớp mô phỏng |
| --- | --- |
| Long: Open ≤ stop; short: Open ≥ stop | Open |
| Long: Low ≤ stop; short: High ≥ stop, không gap qua stop | Mức stop |
| Gap qua target hoặc chạm target | Mức target |
| Cùng nến chạm stop và target | Stop ưu tiên |
| Cùng nến chạm TP1 và TP2, kể cả bằng giá | TP1 trước, TP2 xử lý số lượng còn lại |

Tick mô phỏng là 0,1 điểm. Long stop làm tròn xuống, short stop lên;
long target lên, short target xuống. Giá fill không đúng tick bị từ chối
`FILL_OFF_TICK`. Mô hình hợp đồng hiện chỉ chạy dữ liệu giao dịch 5 phút
và `slippage_rate=0`.

Không mô phỏng lệnh chỉ khớp được một phần khối lượng do thanh khoản.
Đóng từng phần là hành động thoát theo quantity nguyên của vị thế.

## 2. Đóng từng phần và trailing

Mỗi lần đóng giảm quantity, phân bổ chi phí mở và ghi một trade cho phần đã
đóng. Target đã khớp không được xét lại. Đóng hết xóa trạng thái entry fill,
stop và cực trị trailing. Đây là trạng thái bộ thực thi, chưa có hệ thống
quản lý lệnh chờ với thao tác hủy/sửa lệnh độc lập.

Trailing kích hoạt sau TP1, khởi tạo ở giá TP1; không dùng High/Low của chính
nến TP1. Từ nến sau, cập nhật cực trị sau khi xử lý nến và chỉ áp dụng stop mới
ở nến kế tiếp. Long dùng stop cao hơn, short dùng stop thấp hơn; không nới stop.

Mẫu v1 tại cùng Close ưu tiên `MARGIN_BREACH` → `FORCED_EXIT` → `TIME_STOP`.
TP trong nến đã xử lý trước thời điểm Close. Thứ tự này được truyền trong JSON.

## 3. Sổ tiền và chi phí

Gọi `multiplier = accounting.contract_multiplier` và
`sign = +1` cho long, `-1` cho short:

```text
notional = price × multiplier × quantity
required_margin = mark × multiplier × open_quantity × margin_rate
unrealized_pnl = sign × (mark - entry_fill) × multiplier × open_quantity
equity = cash + unrealized_pnl
available_cash = equity - required_margin

tax_base = fill_price × multiplier × fill_quantity × margin_rate / 2
pit = tax_base × pit_rate
exchange_fee = exchange_fee_per_contract × fill_quantity
clearing_fee = clearing_fee_per_contract × fill_quantity
broker_fee = broker_fee_per_contract × fill_quantity
costs = pit + exchange_fee + clearing_fee + broker_fee
```

- Entry chỉ trừ chi phí mở, không trừ notional hoặc ký quỹ khỏi cash.
- Exit cộng P/L giá đã chốt rồi trừ chi phí thoát.
- `gross = sign × (exit-entry) × multiplier × exit_quantity`;
  `net = gross - allocated_entry_cost - exit_costs`.
- Phân bổ chi phí mở theo exit_quantity/initial_quantity, không vượt phần còn
  chưa phân bổ; lần đóng cuối nhận toàn bộ phần dư.
- Dùng Decimal, tiền làm tròn HALF_UP đến 1 VND. Từng khoản chi phí, P/L đã
  chốt, P/L chưa chốt và ký quỹ khi mark được làm tròn tại nơi hạch toán.
- Không có khoản chi phí dồn tích riêng hoặc quyết toán qua đêm theo DSP/FSP.

Thuế suất và các loại phí là tham số mô phỏng do bên gọi cung cấp.
Các mức trong mẫu không phải xác nhận mức thuế/phí thực tế cho mọi ngày lịch sử.
`contract_multiplier` mặc định 100.000; các tỷ lệ/phí còn lại phải gửi rõ.

## 4. Sizing và ký quỹ

```text
estimated_roundtrip_cost =
    costs(entry_price, 1) + costs(rounded_stop_price, 1)
risk_per_contract = stop_points × multiplier + estimated_roundtrip_cost
qty_risk = floor(cash_before_entry × risk_fraction / risk_per_contract)
qty_margin = floor(cash_before_entry /
                   (entry_price × multiplier × margin_rate × margin_buffer))
quantity = min(qty_risk, qty_margin, max_contracts)
```

Quantity < 1 bị từ chối. Trước khi ghi fill, kiểm tra
`cash_before_entry - open_costs >= required_margin_at_fill × margin_buffer`;
không đủ thì `INSUFFICIENT_MARGIN_AFTER_COSTS`. Bộ chạy chỉ mở khi không có vị thế.

Tại mỗi Close, mark dùng Close vừa hoàn tất. Điều kiện
`account.equity < account.required_margin` trong mẫu v1 tạo tín hiệu
`MARGIN_BREACH` cho Open kế tiếp. Không mô phỏng thanh lý giữa nến.
Thiếu nến thực thi bắt buộc, lỡ `flat_by` hoặc còn vị thế cuối kỳ khi
`allow_overnight=false` thì lượt chạy lỗi; không tự tạo giá đóng.

## 5. Kết quả và giới hạn kiểm chứng

Result giữ input/policy hash, cấu hình accounting, đơn vị, giả định, signal,
order, fill, từng phần đóng và equity/ký quỹ. Phí/thuế tách riêng trên mỗi fill.
Trade liên kết entry_fill_id/exit_fill_id; nhiều phần đóng cùng một position_id.
`open_position.strategy_details` giữ stop/cực trị trailing nếu còn vị thế.

`fill_time` dùng Open khi gap hoặc khớp thị trường, Close khi chạm trong nến;
`bar_time` là Open nến chứa fill. OHLC không cho biết giây chạm mức giá.
Đây là mốc ghi nhận mô phỏng, không phải thời gian khớp thực tế.

[Danh mục kiểm thử](../testing/vn30f1m/canslim-v1-test-cases.md) dẫn tới test
sổ tiền, execution, luồng JSON và lưu/đọc. Kiểm thử dùng dữ liệu tổng hợp;
nghiệm thu bộ dữ liệu thật sáu tháng chưa được xác nhận.
