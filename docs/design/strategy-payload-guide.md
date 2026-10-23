# Hướng dẫn điền cây công thức và payload chiến lược

Soạn chiến lược bằng các chỉ báo, phép toán và hành động trong tài liệu này.

- [Đặc tả API](backtest-api-specification.md): cấu trúc request và kết quả.
- [Payload minh họa](../../src/backtesting_api/web/canslim-v1-example.json): mẫu JSON để điền.
- [CANSLIM v1](../strategies/canslim-v1-rules.md): giá trị và quy tắc của mẫu.
- `POST /api/backtests/validate` kiểm tra cấu trúc, dữ liệu và tổ hợp thực thi.
- Khi chạy, nến thiếu chỉ báo được ghi chưa đánh giá được và bỏ mở lệnh.

## 1. Đọc bảng và điền theo thứ tự nào?

- **Bắt buộc**: phải có trong nhóm đang khai báo.
- **Bắt buộc khi…**: điều kiện cần field được ghi ngay trong mô tả param.
- **Tùy chọn**: có thể bỏ; bảng ghi cách xử lý khi bỏ.
- Keyword phân biệt hoa/thường. `true`/`false`là boolean JSON, không viết`"true"`/`"false"`. Tên tự đặt khác với keyword cố định.

1. Điền dữ liệu và khai báo chỉ báo.
2. Viết điều kiện mở, đóng và sizing.
3. Điền giới hạn ngày, khớp lệnh và cách tính tiền.
4. Đối chiếu mọi `ref` và tên điều kiện.

## 2. Tham chiếu

`ref` đọc giá trị từ nguồn hoặc chỉ báo đã khai báo. Ví dụ: `trade_data.close` đọc cột Close trong `trade_data`.

Ví dụ dữ liệu đã nhập:

```json
{"trade_data": {"bars": [{"close": "1301.0"}, {"close": "1302.0"}]}}
```

Cột nằm ở `trade_data.bars[].close`; bộ đọc quy ước viết gọn thành`trade_data.close` trong source/ref, không cần nhập chỉ số từng dòng.

| Muốn lấy gì?                          | Điền thế nào?                           | Kết quả trong ví dụ                                      |
| ---------------------------------------- | ------------------------------------------- | ------------------------------------------------------------ |
| Cả cột Close làm đầu vào chỉ báo | `"source": "trade_data.close"`            | Chuỗi 1301.0, 1302.0; chỉ tính đến nến đã khả dụng |
| Close của nến đang xét               | `{"ref": "trade_data.close"}`             | 1302.0 nếu đang xét nến thứ hai đã đóng             |
| Close của nến trước                  | `{"ref": "trade_data.close", "shift": 1}` | 1301.0 khi đang xét nến thứ hai                          |

Với chỉ báo cũng vậy: khai báo chỉ báo trong indicators rồi dùng ref lấy
**kết quả tính ra**:

```json
{
  "indicators": {
    "sma20": {"type": "SMA", "source": "trade_data.close", "period": 20}
  },
  "entry": {
    "conditions": {
      "LONG": {"gt": [{"ref": "trade_data.close"}, {"ref": "sma20"}]}
    },
    "any": ["LONG"]
  }
}
```

Ví dụ trên tính SMA20 rồi so Close với SMA20. Tham chiếu dựa vào tên khai báo, độc lập với thứ tự khóa JSON.

`position`, `account`, `day`, `clock` là trạng thái do bộ chạy tính. `position.entry_price` chỉ có sau khi lệnh mở khớp.

| Tham chiếu được dùng                                      | Ý nghĩa                                                                                             |
| -------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| `trade_data.open`,`.high`,`.low`,`.close`,`.volume`  | OHLCV chuỗi giao dịch                                                                               |
| `market_data.open`,`.high`,`.low`,`.close`,`.volume` | OHLCV VNINDEX                                                                                         |
| `sma20`,`ema5`,`mfi14`                                   | Một giá trị chỉ báo                                                                              |
| `bb.middle`,`bb.upper`,`bb.lower`                        | Ba đầu ra BB                                                                                        |
| `macd.line`,`macd.signal`,`macd.histogram`               | Các đầu ra MACD                                                                                    |
| `position.entry_price`                                       | Giá khớp vào thực tế                                                                             |
| `position.entry_<tên>`                                      | Giá trị lưu từ `entry.details.<tên>` khi tạo tín hiệu mở; ví dụ `position.entry_pivot` |
| `position.initial_quantity`                                  | Số hợp đồng lúc mở vị thế                                                                     |
| `position.held_bars`                                         | Số nến giữ vị thế                                                                                |
| `account.equity`                                             | Giá trị tài khoản tại thời điểm xét                                                          |
| `account.required_margin`                                    | Ký quỹ yêu cầu hiện tại                                                                         |
| `day.net_pnl`                                                | P/L ròng ngày theo quy tắc tài khoản v1                                                          |
| `day.start_equity`                                           | Giá trị tài khoản đầu ngày                                                                     |
| `day.entry_fill_count`                                       | Số lần khớp mở vị thế trong ngày                                                               |
| `clock.local_time`                                           | Giờ tại thời điểm đánh giá                                                                    |

### Phân biệt tên cố định và tên do khai báo quyết định

| Loại tên                | Ví dụ                                                                  |
| ------------------------- | ------------------------------------------------------------------------ |
| Field cố định          | `trade_data`,`bars`,`close`,`type`,`source`,`period`,`ref` |
| Keyword cố định        | `SMA`,`BB`,`LONG`,`SHORT`,`next_open`                          |
| Khóa khai báo chỉ báo | `sma20` trong indicators.sma20                                         |
| Đầu ra chỉ báo        | `upper` trong bb.upper                                                 |
| Tên điều kiện thoát  | `TP1` trong conditions.TP1                                             |

Ví dụ cần thêm SMA50 thì khai báo `"sma50": {"type": "SMA", "source": "trade_data.close", "period": 50}`rồi dùng`{"ref": "sma50"}`.

Trong bb.upper, bb lấy từ khóa indicators.bb; upper là đầu ra cố định của BB.

### Phân biệt source, ref và tên điều kiện

| Cách điền                         | Dùng để làm gì?                                                  |
| ------------------------------------ | --------------------------------------------------------------------- |
| `"source": "trade_data.close"`     | Cấp cả chuỗi Close cho hàm chỉ báo                              |
| `{"ref": "trade_data.close"}`      | Lấy một giá trị Close tại thời điểm xét                      |
| `{"ref": "macd.line", "shift": 1}` | Lấy MACD line của một nến trước trong chính chuỗi/hợp đồng |
| `"any": ["LONG", "SHORT"]`         | Tra tên điều kiện trong conditions của nhóm hiện tại          |
| `"level": "TP1"`                   | Chọn mức target đã tạo cho hướng vị thế hiện tại           |
| `"quantity": "remaining"`          | Hành động đóng số lượng còn lại; không phải ref           |

## 3. Các nút của cây công thức

Mỗi object biểu thức chứa một phép toán, hoặc `ref`kèm`shift` tùy chọn.

| Keyword                         | Đầu vào bắt buộc                                      | Kết quả / cách đọc                             |
| ------------------------------- | ---------------------------------------------------------- | --------------------------------------------------- |
| `all`                         | Mảng không rỗng các điều kiện                       | Tất cả cùng đúng                               |
| `any`                         | Mảng không rỗng các điều kiện                       | Ít nhất một điều kiện đúng                  |
| `gt`,`gte`,`lt`,`lte`   | Mảng đúng 2 toán hạng                                 | Lần lượt`>`,`>=`,`<`,`<=`                |
| `add`,`sub`,`mul`,`div` | Mảng đúng 2 toán hạng số                             | Cộng, trừ, nhân, chia; thứ tự trái rồi phải |
| `min`,`max`                 | Mảng đúng 2 toán hạng số trong thiết kế hiện tại | Chọn giá trị nhỏ/lớn hơn                      |
| `floor`                       | Mảng đúng 1 toán hạng số                             | Làm tròn xuống                                   |
| `ref`                         | Chuỗi tên trong bảng tham chiếu                        | Đọc giá trị, không thực thi mã               |
| `shift`                       | Số nguyên >= 0, tùy chọn cùng ref                     | Lùi số mẫu; bỏ thì 0                           |

- Toán hạng số: số JSON hữu hạn, `ref` số hoặc cây phép toán số.
- Chuỗi giờ như `"14:20"` dùng để so sánh giờ.
- Giá nến và trường tiền nhận chuỗi thập phân; công thức dùng số JSON như `6`, `0.01`.
- Tính tiền giữ độ chính xác thập phân. Chia 0, kết quả sai hoặc phép số học với boolean bị từ chối.
- Tên trong `all`/`any` được tra trong `conditions` của cùng nhóm. Tham chiếu vòng bị từ chối.
- Phép toán được hỗ trợ liệt kê trong bảng trên; `eq`, `not`, `cross_over`, mã Python và chuỗi điều kiện bị từ chối.

### Ví dụ điền từ câu điều kiện

“Close lớn hơn SMA20 và MFI14 ít nhất 55”:

```json
{
  "all": [
    {"gt": [{"ref": "trade_data.close"}, {"ref": "sma20"}]},
    {"gte": [{"ref": "mfi14"}, 55]}
  ]
}
```

“Close vượt dải trên, nhưng không quá 3 điểm”

```json
{
  "all": [
    {"gt": [{"sub": [{"ref": "trade_data.close"}, {"ref": "bb.upper"}]}, 0]},
    {"lte": [{"sub": [{"ref": "trade_data.close"}, {"ref": "bb.upper"}]}, 3]}
  ]
}
```

“TP1 long bằng giá khớp vào cộng 6 điểm”

```json
{"add": [{"ref": "position.entry_price"}, 6]}
```

## 4. Params ngoài cùng của payload

- `auto_fetch_data: true`: thay cả hai nguồn nhập tay bằng dữ liệu tự tải, kể cả nguồn nhập tay sai.
- Bỏ cờ hoặc đặt `false`: kiểm tra và dùng dữ liệu nhập tay.
- Có `report`: lấy thêm số nến khởi tạo trước `start_date` theo `warmup_bars`, chỉ báo và `shift`; tải đến hết `end_date`.
- Bỏ `report`: lấy sáu tháng gần nhất đến hiện tại. Lỗi tải kết thúc yêu cầu.
- Xem [đặc tả API](backtest-api-specification.md#3-cấu-trúc-request) về nến đã đóng và lịch hợp đồng.

**Trường bắt buộc:**

- `strategy`: Quy tắc giao dịch: dùng chỉ báo nào, khi nào mở/đóng vị thế, vào bao nhiêu hợp đồng và giới hạn rủi ro.
- `execution`: Cách mô phỏng khớp lệnh, gồm thời điểm khớp và mức trượt giá (chi tiết mục 9).
- `initial_cash`: Số vốn ban đầu của tài khoản backtest. Ví dụ v1: 100.000.000 đồng.
- `accounting`: Các thông số tính P/L, ký quỹ, thuế và phí; điền theo nhóm accounting bên dưới. Vốn ban đầu vẫn nằm ngoài nhóm này.

**Định dạng nhập:** trade_data, strategy, execution, accounting là object JSON;
initial_cash là chuỗi số thập phân, ví dụ `"100000000"`.

**Trường tùy chọn:**

- `auto_fetch_data`: Boolean, mặc định `false`. Đặt `true` để tự tải cả VN30F1M và VNINDEX 5 phút từ VNDIRECT; dữ liệu tự tải luôn được ưu tiên hơn cả hai nguồn nhập tay.
- `trade_data`: Lịch sử giá và khối lượng giao dịch; bắt buộc khi không bật tự lấy.
- `report`: kỳ báo cáo gồm `start_date`/`end_date` dạng `YYYY-MM-DD`; khi tự lấy,
  hai ngày này đồng thời xác định khoảng tải cùng sáu tháng dữ liệu khởi tạo.
- `market_data`: Lịch sử VNINDEX để đánh giá thị trường chung. Khi nhập tay và có source/ref trỏ tới nguồn này thì phải gửi; nếu tự lấy thì máy chủ cung cấp.

Nguồn cho mẫu v1:

- SMA20, EMA5, BB và MACD: `market_data.close` của VNINDEX.
- MFI14: HLCV trong `market_data`; nguồn này bắt buộc cho v1.
- So sánh Close với SMA/BB ở entry dùng VNINDEX. Ví dụ `trade_data.close` ở mục tham chiếu chỉ minh họa cú pháp.
- Khớp lệnh, stop, trailing và P/L dùng giá hợp đồng. TP1/TP2 cách giá khớp 6/12 điểm theo hướng vị thế.

### accounting — tính tiền, ký quỹ, thuế và phí

**Vị trí:** `accounting` ngoài cùng, cùng cấp với `initial_cash` và `strategy`.
Các field dưới đây chỉ nhập trong accounting, không lặp lại ở ngoài cùng.

**Chọn mô hình tính tiền:**

- `model`: `"normalized"` cho mô hình mua/bán theo đơn vị giá hoặc `"contract"` cho hợp đồng.

Với `model: "normalized"`, điền `fee_rate` là tỷ lệ phí trên giá trị mỗi lượt
khớp. Với `model: "contract"`, các param bắt buộc là:

- `margin_rate`: Tỷ lệ ký quỹ, điền `"0.17"` = 17%, cố định toàn kỳ.
- `pit_rate`: Thuế suất thu nhập cá nhân, điền `"0.001"` = 0,1% trên cơ sở
  tính thuế; không phải tổng tỷ lệ phí trên toàn giá trị hợp đồng.
- `exchange_fee_per_contract`: Phí sàn mỗi hợp đồng khớp mỗi lượt, điền `"2700"` đồng.
- `clearing_fee_per_contract`: Phí bù trừ mỗi hợp đồng mỗi lượt, điền `"2550"` đồng.
- `broker_fee_per_contract`: Phí môi giới mỗi hợp đồng mỗi lượt, mẫu điền
  `"0"`. Giá trị 0 chỉ bỏ phí môi giới, không bỏ các phí/thuế khác.

**Trường tùy chọn:**

- `contract_multiplier`: Hệ số quy đổi điểm giá sang tiền, dùng tính P/L,
  rủi ro và ký quỹ. Bỏ thì mặc định `"100000"`; không nhân vào OHLC/chỉ báo.

**Định dạng:** các giá trị là chuỗi số thập phân. Hệ số hợp đồng > 0;
0 < margin_rate <= 1; 0 <= pit_rate <= 1; các khoản phí >= 0.
Lưu đầy đủ giá trị áp dụng, kể cả mặc định, cùng kết quả chạy.

**Ví dụ:**

```json
{
  "initial_cash": "100000000",
  "accounting": {
    "model": "contract",
    "contract_multiplier": "100000",
    "margin_rate": "0.17",
    "pit_rate": "0.001",
    "exchange_fee_per_contract": "2700",
    "clearing_fee_per_contract": "2550",
    "broker_fee_per_contract": "0"
  }
}
```

- `tax_base = giá khớp × contract_multiplier × số hợp đồng × margin_rate / 2`.
- `PIT = tax_base × pit_rate`. Phí theo hợp đồng nhân với lượng khớp; mở và đóng tính riêng.
- Các mức trong ví dụ là tham số mô phỏng v1.
- `account.equity` đọc vốn do bộ chạy tính; kết quả hợp đồng được lưu và đọc qua kho file.

### trade_data / market_data

`bars` chứa các nến đầu vào; `bars[].close` là Close của từng nến.

**Trường bắt buộc:**

- `bars` : Mảng nến có thứ tự thời gian.
- `bars[].time` : Số nguyên Unix tại lúc mở nến.
- `bars[].open`, `bars[].high`, `bars[].low`, `bars[].close` : Mỗi trường là chuỗi giá thập phân hữu hạn, OHLC hợp lệ.
- `bars[].volume` (khi dùng mfi/quy tắc khối lượng): Số không âm.
- `trade_data.contract_map` (khi tách hợp đồng v1): Bảng ánh xạ theo data contract, không tự suy từ OHLCV.

**Trường tùy chọn:**

- `resolution`: Khung thời gian, mặc định `"5"` (5 phút); `"D"` là nến ngày.
- `bars[].close_time`,`bars[].available_at` (tùy chọn với quy ước 5 phút đã chốt): Bỏ thì open+300 giây và available=close; không áp dụng mặc định này cho daily.
- `symbol`: Nhãn như`VN30F1M `; không chọn rule.
- `timestamp_unit`: Chỉ`"s"`,`"ms"`; mặc định`"s"`.
- `timezone`: Tên múi giờ IANA; mặc định`Asia/Ho_Chi_Minh `.
- `price_unit` (tùy chọn cho logic giá): Nhãn đơn vị.

contract_map đã có các dòng contract_code, expiry_date và expiry_unix trong
payload. Cách đọc ngày và chuyển kỳ theo [data contract v1](../data/vn30f1m/data-contract-v1.md).

## 5. strategy và chỉ báo

**Vị trí:** `strategy`; các khai báo chỉ báo nằm trong`strategy.indicators`.
**Mô tả:** chỉ báo cần tính và các nhóm quy tắc dùng kết quả đó.

**Trường bắt buộc theo từng trường hợp:**

- `entry`,`exit` : Theo mục 6–7.
- `indicators` (khi quy tắc dùng chỉ báo): Object chứa các khai báo như sma20, ema5, bb
- `sizing`: Bắt buộc; v1 dùng risk_and_margin, không có quy tắc ngầm mua 1 hợp đồng.

**Trường tùy chọn:**

- `warmup_bars`: Số nến lịch sử tối thiểu của chuỗi chỉ báo (VNINDEX đối với v1) mà chiến lược yêu cầu trước khi được xét mở vị thế, tính cả nến đang xét đã đóng. Nếu bỏ, không áp thêm ngưỡng số nến riêng từ field này; chỉ xét khi các chỉ báo được dùng đã có giá trị hợp lệ.
- `daily_limits`.

Mỗi chỉ báo cần `type`, `source` và tham số theo bảng. Hàm tính nằm trong `domain/indicators.py`.

| type (keyword cố định) | source được dùng                              | Tham số phải điền                                                                                        | Đầu ra để ref                      |
| ------------------------- | ------------------------------------------------- | ------------------------------------------------------------------------------------------------------------ | -------------------------------------- |
| `SMA`                   | Một cột số OHLCV của trade_data/market_data   | `period`: số nguyên dương                                                                              | Tên chỉ báo                         |
| `HIGHEST` / `LOWEST`  | Một cột số OHLCV của trade_data/market_data   | `period`: số nguyên dương                                                                              | Tên chỉ báo                         |
| `EMA`                   | Một cột giá của trade_data/market_data        | `period`: số nguyên dương                                                                              | Tên chỉ báo                         |
| `BB`                    | Một cột giá của trade_data/market_data        | `period`,`stddev_multiplier` > 0                                                                         | tên.middle, tên.upper, tên.lower    |
| `MACD`                  | Một cột giá của trade_data/market_data        | `fast_period`,`slow_period`,`signal_period`: fast < slow | tên.line, tên.signal, tên.histogram |
| `MFI`                   | `"trade_data"`hoặc`"market_data"`, đủ HLCV | `period`: nguyên dương                                                                                  | Tên chỉ báo                         |

Ví dụ v1: SMA20, EMA5, BB(20,2), MACD(12,26,9), MFI14. Keyword
MACD Line = EMA nhanh − EMA chậm; Signal = EMA của MACD Line;
Histogram = MACD Line − Signal. Signal và Histogram chưa có giá trị khi
chưa đủ mẫu khởi tạo Signal; điều kiện dùng chúng chưa đánh giá được.

- JSON mới không khai báo `histogram`; đây là đầu ra, không phải cách vẽ.
- Trường cũ `histogram: "line"` vẫn được nhận để tương thích đầu vào,
  nhưng luôn dùng công thức Histogram đã sửa, không khôi phục công thức cũ.
- Chạy lại payload dùng `macd.histogram` có thể đổi tín hiệu và kết quả.
  Kết quả đã lưu không tự tính lại; biểu đồ dựng lại dùng công thức hiện tại.

## 6. Điền entry

Mô tả: điều kiện mở vị thế sau Close. Các giá trị bên dưới là của mẫu v1.

**Trường bắt buộc theo từng trường hợp:**

- `conditions`: Các nhánh `BUY` cho mô hình chuẩn hóa hoặc `LONG`,`SHORT` cho
  mô hình hợp đồng; mỗi nhánh là cây điều kiện.
- `details`: Tùy chọn; các giá trị cần giữ từ lúc phát tín hiệu mở để dùng khi
  thoát. Ví dụ `"pivot": {"ref": "pivot", "shift": 1}` được đọc lại bằng
  `position.entry_pivot` sau khi lệnh BUY khớp.
- `any`:`["LONG", "SHORT"]`; tên phải có trong conditions.
- `require_flat`(cho v1):`true `: chỉ vào khi không có vị thế.
- `require_no_pending`(cho v1):`true `: không có lệnh chờ.
- `reentry`(cho v1): Chỉ`"next_bar_close_after_exit"` trong thiết kế này.
- `pending` (cho v1): Object quy tắc lệnh chờ bên dưới.
- `signal_windows`(khi giới hạn giờ): Mảng cặp`HH:MM `, gồm hai đầu; v1 09:05–11:20 và 13:05–14:00.
- `on_conflict`(khi có cả hai hướng): Chỉ`"SIGNAL_CONFLICT"`: hai hướng cùng đạt thì không giao dịch.
- `pending.max_execution_bars`(khi có pending): Số nguyên dương; v1`1 `.
- `pending.cross_lunch`(khi có pending): Boolean; v1`false `.
- `pending.cross_cutoff`(khi có pending): Boolean; v1`false `.
- `pending.cross_session`(khi có pending): Boolean; v1`false `.

## 7. Điền exit

Mô tả: mức giá, điều kiện và thứ tự thoát vị thế.

**Trường bắt buộc theo từng trường hợp:**

- `allow_overnight`(cho v1):`false `.
- `targets`(khi có target_touch): Với v1 có`LONG `và`SHORT `, mỗi hướng có`TP1 `,`TP2 ` là cây trả mức giá.
- `intrabar` (khi stop/target trong nến): V1 phải có; điều kiện là các hành động ở bảng dưới.
- `bar_close` (khi thoát theo điều kiện tại close): V1 phải có; conditions chứa các cây đúng/sai.
- `flat_by`(khi hạn hết vị thế): Giờ`HH:MM `; v1`"14:30"`.

Trong mỗi nhóm intrabar/bar_close:

**Trường bắt buộc theo từng trường hợp:**

- `conditions` : Tên điều kiện → định nghĩa; tên thoát là nhãn để tham chiếu.
- `any` : Danh sách tên có trong conditions, không rỗng.
- `bar_close.quantity`:`"remaining"` trong mẫu hiện tại.
- `bar_close.fill_policy`: Chỉ`"next_open"` trong mẫu hiện tại.
- `priority` (khi có nhiều điều kiện có thể cùng đạt): Liệt kê các tên trong any theo thứ tự xử lý, không trùng/thiếu.

V1: intrabar ưu tiên PROTECTIVE_STOP → TP1 → TP2; bar_close ưu tiên
MARGIN_BREACH → FORCED_EXIT → TIME_STOP.

### Hành động trong intrabar.conditions

**Trường bắt buộc theo từng trường hợp:**

- `type`: `"protective_stop"` hoặc`"target_touch"`.
- `quantity`:`"remaining"` hoặc object chia số lượng dưới đây.
- `distance_points`(với protective_stop): Số dương; v1`6 `, đơn vị điểm.
- `level`(với target_touch):`"TP1"`hoặc`"TP2"`, phải có trong targets của hướng đang giữ.
- `requires`(khi phụ thuộc khớp trước): Mẫu chỉ có`"TP1_filled"` ở TP2; TP1 bỏ trường này.

**Trường tùy chọn:**

- `trailing` (tùy chọn cho stop).

**Vị trí:** `strategy.exit.intrabar.conditions.TP1.quantity`.
**Trường:** cả ba trường đều bắt buộc khi chọn quantity dạng object:

| Trường                   | Điền gì?                   |
| -------------------------- | ----------------------------- |
| `if_initial_quantity_eq` | Số nguyên dương           |
| `then`                   | `"remaining"`               |
| `else`                   | Cây trả số lượng nguyên |

Cấu trúc này chỉ chọn lượng TP theo số hợp đồng ban đầu.

### Các trường trailing khi khai báo

**Vị trí:** `strategy.exit.intrabar.conditions.PROTECTIVE_STOP.trailing`.
**Trường bắt buộc:**

| Trường            | Keyword / giá trị v1         |
| ------------------- | ------------------------------ |
| `activate_after`  | Chỉ`"TP1_fill"`             |
| `distance_points` | Số dương, v1`6`           |
| `seed`            | Chỉ`"TP1_price"`            |
| `extrema_from`    | Chỉ`"bar_after_TP1"`        |
| `update_at`       | Chỉ`"bar_close"`            |
| `effective_from`  | Chỉ`"next_bar"`             |
| `combine`         | Chỉ`"tightest"`             |
| `allow_widening`  | `false`trong thiết kế này |

Trailing bắt đầu lấy cực trị từ nến sau TP1.

## 8. sizing và daily_limits

**Vị trí:** `strategy.sizing`và`strategy.daily_limits`.
**Mô tả:** tính số hợp đồng và giới hạn mở mới trong ngày.

**Trường bắt buộc theo từng trường hợp:**

- `type`: `"risk_and_margin"` cho mô hình hợp đồng hoặc `"fixed_fractional"`
  cho mô hình chuẩn hóa.
- `risk_fraction`: Tỷ lệ > 0 và <= 1; v1`0.01 ` = 1%.
- `stop_points`: Số dương, v1`6 `; phải khớp stop ban đầu để tính rủi ro.
- `margin_buffer`: Hệ số dự phòng ký quỹ, >= 1; mẫu v1 dùng `1.10`.
- `max_contracts` : Số hợp đồng được giữ tối đa.
- `pyramiding`(cho v1):`false `, không thêm vào vị thế.`daily_limits`khi có phải chứa`stop_new_entry`, giá trị là cây điều kiện.

Với `fixed_fractional`, điền `risk_fraction` và `stop_loss_fraction`. Số lượng
bằng phần nguyên của vốn chịu rủi ro chia rủi ro trên một đơn vị, sau đó giới
hạn tiếp bởi số lượng mua được sau phí.

- V1 ngừng mở mới khi P/L ròng ngày ≤ −2% vốn đầu ngày hoặc đã có 3 lần khớp mở.
- Vị thế đang giữ tiếp tục được quản trị theo quy tắc thoát.

## 9. execution — cách khớp lệnh

Mô tả: cách khớp lệnh mở và trượt giá.

| Trường execution         | Yêu cầu trong mẫu                                                                   |
| -------------------------- | -------------------------------------------------------------------------------------- |
| `entry_fill_policy`      | Tương thích JSON cũ; cấu hình mới dùng `strategy.entry.order`/`actions`    |
| `slippage_rate`          | Bắt buộc                                                                             |
| `matching_model`         | `next_open` (mặc định khi bỏ trống) hoặc `hnx_sessions_v1` cho ATO/LO/ATC    |
| `auction_match_quantity` | Không bắt buộc; số nguyên không âm, giới hạn cố định lượng khớp ATO/ATC |

Thứ tự xử lý, giá gap, bước giá, phí/ký quỹ và lịch theo [tài liệu thực thi v1](canslim-v1-execution-accounting.md).

**Ví dụ:**

```json
{"execution": {"entry_fill_policy": "next_open", "slippage_rate": "0"}}
```

- ATO theo JSON cũ: `entry_fill_policy: "ato"`; xét lúc 08:45, tính lượng từ Close liên tục gần nhất, khớp Open 09:00.
- ATC theo JSON cũ: `strategy.exit.bar_close.fill_policy: "atc"`; khớp Close bản ghi 14:45.
- Bỏ `auction_match_quantity`: giả định khớp đủ. Đặt `2`: mỗi lệnh khớp tối đa 2 hợp đồng.
- Giới hạn lượng là tham số mô phỏng. Xem [khớp theo phiên HNX](hnx-session-matching.md).

### 9.1. Chọn lệnh trong chiến lược

Payload đầy đủ để nạp lên web hoặc gửi API:

- [LO tự lấy dữ liệu](../examples/orders/lo-auto.json).
- [ATO/ATC giới hạn lượng khớp](../examples/orders/ato-atc-partial-auto.json): thời hạn theo phiên đấu giá.

Các đoạn dưới là phần cấu hình để thay trong payload hiện có. Giữ điều kiện, ngưỡng, dữ liệu và cách tính tiền.

- Với `next_open`, thay `execution.entry_fill_policy: "next_open"` bằng `strategy.entry.order: {"type":"SIMULATED"}`.
- Nhóm đóng: thay `bar_close.fill_policy: "next_open"` bằng `bar_close.order` cùng giá trị.
- `execution.matching_model` chọn cách khớp; `SIMULATED` giữ cơ chế mô phỏng tại Open kế tiếp.

Ví dụ LO: chọn `execution.matching_model: "hnx_sessions_v1"`, bỏ
`entry_fill_policy: "limit"` và chuyển `entry.limit_price` vào `order`:

```json
{"order":{"type":"LO","limit_price":{"ref":"trade_data.close"},"pending":{"max_execution_bars":2,"cross_lunch":false,"cross_cutoff":false,"cross_session":false}}}
```

Ví dụ ATO mở / ATC đóng riêng, cùng model HNX: nhóm `entry` dùng
`"order":{"type":"ATO"}`; nhóm `exit.bar_close` dùng cấu hình dưới đây,
giữ các điều kiện và thứ tự ưu tiên đã được chọn:

```json
{"order":{"type":"ATC"},"quantity":"remaining"}
```

- ATO/ATC dùng thời hạn cố định của phiên; cấu hình chỉ chứa loại lệnh.
- JSON cũ dùng HNX cùng `next_open`: giữ model HNX và đổi loại lệnh sang `SIMULATED`.

Để nhánh A/B chọn lệnh riêng, thêm vào nhóm `entry`:

```json
{
  "actions": {
    "A": {"side":"LONG","order":{"type":"LO","limit_price":{"ref":"trade_data.close"}}},
    "B": {"side":"LONG","order":{"type":"ATO"}}
  },
  "any": ["A","B"],
  "priority": ["A","B"]
}
```

- `conditions` cần đúng nhãn A/B; mỗi nhánh dùng `all`/`any`.
- ATO xét lúc 08:45; LO trong phiên liên tục.
- MTL/MOK/MAK xem mục 9.2.

Để đặt nhiều nhánh cùng đúng:

- Dùng contract/HNX, `sizing.pyramiding: true` và lệnh mở LO/ATO/MTL/MOK/MAK.
- Bỏ `on_conflict`, `require_flat: true`, `require_no_pending: true`.
- Hạn mức gồm lượng đang giữ và mở đang chờ; nhánh sau nhận phần còn đủ.
- Chỉ bổ sung cùng hướng. Mỗi lần mở giữ giá vốn, stop/TP và thời gian riêng.
- Lệnh đóng `remaining` áp dụng cho phần đang xét. Xem [API mục 3.4](backtest-api-specification.md#34-execution).

### 9.2. MTL/MOK/MAK với lượng đối ứng cố định

[market-fixed.json](../examples/orders/market-fixed.json) dùng dữ liệu tổng hợp:

- MTL đặt mở 5, khớp 2+2+1.
- Hai tín hiệu MAK đóng lần lượt 2 và 2; còn 1 hợp đồng cuối kỳ.
- Mỗi MAK hủy dư ngay sau lần thử khớp.
- Chọn `execution.matching_model: "hnx_sessions_v1"`, `execution.continuous_match_quantity: 2` và accounting contract.
- Cung cấp `trade_data.price_limits` có nguồn; dữ liệu tự lấy hiện thiếu bảng này.
- Mở/đóng khai báo `order.type`: `MAK`, `MOK` hoặc `MTL`.
- MTL có `pending` cho LO dư; đổi sang MAK/MOK phải xóa `pending`. Giá khớp do bộ khớp xác định.
- Giá dự kiến tính lượng là Close đã hoàn tất; thử khớp ở Open liên tục kế tiếp cùng buổi.
- MTL chuyển dư sang LO nhưng chỉ xét LO từ nến sau chuyển đổi.
- Lượng cố định dùng chung mỗi nến/hợp đồng, không phải volume thị trường.
- Xem [quy tắc phiên](hnx-session-matching.md#7-đặc-tả-mtlmokmak--a01).

## 10. Kiểm tra trước khi gửi

1. JSON đúng cú pháp, không dùng dấu ba chấm hoặc chú thích trong JSON gửi chạy.
2. Mỗi chỉ báo có type/source và đủ tham số theo type; mọi ref có nguồn rõ ràng.
3. Mỗi phép toán đủ toán hạng và đúng kiểu; all/any không chứa cây trả số.
4. Tên trong any/priority tồn tại; không dùng ref vị thế ở entry khi chưa có vị thế.
5. Chỉ dùng dữ liệu đã khả dụng; đủ lịch sử VNINDEX và đúng mã hợp đồng.
6. Mẫu v1 giữ 150 nến tính cả t và tối đa 5 hợp đồng; kỳ báo cáo phải nằm trong dữ liệu thực có.
7. Bổ sung lịch sử cho mẫu hai nến trước khi chạy CANSLIM v1.
