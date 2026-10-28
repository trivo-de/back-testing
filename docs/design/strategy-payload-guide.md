# Hướng dẫn tạo chiến lược JSON

Tài liệu dành cho người viết payload và agent chuyển yêu cầu giao dịch thành cấu
hình backtest. Nội dung áp dụng cho API hiện tại, mặc định `price-only-v2`.
Cập nhật ngày 27/10/2026.

## 1. Bắt đầu

API nhận cấu hình chiến lược; máy chủ lấy dữ liệu VN30F1M và VNINDEX 5 phút,
đánh giá điều kiện, mô phỏng khớp lệnh và lưu kết quả theo điểm × lượng.

Ví dụ đầy đủ: mở LONG khi giá đóng cửa lớn hơn SMA20, đóng khi giá nhỏ hơn
SMA20, cắt lỗ 6%, chốt lời 12%. Cuối ngày engine đóng hết lượng còn giữ.

```json
{
  "symbol": "VN30F1M",
  "entry": {
    "long": {"left": "price", "op": "above", "right": "sma20"}
  },
  "exit": {
    "long": {"left": "price", "op": "below", "right": "sma20"}
  },
  "risk": {"sl": 6, "tp": 12}
}
```

Request dùng `Content-Type: application/json`. Các thao tác chính:

| Thao tác | Endpoint | Kết quả |
| --- | --- | --- |
| Tra cấu trúc hiện hành | `GET /api/strategy-parameters` | Schema, mặc định, tham số, chỉ báo, toán tử, giới hạn và ví dụ |
| Kiểm tra | `POST /api/backtests/validate` | Cấu hình đã kiểm tra, cấu hình có hiệu lực và thông tin nguồn |
| Chạy | `POST /api/backtests` | HTTP 201, kết quả và `metadata.run_id` |
| Đọc kết quả đã lưu | `GET /api/backtests/{run_id}` | Kết quả của lần chạy đó |
| Đọc đầu vào đã ghim | `GET /api/backtests/{run_id}/input` | Request, dữ liệu, chính sách và cấu hình có hiệu lực |
| Đọc dữ liệu biểu đồ | `GET /api/backtests/{run_id}/chart` | Nến và sự kiện thuộc cùng lần chạy |

Trên web, bấm **Tra cứu tham số** cạnh vùng JSON. Khung hai cột chia thành
Cấu hình / Chỉ báo / Toán tử; chọn mục bên trái để xem giải thích và ví dụ.

## 2. Quy trình viết chiến lược

1. Xác định hướng LONG/SHORT, điều kiện mở và điều kiện đóng trong yêu cầu.
2. Xác định nguồn của từng điều kiện: VN30F1M hay VNINDEX; chỉ báo và chu kỳ.
3. Khai báo lượng mở, các mức bảo vệ và khung giờ khi có yêu cầu.
4. Viết điều kiện theo mục 4, đối chiếu payload hoàn chỉnh ở mục 7.
5. Kiểm tra bằng `/validate`, đọc lỗi và sửa phần liên quan.
6. Chạy bằng POST, lưu `run_id` để đối chiếu kết quả, nguồn và cấu hình đã áp dụng.

Agent đọc `request_schema`, `defaults`, `aliases`, `operators` và `limits` từ
`/api/strategy-parameters` trước khi tạo cấu hình. Khi yêu cầu thiếu dữ kiện làm
thay đổi chiến lược, hỏi một câu cụ thể, chẳng hạn: “Điều kiện MA20 dùng giá
VN30F1M hay VNINDEX?” hoặc “Cắt lỗ 6 là 6% hay cách 6 điểm giá?”.
Giữ nguyên các ngưỡng người dùng đã nêu; phần bỏ trống dùng mặc định ở mục 3.
Khi sửa bản có sẵn, cập nhật phần được yêu cầu và giải thích ngắn gọn thay đổi
trong bản nháp trước khi chạy.

## 3. Cấu trúc request và mặc định

| Trường | Kiểu / mặc định | Ý nghĩa |
| --- | --- | --- |
| `symbol` | Bắt buộc, `"VN30F1M"` | Mã giao dịch |
| `from`, `to` | Cùng bỏ hoặc cùng có | Ngày ISO `YYYY-MM-DD`, gồm hai đầu, giờ Việt Nam |
| `quantity` | Số nguyên dương; mặc định `1` | Lượng mở mỗi lần vào vị thế |
| `entry.long`, `entry.short` | Ít nhất một hướng | Điều kiện mở vị thế tương ứng |
| `exit.long`, `exit.short` | Tùy chọn nếu có bảo vệ | Điều kiện đóng đúng hướng; mặc định đóng lượng còn lại |
| `risk` | Tùy chọn | Cắt lỗ, chốt lời, dừng lỗ kéo theo |
| `order` | Bỏ: khớp tại giá đóng cửa | Cách khớp chung; khai báo khi dùng LO |
| `indicators` | Mặc định `{}` | Chỉ báo tự đặt tên, có nguồn và chu kỳ tường minh |
| `warmup_bars` | Số nguyên ≥ 0; mặc định `0` | Yêu cầu bổ sung về số nến khởi tạo |
| `entry.signal_windows` | Bỏ: mọi giờ trong phiên | Các cửa sổ được mở vị thế |
| `daily_limits.stop_new_entry` | Bỏ: tắt giới hạn bổ sung | Điều kiện dừng mở mới trong ngày |
| `exit.flat_by` | Bỏ: chính sách cuối ngày | Hạn bắt buộc đóng vị thế sớm hơn cuối phiên |

Mỗi hướng có `entry` cần `exit` cùng hướng hoặc ít nhất một cơ chế trong `risk`.
Điều kiện thoát được đánh giá theo nến; đóng cuối ngày là bước riêng của engine.

### Kỳ báo cáo và dữ liệu

- Bỏ cả `from/to`: lấy sáu tháng lịch gần nhất đến lúc lấy dữ liệu.
- Có cả hai ngày: lấy kỳ báo cáo cùng lịch sử cần cho chỉ báo.
- `warmup_bars` là ngưỡng bổ sung; số mẫu cần dùng mức lớn nhất giữa ngưỡng này
  và yêu cầu của chỉ báo, `shift`, giao cắt.
- Nến được dùng khi đã đóng và đã khả dụng. Dữ liệu thị trường có thể khả dụng
  trễ hơn dữ liệu giao dịch; engine đối chiếu thời điểm khả dụng ở từng quyết định.
- Phần trước kỳ chỉ khởi tạo chỉ báo. `report_range` là kỳ yêu cầu;
  `available_range` là phần nguồn thực có. Thiếu một phần kỳ được thể hiện
  trong metadata và cảnh báo `PARTIAL_REPORT_COVERAGE`.
- Kiểm tra và chạy đều lấy nguồn tại lúc gọi. Kết quả chạy ghim dữ liệu của
  chính lần chạy để đọc lại và đối chiếu.

Tên khóa phân biệt hoa/thường. Lượng và chu kỳ viết bằng số nguyên JSON.
Phần trăm trong `risk` nhận số hoặc chuỗi thập phân, ví dụ `6` hoặc `"0.6"`.
Hằng số trong cây biểu thức viết bằng số JSON, ví dụ `100` hoặc `0.6`.

## 4. Điều kiện, nguồn và chỉ báo

### 4.1. Nguồn và tên rút gọn

`trade_data` là VN30F1M; `market_data` là VNINDEX. Trong biểu thức, hai nguồn có
các cột `open`, `high`, `low`, `close`, `volume`, ví dụ `trade_data.high`.

| Tên rút gọn | Giá trị | Số mẫu khởi tạo tối thiểu |
| --- | --- | --- |
| `price` | Giá đóng cửa VN30F1M | 1 |
| `sma20` | SMA20 của giá đóng cửa VN30F1M | 20 |
| `ema5` | EMA5 của giá đóng cửa VN30F1M | 5 |
| `bb20_2.middle`, `.upper`, `.lower` | Ba dải BB, chu kỳ 20, hệ số 2 | 20 |
| `macd12_26_9.line`, `.signal`, `.histogram` | MACD 12/26/9; Histogram = Line − Signal | 34 theo yêu cầu khởi tạo của bộ chạy |
| `mfi14` | MFI14 từ High/Low/Close/Volume | 15 |

Thêm tiền tố `market.` để dùng VNINDEX: `market.price`, `market.sma20`,
`market.macd12_26_9.line`... `shift` và giao cắt làm tăng lịch sử cần thiết.
Chỉ báo cần volume chờ đủ dữ liệu volume hợp lệ.

### 4.2. So sánh và kết hợp

Điều kiện ngắn gồm ba phần `left`, `op`, `right`:

```json
{"left": "price", "op": "above", "right": "sma20"}
```

| Toán tử | Điều kiện đạt |
| --- | --- |
| `above` hoặc `gt` | Trái > phải |
| `below` hoặc `lt` | Trái < phải |
| `gte` | Trái ≥ phải |
| `lte` | Trái ≤ phải |
| `cross_up` | Mẫu trước: trái ≤ phải; mẫu hiện tại: trái > phải |
| `cross_down` | Mẫu trước: trái ≥ phải; mẫu hiện tại: trái < phải |
| `all` | Tất cả điều kiện con đều đạt |
| `any` | Ít nhất một điều kiện con đạt |

`all/any` nhận danh sách có ít nhất một điều kiện. Ví dụ giá trên SMA20 và MFI
của VNINDEX trong khoảng 55 đến 80, gồm cả hai cận:

```json
{
  "all": [
    {"left": "price", "op": "above", "right": "sma20"},
    {"ref": "market.mfi14", "min": 55, "max": 80}
  ]
}
```

Khoảng số nhận `min`, `max` hoặc cả hai; khi có cả hai thì `min <= max`.
Giao cắt dùng hai mẫu liên tiếp đã khả dụng của nguồn được tham chiếu. Thiếu
mẫu hoặc ngắt chuỗi ở khoảng thiếu/chuyển mã thì trạng thái là chưa đánh giá được.

### 4.3. Tham chiếu, số học và trạng thái

`ref` đọc giá trị; `shift` nguyên không âm lùi theo chuỗi nguồn. Ví dụ giá hiện
tại lớn hơn giá đóng cửa nến trước:

```json
{"gt": [{"ref": "trade_data.close"}, {"ref": "trade_data.close", "shift": 1}]}
```

`add`, `sub`, `mul`, `div`, `min`, `max` nhận đúng hai toán hạng số;
`floor` nhận một toán hạng. Ví dụ giá đóng cửa trừ 6 điểm:

```json
{"sub": [{"ref": "trade_data.close"}, 6]}
```

| Tham chiếu trạng thái | Ý nghĩa |
| --- | --- |
| `position.entry_price` | Giá vào của vị thế đang giữ |
| `position.initial_quantity` | Lượng mở ban đầu |
| `position.held_bars` | Số nến giữ vị thế; nến vào tính là 1 |
| `day.entry_fill_count` | Số lần mở đã khớp trong ngày |
| `day.net_pnl` | Lãi/lỗ đã chốt trong ngày, điểm × lượng |
| `clock.local_time` | Giờ quyết định theo Việt Nam, `HH:MM` |

`position.*` dùng trong điều kiện thoát sau khi có vị thế. `shift` áp dụng cho
chuỗi nguồn/chỉ báo. Giao cắt đọc hai mẫu của chuỗi được tham chiếu; hằng số giữ
nguyên giữa hai mẫu. Trạng thái vị thế và thống kê ngày là giá trị hiện thời.
Mỗi cây sau giải tên rút gọn sâu tối đa 32, tối đa 4096 nút.
Ví dụ đóng khi giữ ít nhất 18 nến hoặc từ 14:20:

```json
{
  "any": [
    {"gte": [{"ref": "position.held_bars"}, 18]},
    {"gte": [{"ref": "clock.local_time"}, "14:20"]}
  ]
}
```

### 4.4. Chỉ báo tự khai báo

Đặt trong `indicators`, rồi tham chiếu bằng tên đã đặt. Tên bắt đầu bằng chữ,
các ký tự sau dùng chữ, số hoặc `_`; chọn tên riêng khác các tên rút gọn có sẵn.

| `type` | Tham số bắt buộc ngoài `type/source` | Nguồn |
| --- | --- | --- |
| `SMA`, `HIGHEST`, `LOWEST` | `period` nguyên dương | Cột OHLC hoặc volume của một nguồn |
| `EMA` | `period` nguyên dương | Cột OHLC của một nguồn |
| `BB` | `period`, `stddev_multiplier` dương | Cột OHLC; đầu ra `.middle/.upper/.lower` |
| `MACD` | `fast_period`, `slow_period`, `signal_period`; fast < slow | Cột OHLC; đầu ra `.line/.signal/.histogram` |
| `MFI` | `period` nguyên dương | `trade_data` hoặc `market_data` để đọc HLCV |

Ví dụ hoàn chỉnh ở mục 7.5. Danh mục hiện hành cùng giới hạn được trả tại
`GET /api/strategy-parameters`.

## 5. Cách khớp lệnh

### Mặc định: tại giá đóng cửa

Bỏ `order` thì engine dùng `IMMEDIATE`: điều kiện đúng tại nến đóng → tín hiệu
→ lệnh → khớp đủ lượng tại chính giá đóng cửa đó. Đây là giả định mô phỏng
khớp cùng giá đóng cửa, độ trễ bằng 0. Lệnh đóng mặc định dùng lượng còn giữ.

### Lệnh giới hạn

`order.type="LO"` cần `limit_price` là số hoặc biểu thức giá dương. Giá được
tính và ghim khi tạo lệnh. Bắt đầu xét từ nến thực có kế tiếp:

| Hướng lệnh | Giá khớp mô phỏng |
| --- | --- |
| BUY | Open nếu Open ≤ limit; còn lại khớp limit khi Low ≤ limit |
| SELL | Open nếu Open ≥ limit; còn lại khớp limit khi High ≥ limit |

LO chờ tối đa **3 nến thực có sau nến tạo**, chỉ trong ngày đặt. Vẫn được khớp
ở nến thứ ba; sau nến đó hết hạn nếu chưa khớp. Nghỉ trưa giữ bộ đếm. Cuối
ngày hủy lệnh còn chờ; cuối dữ liệu giữa phiên hủy với `END_OF_REPORT`.
LO khớp đủ lượng khi điều kiện giá đạt.

`order` tại từng `entry.long/short` hoặc `exit.long/short` ưu tiên hơn `order`
chung. Dạng đầy đủ của hành động gồm `condition`, `order` tùy chọn; hành động
đóng nhận thêm `quantity` nguyên dương hoặc `"remaining"`. Lượng yêu cầu đóng
phải phù hợp lượng đang giữ lúc gửi lệnh.

Engine giữ tối đa một vị thế và một lệnh chủ động đang chờ. Khi phẳng mà LONG
và SHORT cùng đúng, ghi `SIGNAL_CONFLICT`. Nến đã đóng hết vị thế sẽ bắt đầu
xét mở mới từ nến sau.

## 6. Bảo vệ, lượng và đóng cuối ngày

### 6.1. Đơn vị và lượng

`quantity=3` mở một vị thế có lượng 3. Trong `risk.targets`, `quantity` là lượng
đóng ở từng mức; `"remaining"` đóng hết phần còn lại.

`risk.sl`, `risk.tp`, `risk.trailing`, `risk.trailing_after_tp1` dùng **%**:
`6` là 6%, `0.6` là 0,6%. `stop_price`, `targets[].price` là **giá tuyệt đối**.

| Cấu hình | Cách dùng |
| --- | --- |
| `risk.sl` | % cắt lỗ từ giá vào thực tế |
| `risk.tp` | % chốt lời từ giá vào thực tế, đóng lượng còn lại |
| `risk.trailing` | % kéo theo từ mốc giá thuận lợi, bắt đầu tại entry |
| `risk.stop_price` | Số/biểu thức giá dừng lỗ, tính và ghim lúc quyết định mở |
| `risk.targets` | Mỗi mức có `pct` hoặc `price`, kèm `quantity` |
| `risk.trailing_after_tp1` | % kéo theo, bắt đầu sau khi TP1 thực sự khớp |

Chọn một trong mỗi cặp: `sl` / `stop_price`, `tp` / `targets`,
`trailing` / `trailing_after_tp1`. Dạng sau TP1 cần có `targets`.
Phần trăm phải dương; mức giá quy đổi phải dương và nằm đúng phía cắt lỗ/chốt
lời so với giá khớp thực tế. Với giá vào P và r = tham số / 100:

- LONG: stop = P × (1 − r); target = P × (1 + r).
- SHORT: stop = P × (1 + r); target = P × (1 − r).

Ví dụ vào 100, SL 6%, TP 12%: LONG có stop 94, target 112;
SHORT có stop 106, target 88.

### 6.2. Thời điểm và thứ tự bảo vệ

SL/TP xét **Close** và khớp tại **Close thực tế** đạt/vượt ngưỡng. Ví dụ LONG
có TP 112, nến đóng 115 thì thoát tại 115. Entry khớp tại Close bắt đầu được
bảo vệ từ nến sau; entry LO khớp Open/trong nến được xét bảo vệ tại Close sau fill.

TP nhiều mức xử lý theo thứ tự có lợi tăng dần. Một Close vượt nhiều mức thì
các phần đóng đều dùng Close đó. `remaining` đặt ở mức cuối; tổng lượng cố định
nằm trong lượng mở ban đầu. Biểu thức lượng TP chỉ đọc
`position.initial_quantity` và phải cho ra số nguyên dương.

Trailing dùng Close thuận lợi nhất kể từ kích hoạt, có giá khớp kích hoạt làm
mốc ban đầu. Mỗi nến kiểm tra mức đang có trước, sau đó siết mức mới cho nến
kế tiếp. LONG dùng mốc cao nhất, SHORT dùng mốc thấp nhất.
`trailing_after_tp1` lấy giá khớp TP1 làm mốc. Khi kích hoạt thoát, trailing
gửi lệnh theo `order` của hành động đóng cùng hướng, hoặc `order` chung khi
chưa khai báo riêng. LO đang chờ giữ nguyên hạn và limit.

### 6.3. Giờ mở, giới hạn ngày và cuối ngày

`entry.signal_windows` nhận các cặp `["HH:MM","HH:MM"]`, gồm hai đầu, tăng dần
và tách nhau. Khớp tại Close xét giờ quyết định; LO còn xét Open của nến thực
thi. Ví dụ: `[["09:05","11:20"],["13:05","14:00"]]`.

`daily_limits.stop_new_entry` dừng mở mới. Số lần entry đã khớp và lãi/lỗ đã
chốt trong ngày đặt lại khi sang ngày mới. Ví dụ ở mục 7.6.

Cuối phiên liên tục, engine xét lệnh chờ khớp trong nến cuối, hủy phần còn chờ,
đóng hết lượng còn giữ tại Close thực và ghi `END_OF_DAY` — **Hết ngày**.
Bước đóng này ưu tiên trước bảo vệ/điều kiện tại Close cuối; tại mốc đó engine
kết thúc mở mới. Lịch hiện tại dùng nến mở 14:25, đóng 14:30. Khi dữ liệu dừng
giữa phiên, lượng còn giữ được ghi trong `open_position`.

`exit.flat_by` là hạn bắt buộc sớm hơn cuối phiên: chiến lược cần điều kiện
đóng đáp ứng mốc đó. Còn vị thế tại hạn thì trả `REQUIRED_EXIT_NOT_FILLED`.
Cửa sổ entry phải kết thúc trước `flat_by`.

## 7. Các payload hoàn chỉnh

Các ví dụ minh họa cách ghép cấu hình. Ngưỡng, chu kỳ và lượng được ghi ngay
trong từng ví dụ để đối chiếu với yêu cầu của mình.

### 7.1. LONG/SHORT, giao cắt và nguồn thị trường

Mở khi giá VN30F1M cắt SMA20 theo hướng phù hợp với VNINDEX. Đóng khi giá đi
ngược SMA20 hoặc giữ ít nhất 18 nến. Mỗi lần mở lượng 2.

```json
{
  "symbol": "VN30F1M",
  "from": "2026-04-01",
  "to": "2026-09-15",
  "quantity": 2,
  "entry": {
    "long": {"all": [
      {"left": "price", "op": "cross_up", "right": "sma20"},
      {"left": "market.price", "op": "above", "right": "market.sma20"}
    ]},
    "short": {"all": [
      {"left": "price", "op": "cross_down", "right": "sma20"},
      {"left": "market.price", "op": "below", "right": "market.sma20"}
    ]}
  },
  "exit": {
    "long": {"any": [
      {"left": "price", "op": "below", "right": "sma20"},
      {"gte": [{"ref": "position.held_bars"}, 18]}
    ]},
    "short": {"any": [
      {"left": "price", "op": "above", "right": "sma20"},
      {"gte": [{"ref": "position.held_bars"}, 18]}
    ]}
  },
  "risk": {"sl": 6, "tp": 12}
}
```

### 7.2. Mở bằng LO, đóng theo điều kiện tại Close

Limit mở ghim bằng Close lúc ra tín hiệu. Hành động đóng khai báo riêng
`IMMEDIATE` để khớp tại Close khi điều kiện thoát đạt.

```json
{
  "symbol": "VN30F1M",
  "entry": {
    "long": {"left": "price", "op": "above", "right": "sma20"}
  },
  "exit": {
    "long": {
      "condition": {"left": "price", "op": "below", "right": "sma20"},
      "order": {"type": "IMMEDIATE"}
    }
  },
  "order": {"type": "LO", "limit_price": {"ref": "trade_data.close"}},
  "risk": {"sl": 6}
}
```

### 7.3. TP nhiều mức và trailing sau TP1

Mở lượng 3; TP1 đóng `floor(3/2)=1`, TP2 đóng phần còn lại. Trailing 6% bắt đầu
sau khi TP1 khớp. Các phần đóng cùng giữ liên kết vị thế.

```json
{
  "symbol": "VN30F1M",
  "quantity": 3,
  "entry": {
    "long": {"left": "price", "op": "above", "right": "sma20"}
  },
  "risk": {
    "sl": 6,
    "targets": [
      {"pct": 6, "quantity": {"floor": [{"div": [{"ref": "position.initial_quantity"}, 2]}]}},
      {"pct": 12, "quantity": "remaining"}
    ],
    "trailing_after_tp1": 6
  }
}
```

### 7.4. Cắt lỗ và chốt lời bằng giá tuyệt đối

Mở tại Close; ghim stop thấp hơn Close quyết định 6 điểm, target cao hơn 12 điểm.
Với LO, các giá tuyệt đối vẫn ghim tại quyết định mở và được kiểm tra lại so
với giá khớp thực tế.

```json
{
  "symbol": "VN30F1M",
  "entry": {
    "long": {"left": "price", "op": "above", "right": "sma20"}
  },
  "risk": {
    "stop_price": {"sub": [{"ref": "trade_data.close"}, 6]},
    "targets": [
      {"price": {"add": [{"ref": "trade_data.close"}, 12]}, "quantity": "remaining"}
    ]
  }
}
```

### 7.5. Chỉ báo tự khai báo và nến trước

Mở LONG khi giá vượt mức cao nhất của 20 nến trước và nằm trên SMA50. Đóng khi
giá nhỏ hơn SMA50. `shift=1` lấy giá trị chỉ báo ở mẫu trước.

```json
{
  "symbol": "VN30F1M",
  "indicators": {
    "peak20": {"type": "HIGHEST", "source": "trade_data.high", "period": 20},
    "mean50": {"type": "SMA", "source": "trade_data.close", "period": 50}
  },
  "entry": {
    "long": {"all": [
      {"gt": [{"ref": "trade_data.close"}, {"ref": "peak20", "shift": 1}]},
      {"left": "price", "op": "above", "right": "mean50"}
    ]}
  },
  "exit": {
    "long": {"left": "price", "op": "below", "right": "mean50"}
  }
}
```

### 7.6. Khung giờ, dừng mở mới và hạn đóng sớm

Chỉ mở trong hai cửa sổ; dừng mở khi đủ 3 lần khớp entry hoặc P&L đã chốt trong
ngày ≤ −20 điểm × lượng. Đóng khi giá dưới SMA20 hoặc từ 14:20; hạn phẳng 14:25.

```json
{
  "symbol": "VN30F1M",
  "quantity": 2,
  "entry": {
    "signal_windows": [["09:05", "11:20"], ["13:05", "14:00"]],
    "long": {"left": "price", "op": "above", "right": "sma20"}
  },
  "exit": {
    "long": {"any": [
      {"left": "price", "op": "below", "right": "sma20"},
      {"gte": [{"ref": "clock.local_time"}, "14:20"]}
    ]},
    "flat_by": "14:25"
  },
  "daily_limits": {
    "stop_new_entry": {"any": [
      {"gte": [{"ref": "day.entry_fill_count"}, 3]},
      {"lte": [{"ref": "day.net_pnl"}, -20]}
    ]}
  },
  "risk": {"sl": 6}
}
```

## 8. Kiểm tra và đọc kết quả

`/validate` kiểm tra cấu trúc, biểu thức và nguồn, trả các trường:

| Trường | Dùng để |
| --- | --- |
| `valid`, `payload` | Xác nhận bước kiểm tra và xem lại cấu hình gửi vào |
| `effective_config` | Xem mặc định đã áp dụng, hành động, chỉ báo đã giải và số mẫu cần |
| `data_metadata`, `warnings` | Xem nguồn, kỳ yêu cầu, phạm vi thực có và khoảng thiếu |

Điều kiện và bảo vệ tiếp tục được đánh giá theo từng nến khi chạy. Mức bảo vệ
tuyệt đối còn cần phù hợp giá entry thực tế. Dùng bản ghim của lần chạy để
đối chiếu những quyết định đã xảy ra.

| Nhóm kết quả | Ý nghĩa |
| --- | --- |
| `evaluations` | Quyết định theo nến, trạng thái và lý do |
| `signals` | Tín hiệu mở/đóng |
| `orders` | Lệnh gửi, loại, lượng, trạng thái và lý do kết thúc |
| `fills` | Lần thực sự khớp, giá, lượng, thời điểm, liên kết lệnh/vị thế |
| `trades` | Các phần đóng và P&L đã chốt của từng phần |
| `open_position` | Vị thế còn giữ cuối dữ liệu, hoặc `null` |
| `summary`, `pnl_history` | Tổng hợp và diễn biến P&L theo nến |
| `metadata` | `run_id`, nguồn, phạm vi, cấu hình có hiệu lực, phiên bản, mã băm |

Lãi/lỗ phần đóng = hướng × (giá đóng − giá vào) × lượng đóng; LONG = 1, SHORT = −1.
Phần chưa chốt dùng Close đang đánh dấu và lượng còn lại.
`total_pnl = realized_pnl + unrealized_pnl`, đơn vị **điểm × lượng**.
`max_drawdown` là mức giảm lớn nhất từ đỉnh tổng P&L đã biết, có mốc đầu 0.
`win_rate` là số vị thế lãi chia số vị thế đã đóng hết, tỷ lệ 0..1; vị thế hòa
vốn vẫn nằm trong mẫu số, mẫu số 0 trả `null`. Giá/P&L là chuỗi thập phân;
lượng/số đếm là số nguyên. Đọc `orders` cùng `fills` để phân biệt tín hiệu,
lệnh chờ và giao dịch thực sự khớp.

## 9. Đọc lỗi và sửa cấu hình

HTTP 422 có `detail` là danh sách lỗi cấu trúc với `loc/msg`, hoặc chuỗi mã lỗi
nghiệp vụ. HTTP 503 dùng cho lỗi nguồn/dịch vụ. Khi kiểm tra lỗi, giữ cấu hình đã gửi,
nội dung `detail`, và `run_id` nếu đã nhận kết quả thành công.

| Mã lỗi / trạng thái | Cách xử lý |
| --- | --- |
| `INVALID_REPORT_RANGE` | Điền đủ ngày ISO, đúng thứ tự, trong thời gian đã xảy ra |
| `EXIT_REQUIRED` | Thêm điều kiện đóng cùng hướng hoặc cơ chế bảo vệ |
| `UNKNOWN_REF`, `INVALID_INDICATOR_NAME` | Tra tên trong danh mục; khai báo chu kỳ khác trong `indicators` |
| `INDICATOR_PARAMETERS_MISMATCH` | Đối chiếu loại, nguồn và đúng bộ tham số chỉ báo |
| `UNSUPPORTED_OPERATOR`, `INVALID_OPERAND_COUNT` | Dùng toán tử và số toán hạng ở mục 4 |
| `INVALID_SHIFT`, `CROSS_REQUIRES_SERIES` | Shift nguyên không âm trên chuỗi; giao cắt dùng chuỗi nguồn/chỉ báo và hằng số |
| `LIMIT_PRICE_REQUIRED_ONLY_FOR_LO` | LO có `limit_price`; khớp tại Close chỉ cần `type` |
| `INVALID_RISK`, `TRAILING_REQUIRES_TP1` | Đối chiếu các cặp lựa chọn và điều kiện bật bảo vệ |
| `INVALID_PROTECTION_LEVEL` | Kiểm tra giá dương, đúng phía so với giá entry thực tế |
| `INVALID_TARGET_QUANTITY`, `REMAINING_TARGET_MUST_BE_LAST` | Kiểm tra lượng, biểu thức lượng và mức `remaining` cuối danh sách |
| `INVALID_CLOSE_QUANTITY_OR_PRICE` | Đối chiếu lượng đóng với lượng còn giữ |
| `ENTRY_WINDOW_AFTER_FLAT_BY` | Kết thúc cửa sổ mở trước hạn bắt buộc đóng |
| `REQUIRED_EXIT_NOT_FILLED` | Kiểm tra điều kiện/cách khớp cho hạn đóng sớm `flat_by` |
| `REPORT_DATA_MISSING`, `CALENDAR_REQUIRED` | Kiểm tra độ phủ nguồn và lịch phiên của kỳ yêu cầu |
| `MISSING_POSITION_EXECUTION_BAR`, `MISSING_POSITION_MANAGEMENT_DATA` | Xem khoảng thiếu của nguồn đang phục vụ vị thế |
| `OPEN_POSITION_AT_CONTRACT_CHANGE` | Kiểm tra thời điểm đóng trước ranh giới đổi mã |
| `AUTO_FETCH_NETWORK_ERROR`, `AUTO_FETCH_HTTP_ERROR`, `AUTO_FETCH_INVALID_SOURCE` | Kiểm tra lỗi nguồn/thông tin tải, thử lại khi nguồn sẵn sàng |
| `UNEVALUABLE` trong kết quả | Đọc lý do nến chưa đủ mẫu/dữ liệu để đánh giá mở |
| `LEGACY_OR_DATA_FIELD_NOT_ALLOWED`, `extra_forbidden` | Đối chiếu các trường request ở mục 3 |

Agent sửa theo lỗi trả về, kiểm tra lại và báo phần đã đổi. Với lỗi nguồn hoặc
yêu cầu còn thiếu, nêu thông tin cần bổ sung để người dùng quyết định bước tiếp theo.

## 10. Tra cứu liên quan

- [Hợp đồng chiến lược](price-only-contract.md): quy tắc nghiệp vụ chi tiết.
- [Đặc tả API](backtest-api-specification.md#bề-mặt-api-hiện-tại): endpoint, bộ lọc lịch sử.
- [Kiểm chứng C–D](../testing/price-only-cd.md): bằng chứng thực thi, dữ liệu, giao diện.
- Danh mục máy đọc được: `GET /api/strategy-parameters`.
- Cấu trúc endpoint: `/openapi.json`; giao diện tra API: `/docs`.
