# Thực thi và tính tiền hợp đồng

[Khớp theo phiên HNX](hnx-session-matching.md) dùng cùng công thức tiền, phí và ký quỹ. Mẫu CANSLIM hiện tại dùng thứ tự `next_open` bên dưới.

Luồng JSON hiện tại dùng `InlineExecution` → `ContractExecution` →
`ContractPortfolio`. Long/short, đóng từng phần, stop/target/trailing, sizing
tại Open, phí/thuế và ký quỹ đã được triển khai.

- `sizing.pyramiding: true`: `InlineMultiExecution` dùng `ContractBook` cho tài khoản chung và bộ thực thi riêng từng `position_id`.
- Giá vốn, phí mở và lượng đóng `remaining` thuộc từng phần. `ContractPortfolio` tính phí/P&L rồi cộng vào tài khoản.
- Hạn mức gồm đang giữ và mở đang chờ; kiểm tra lại tổng ký quỹ khi khớp.
- LO chốt lượng theo giá giới hạn; ATO dùng Close liên tục trước 08:45.
- Chế độ HNX nhận LO/ATO và loại thị trường ở mục 6. Thứ tự tại [tài liệu phiên](hnx-session-matching.md#1-bật-chế-độ).

Tham số mẫu: stop/TP1 6 điểm, TP2 12 điểm, tối đa 5 hợp đồng, ký quỹ 17%, dự phòng 1,10. Xem [CANSLIM v1](../strategies/canslim-v1-rules.md). API dùng tham số và biểu thức trong JSON theo [đặc tả API](backtest-api-specification.md).

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

TP1/TP2 đóng từng phần theo lượng nguyên của vị thế. Giới hạn lượng khớp theo lệnh được mô tả riêng trong [khớp theo phiên](hnx-session-matching.md).

## 2. Đóng từng phần và trailing

- Mỗi lần đóng giảm lượng, phân bổ phí mở và ghi một trade. Target đã khớp được đánh dấu hoàn tất.
- Đóng hết xóa trạng thái entry fill, stop và cực trị trailing.

1. TP1 khớp: kích hoạt trailing, lấy giá TP1 làm mốc.
2. Từ nến sau TP1: cập nhật cực trị sau khi xử lý nến.
3. Stop mới có hiệu lực ở nến kế tiếp; chỉ siết chặt theo hướng vị thế.

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

Thuế và phí là tham số mô phỏng của bên gọi. `contract_multiplier` mặc định 100.000; các tỷ lệ và phí còn lại cần khai báo rõ.

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

- Tại mỗi Close, mark dùng Close vừa hoàn tất.
- Điều kiện `account.equity < account.required_margin` trong mẫu v1 tạo tín hiệu `MARGIN_BREACH` cho Open kế tiếp.
- Không mô phỏng thanh lý giữa nến.
- Thiếu nến thực thi bắt buộc, lỡ `flat_by` hoặc còn vị thế cuối kỳ khi `allow_overnight=false` thì lượt chạy lỗi; không tự tạo giá đóng.

## 5. Kết quả và giới hạn kiểm chứng

- Result giữ input/policy hash, cấu hình accounting, đơn vị, giả định, signal, order, fill, từng phần đóng và equity/ký quỹ.
- Phí/thuế tách riêng trên mỗi fill.
- Trade liên kết entry_fill_id/exit_fill_id; nhiều phần đóng cùng một position_id.
- `open_position.strategy_details` giữ stop/cực trị trailing nếu còn vị thế.

`fill_time` dùng Open khi gap hoặc khớp thị trường, Close khi chạm trong nến;
`bar_time` là Open nến chứa fill. OHLC không cho biết giây chạm mức giá.
Đây là mốc ghi nhận mô phỏng, không phải thời gian khớp thực tế.

[Danh mục kiểm thử](../testing/vn30f1m/canslim-v1-test-cases.md) dẫn tới test
sổ tiền, execution, luồng JSON và lưu/đọc. Kiểm thử dùng dữ liệu tổng hợp;
nghiệm thu bộ dữ liệu thật sáu tháng chưa được xác nhận.

## 6. Hợp đồng kế toán MTL/MOK/MAK

Chốt ngày 20/10/2026 cho phần mở rộng [mục 7 khớp theo phiên](hnx-session-matching.md#7-đặc-tả-mtlmokmak--a01).
Các công thức tiền/phí/làm tròn ở mục 3–4 giữ nguyên. Phần mở rộng đã được
triển khai với lượng đối ứng cố định cho contract/HNX; không đổi mẫu CANSLIM v1.

- Sizing MTL/MOK/MAK dùng Close liên tục vừa khả dụng làm giá dự kiến. Lưu giá, thời điểm, lượng mong muốn và lượng nhận sau hạn mức.
- Giữ chỗ theo lượng nhận đặt; đang giữ cộng mở đang chờ tối đa `max_contracts`.
- Lệnh đóng lấy lượng từ `position_id` đang xét, tối đa lượng còn lại. LONG đóng bằng SELL; SHORT đóng bằng BUY.
- Trước fill mở, `ContractBook` kiểm tra tiền/vốn và tổng ký quỹ sau phí, gồm phần mới với `margin_buffer`.
- Thiếu tiền: từ chối toàn bộ lượng định khớp với `INSUFFICIENT_MARGIN_AFTER_COSTS`, kết thúc dư và giữ ngân sách. Fill đã nhận trước đó giữ nguyên.
- MOK chỉ khớp khi đủ cả lượng nhận đặt và tiền; thiếu điều kiện thì hủy.
- MAK/MTL ghi tiền và phí theo lượng thực khớp. Hủy hoặc chuyển dư chỉ thay trạng thái lệnh.
- MTL và LO dư dùng chung yêu cầu gốc, lượng nhận đặt và phần vị thế.
- Mỗi fill chuyển lượng chờ thành lượng giữ; kết thúc dư giải phóng lượng giữ chỗ.

- Các fill **của cùng lệnh**, trước lần đóng đầu tiên, dùng chung `position_id`, giá vốn bình quân theo lượng và tổng phí mở thực tế.
- Các lệnh/nhánh giữ giá vốn riêng. Thời gian giữ, giá neo stop/TP, trailing và thông tin chiến lược lấy từ fill đầu.
- `position.entry_price` là giá vốn bình quân; bảo vệ giữ giá neo fill đầu.
- TP tính lượng theo lượng nhận đặt, đóng tối đa lượng đang giữ.
- Bảo vệ hoặc lệnh đóng thay đổi vị thế: hủy mở dư cùng lệnh.
- Bộ đếm ngày tăng tại fill mở đầu tiên.
- Kiểm thử tại [hồ sơ MTL/MOK/MAK](../testing/market-orders-partial-matching.md).
