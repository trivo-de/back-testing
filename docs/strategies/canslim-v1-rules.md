# CANSLIM v1 — Rule giao dịch phái sinh

Cập nhật: 25/09/2026. Strategy ID: `canslim_breakout_v1`.
Trạng thái 29/09: đã triển khai bằng cây JSON ở U08, kiểm thử dữ liệu tổng hợp;
chưa nghiệm thu bộ dữ liệu thật sáu tháng (U09). Tên v1 là nhãn mẫu, API mới không cần ID.
Nội dung được chuyển từ quyết định user cung cấp trong `canslim-decisions.md`.
Chỉ dùng các giá trị được ghi rõ trong tài liệu; không tự suy ra default khác.
Tài liệu này không thay [rule v0](canslim-rules.md), config hoặc run lịch sử.

Tài liệu liên quan:

- [Data contract v1](../data/vn30f1m/data-contract-v1.md).
- [Execution và accounting v1](../design/canslim-v1-execution-accounting.md).
- [Ví dụ nghiệm thu v1](../testing/vn30f1m/canslim-v1-test-cases.md).

## 1. Phạm vi

- VN30F1M, nến 5 phút, long và short; không giữ qua đêm, được giữ qua nghỉ trưa.
- Một lần entry tạo quantity 1–5; tổng tối đa 5 hợp đồng, không thêm vào vị thế.
- Có partial exit, không partial fill; không đóng một hướng rồi mở hướng ngược
  lại trong cùng nến. Không vào lại cùng hướng trong nến vừa exit; chỉ xét tín hiệu mới từ Close của nến kế tiếp.
- Bộ indicator mới thay bộ v0. Cấu trúc strategy là xu hướng → breakout →
  xác nhận động lượng/dòng tiền → quản trị rủi ro; không dùng hệ thống bỏ phiếu.
- Thiếu warm-up/required indicator: UNEVALUABLE, không tạo entry.

## 2. Indicator

SMA20, EMA5, BB, MACD và MFI14 dùng OHLCV 5 phút VNINDEX trong market_data.
Chỉ dùng nến đã đóng và khả dụng; warm-up tối thiểu 150 nến VNINDEX tính cả t.
Chuỗi chỉ báo VNINDEX không khởi tạo lại khi hợp đồng giao dịch chuyển kỳ.
Mức chốt lời tính trực tiếp từ giá khớp hợp đồng như mục 5.

| Indicator | Input                    | Công thức/window đã chốt                                 |
| --------- | ------------------------ | ------------------------------------------------------------- |
| SMA20     | Close 5m                 | Trung bình 20 mẫu                                           |
| EMA5      | Close 5m                 | EMA chu kỳ 5                                                 |
| BB(20,2)  | Close 5m                 | Middle=SMA20; Upper=SMA20+2×sigma20; Lower=SMA20−2×sigma20 |
| MACD Line | Close 5m                 | EMA12−EMA26                                                  |
| Histogram | MACD Line                | Bằng chính MACD Line theo định nghĩa v1                  |
| MFI14     | High/Low/Close/Volume 5m | Chu kỳ 14                                                    |

`EMA[t] = input[t] × alpha + EMA[t-1] × (1-alpha)`, `alpha = 2/(N+1)`.
150 nến là lịch sử khởi tạo, không thay chu kỳ EMA5/12/26 thành EMA150.
Không dùng Signal Line trong entry.

### Quy ước tính

- Seed EMA và điểm bắt đầu recurrence: với EMA N, seed bằng SMA của N Close đầu tiên trong history VNINDEX; recurrence bắt đầu từ bar N+1.
- Điều kiện đủ 150 mẫu tại decision đầu tiên, tính cả/không tính t: cần ít nhất 150 bar VNINDEX đã đóng, tính cả bar t.
- BB sigma chia N hay N−1: chia N (`ddof=0`) để kết quả cố định và gần cách tính phổ biến trên nền tảng giao dịch.
- Công thức chi tiết MFI/typical price/money flow: `TP=(H+L+C)/3`; `RawFlow=TP×Volume`; cộng RawFlow dương/âm trong 14 kỳ theo dấu thay đổi TP; `MFI=100-100/(1+Positive/Negative)`.
- MFI khi typical price bằng nhau: RawFlow của bar đó không cộng vào dòng dương hoặc âm.
- MFI khi negative flow hoặc cả hai dòng bằng 0: Negative=0 và Positive>0 → MFI=100; Positive=0 và Negative>0 → MFI=0; cả hai=0 → MFI=50.
- Signal Line nếu cần xuất để hiển thị: `EMA9(MACD_Line)`, seed bằng SMA 9 giá trị MACD đầu tiên; chỉ để hiển thị, không tham gia entry v1.

## 3. Entry — R01

Đánh giá sau Close t, chỉ khi flat, đủ input và trong khung giờ entry.
Close, BB, SMA, EMA, MACD và MFI trong R01 đều là của VNINDEX, không trộn
Close hợp đồng với chỉ báo chỉ số. Tín hiệu mở vị thế VN30F1M; giá khớp,
stop, trailing và P/L dùng trade_data của hợp đồng. Chỉ xét khi nến VNINDEX
đã khả dụng; không dùng dữ liệu công bố sau thời điểm quyết định.

```text
LONG:
Close[t] > SMA20[t]
AND EMA5[t] > SMA20[t]
AND 0 < Close[t] - BB_Upper[t] <= 3.0
AND MACD_Line[t] > 0
AND MACD_Line[t] > MACD_Line[t-1]
AND MFI14[t] >= 55

SHORT:
Close[t] < SMA20[t]
AND EMA5[t] < SMA20[t]
AND 0 < BB_Lower[t] - Close[t] <= 3.0
AND MACD_Line[t] < 0
AND MACD_Line[t] < MACD_Line[t-1]
AND MFI14[t] <= 45
```

Khoảng breakout tính bằng điểm. Các điều kiện nối AND toàn bộ.
Cả long và short cùng true → NO_TRADE, reason `SIGNAL_CONFLICT`.

## 4. Stop-loss — R02

`R = 6.0 điểm`.

- Long: stop = entry_fill − R.
- Short: stop = entry_fill + R.
- Gap vượt stop: fill Open; chạm stop trong nến: fill stop.
- Cùng nến chạm stop và target: stop thắng.
- Stop mới tính sau Close t chỉ hiệu lực từ nến tiếp theo.

## 5. Chốt lời và đóng một phần — R03

Mức TP cố định từ giá khớp vào thực tế của hợp đồng:

```text
LONG:  TP1 = entry_fill + 6 điểm
       TP2 = entry_fill + 12 điểm
SHORT: TP1 = entry_fill - 6 điểm
       TP2 = entry_fill - 12 điểm
```

- Initial quantity = 1: TP1 đóng hết.
- Initial quantity ≥2: TP1 đóng floor(initial_qty/2); TP2 đóng phần còn lại.
- Ví dụ quantity 5: TP1 đóng 2, còn 3.
- Target đã active trước nến xét High/Low. Gap qua target vẫn fill target.

### Các trường hợp biên

- Cùng nến chạm TP1 và TP2, hoặc TP1=TP2: xử lý TP1 trước rồi TP2; nếu TP1=TP2 thì hai phần cùng khớp tại một mức giá, TP2 đóng toàn bộ phần còn lại.
- Target tạo từ entry fill có được xét ngay trong nến entry: có; stop/TP active ngay sau Open fill và được xét High/Low của nến entry; nếu cùng chạm thì stop thắng.

## 6. Trailing và time-stop — R04

- Trailing bật sau TP1 khớp, áp dụng quantity còn lại.
- Long: highest_high_since_TP1 − 6 điểm.
- Short: lowest_low_since_TP1 + 6 điểm.
- Chỉ dịch theo hướng có lợi, không nới stop; cập nhật sau Close, hiệu lực nến sau.
- MAX_HOLD_BARS = 18; hết nến thứ 18 còn vị thế thì phát market exit,
  fill Open hợp lệ kế tiếp. Không tính thời gian nghỉ trưa thành bar.

### Thứ tự và thời điểm

Stop/trailing active bị chạm ưu tiên hơn TP. File quyết định nêu thứ tự
stop/trailing → time-stop → TP → entry; thứ tự này cần hoàn chỉnh theo thời điểm
vì time-stop quyết định sau Close, còn TP có thể khớp trong nến trước Close.

- Xử lý TP intrabar và time-stop tại Close cùng nến: xử lý TP trước; nếu còn quantity tại Close và vừa đủ 18 bar thì phát time-stop cho Open kế tiếp.
- Nến entry được tính thế nào trong 18 nến: nến chứa Open fill là bar số 1.
- Có dùng toàn bộ High/Low của nến TP1 để khởi tạo trailing: không; seed tại giá TP1 để tránh giả định thứ tự intrabar, cập nhật High/Low từ nến kế tiếp.
- Kết hợp trailing và stop ban đầu: long dùng mức cao hơn giữa stop ban đầu và trailing; short dùng mức thấp hơn; trailing không được nới rủi ro.
- Time-stop, forced exit và margin breach đồng thời: cùng Close thì ưu tiên reason `MARGIN_BREACH`, sau đó `FORCED_EXIT`, rồi `TIME_STOP`; chỉ tạo một lệnh thoát.

## 7. Khung giờ — R05

Múi giờ UTC+7. Khung tạo entry signal: 09:05–11:20, 13:05–14:00.
Sau 14:00 không mở vị thế mới. Tránh giao dịch ATO/ATC.

- Forced exit sau Close nến [14:15,14:20), fill Open nến [14:20,14:25).
- Từ 14:30 strategy phải flat.
- Pending entry sống tối đa một nến thực thi; không qua nghỉ trưa/cutoff/phiên khác.
- Thiếu bar thực thi forced exit → run/data INVALID, không chế giá.

### Biên thời gian

- Biên inclusive/exclusive và signal/fill đúng 14:00: thời gian là Close của bar; cho phép signal tại 09:05–11:20 và 13:05–14:00, gồm hai đầu; signal 14:00 fill Open bar 14:00–14:05, sau 14:00 cấm entry mới.
- Xử lý nến cuối report không còn nến thực thi: pending entry bị hủy `END_OF_REPORT`; nếu đang có vị thế cần thoát mà thiếu bar thực thi thì run `INVALID`.
- Không đưa ATO/ATC vào chuỗi 5 phút tính chỉ báo.

## 8. Sizing — R07

Tỷ lệ ký quỹ cố định cho lần chạy v1: `im_rate = 0.17` (17%), theo quyết định
người dùng. Không yêu cầu bảng tỷ lệ theo ngày cho cấu hình này.

```text
risk_budget = equity_before_entry * 0.01
risk_per_contract = 6.0 * 100000 + estimated_roundtrip_cost
qty_risk = floor(risk_budget / risk_per_contract)
qty_margin = floor(available_cash /
                   (entry_price * 100000 * im_rate * 1.10))
quantity = min(qty_risk, qty_margin, 5)
```

Quantity <1 → reject; không pyramiding. Giá entry/equity dùng thông tin available
tại fill, không dùng High/Low/Close tương lai của nến thực thi.

- estimated_roundtrip_cost: phí+thuế entry tại entry price cộng phí+thuế exit ước tính tại stop price cho 1 hợp đồng; cộng broker fee hai lượt nếu có.
- Kiểm tra/trừ chi phí mở lệnh ngoài buffer margin: có; trước fill yêu cầu `equity_after_open_cost >= required_margin × 1.10`, không đủ thì reject entry.
- Giới hạn lỗ/ngày hoặc số lệnh/ngày: ngừng mở mới khi P/L ròng trong ngày ≤ −2% equity đầu ngày hoặc đã có 3 entry fill; vị thế đang mở vẫn được quản trị/đóng bình thường.
- Vốn demo v1: 100.000.000 VND, gắn nhãn `SIMULATION_ASSUMPTION`; không kế thừa 10.000.000 VND của v0.
