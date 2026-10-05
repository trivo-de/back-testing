# Hướng dẫn điền cây công thức và payload chiến lược

Cập nhật: 28/09/2026. Đọc cùng [đặc tả API](backtest-api-specification.md)
và [payload minh họa](../../data/payload.json).
U03 đã triển khai kiểm tra cấu trúc tại `POST /api/backtests/validate`.
U05/U06 đã nối payload mới vào tiếp nhận dữ liệu/lưu kết quả. Bộ thực thi
strategy JSON đã nối ở U08 (29/09); trạng thái `STRUCTURE_VALID` không có nghĩa
đã đủ lịch sử. Khi chạy, thiếu chỉ báo tại nến nào thì nến đó không tạo entry.
Các giá trị v1 lấy từ [quy tắc đã chốt](../strategies/canslim-v1-rules.md).
Không phải ngôn ngữ biểu diễn mọi chiến lược chứng khoán: chỉ sử dụng các
chỉ báo, phép toán và hành động được liệt kê dưới đây.

## 1. Đọc bảng và điền theo thứ tự nào?

- **Bắt buộc**: phải có trong nhóm đang khai báo.
- **Bắt buộc khi…**: điều kiện cần field được ghi ngay trong mô tả param.
- **Tùy chọn**: có thể bỏ; bảng ghi cách xử lý khi bỏ.
- Keyword phân biệt hoa/thường. `true`/`false`là boolean JSON, không viết`"true"`/`"false"`. Tên tự đặt khác với keyword cố định.

Điền dữ liệu → khai báo chỉ báo → viết điều kiện entry → viết exit → điền
sizing/giới hạn ngày → cấu hình khớp và tiền. Sau đó đối chiếu mọi `ref` và
tên điều kiện. Không cần lưu mẫu hoặc cung cấp strategy_id trước.

## 2. Tham chiếu

**Tham chiếu là lấy giá trị từ phần dữ liệu hoặc chỉ báo đã khai báo trong
payload.** Ví dụ đã nhập dữ liệu vào `trade_data`, muốn lấy cột`close` thì
ghi `trade_data.close`: **tên nhóm dữ liệu + dấu chấm + tên cột**.

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

Đọc là: tính SMA20 từ Close đã nhập, rồi so Close với kết quả SMA20. Thứ tự các khóa
JSON không ảnh hưởng tham chiếu; chỉ cần có khai báo trong cùng payload.

Riêng `position`,`account`,`day`,`clock` trong bảng dưới là giá trị engine
tính trong lúc chạy, không lấy trực tiếp từ field đã gửi. Ví dụ
`position.entry_price` là giá khớp mở vị thế, chỉ có sau khi lệnh mở đã khớp.

| Tham chiếu được dùng                                      | Ý nghĩa                                    |
| -------------------------------------------------------------- | -------------------------------------------- |
| `trade_data.open`,`.high`,`.low`,`.close`,`.volume`  | OHLCV chuỗi giao dịch                      |
| `market_data.open`,`.high`,`.low`,`.close`,`.volume` | OHLCV VNINDEX                                |
| `sma20`,`ema5`,`mfi14`                                   | Một giá trị chỉ báo                     |
| `bb.middle`,`bb.upper`,`bb.lower`                        | Ba đầu ra BB                               |
| `macd.line`,`macd.signal`,`macd.histogram`               | Các đầu ra MACD                           |
| `position.entry_price`                                       | Giá khớp vào thực tế                    |
| `position.entry_<tên>`                                       | Giá trị lưu từ `entry.details.<tên>` khi tạo tín hiệu mở; ví dụ `position.entry_pivot` |
| `position.initial_quantity`                                  | Số hợp đồng lúc mở vị thế            |
| `position.held_bars`                                         | Số nến giữ vị thế                       |
| `account.equity`                                             | Giá trị tài khoản tại thời điểm xét |
| `account.required_margin`                                    | Ký quỹ yêu cầu hiện tại                |
| `day.net_pnl`                                                | P/L ròng ngày theo quy tắc tài khoản v1 |
| `day.start_equity`                                           | Giá trị tài khoản đầu ngày            |
| `day.entry_fill_count`                                       | Số lần khớp mở vị thế trong ngày      |
| `clock.local_time`                                           | Giờ tại thời điểm đánh giá           |

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

Toán hạng số có thể là số hữu hạn JSON, một ref số hoặc một cây phép toán số.
Chuỗi `"14:20"` dùng riêng khi so sánh với giờ, không dùng để cộng/trừ.
Giá trong bars và các trường tiền có thể là chuỗi thập phân theo payload;
trong cây công thức dùng số JSON như `6`,`0.01`. Bộ đọc phải giữ độ chính xác
thập phân, không đi qua float để tính tiền. Không chấp nhận chia 0 hoặc tự đổi
kết quả không hợp lệ thành 0. Không dùng phép số học với boolean.

Trong `all`/`any`, chuỗi tên chỉ hợp lệ khi có conditions trong nhóm bao ngoài
để tra tên. Không tra sang nhóm entry/exit khác; không cho tham chiếu vòng.
`eq`,`not`,`cross_over`, hàm Python hoặc chuỗi`"close > sma20"` chưa thuộc
bộ keyword này; không tự hiểu chúng như phép toán đã hỗ trợ.

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

**Bổ sung 02/10/2026:** `auto_fetch_data` là boolean, mặc định `false`.
Khi `true`, phải bỏ `trade_data`/`market_data`; máy chủ tải VN30F1M và VNINDEX
5 phút từ endpoint cố định. Các yêu cầu nhập thủ công dưới đây vẫn áp dụng khi
tắt. Xem [luồng tự tải dữ liệu](auto-fetch-data.md).

**Params bắt buộc:**

- `trade_data`: Lịch sử giá và khối lượng của mã đem giao dịch, dùng tính chỉ báo, xét tín hiệu và mô phỏng khớp lệnh.
- `strategy`: Quy tắc giao dịch: dùng chỉ báo nào, khi nào mở/đóng vị thế, vào bao nhiêu hợp đồng và giới hạn rủi ro.
- `execution`: Cách mô phỏng khớp lệnh, gồm thời điểm khớp và mức trượt giá (chi tiết mục 9).
- `initial_cash`: Số vốn ban đầu của tài khoản backtest. Ví dụ v1: 100.000.000 đồng.
- `accounting`: Các thông số tính P/L, ký quỹ, thuế và phí; điền theo nhóm accounting bên dưới. Vốn ban đầu vẫn nằm ngoài nhóm này.

**Định dạng nhập:** trade_data, strategy, execution, accounting là object JSON;
initial_cash là chuỗi số thập phân, ví dụ `"100000000"`.

**Params tùy chọn:**

- `report`: report trên start_date/end_date dạng`YYYY-MM-DD `;
- `market_data`: Lịch sử VNINDEX để đánh giá thị trường chung nếu chiến lược có điều kiện tham chiếu chỉ số này. Khi có source/ref trỏ tới market_data thì phải gửi; nếu không dùng thì bỏ hoặc null.

**Chỉ báo v1 lấy dữ liệu ở đâu?** Theo quyết định cập nhật, SMA20, EMA5,
BB và MACD lấy `market_data.close`; MFI14 lấy HLCV trong `market_data`.
Các so sánh Close với SMA/BB ở entry cũng lấy VNINDEX. Vì vậy market_data
bắt buộc khi chạy v1. Các ví dụ trade_data.close ở mục tham chiếu chỉ minh
họa cú pháp chung, không phải nguồn của chỉ báo entry v1 nữa.
TP1/TP2 cách giá khớp vào 6/12 điểm theo hướng vị thế;
giá khớp, stop, trailing và P/L đều dùng giá hợp đồng.

### accounting — tính tiền, ký quỹ, thuế và phí

**Vị trí:** `accounting` ngoài cùng, cùng cấp với `initial_cash` và `strategy`.
Các field dưới đây chỉ nhập trong accounting, không lặp lại ở ngoài cùng.

**Param bắt buộc để chọn cách tính tiền:**

- `model`: `"normalized"` cho mô hình tiền v0 hoặc `"contract"` cho hợp đồng v1.

Với `model: "normalized"`, điền `fee_rate` là tỷ lệ phí trên giá trị mỗi lượt
khớp. Với `model: "contract"`, các param bắt buộc là:

- `margin_rate`: Tỷ lệ ký quỹ, điền `"0.17"` = 17%, cố định toàn kỳ.
- `pit_rate`: Thuế suất thu nhập cá nhân, điền `"0.001"` = 0,1% trên cơ sở
  tính thuế; không phải tổng tỷ lệ phí trên toàn giá trị hợp đồng.
- `exchange_fee_per_contract`: Phí sàn mỗi hợp đồng khớp mỗi lượt, điền `"2700"` đồng.
- `clearing_fee_per_contract`: Phí bù trừ mỗi hợp đồng mỗi lượt, điền `"2550"` đồng.
- `broker_fee_per_contract`: Phí môi giới mỗi hợp đồng mỗi lượt, mẫu điền
  `"0"`. Giá trị 0 chỉ bỏ phí môi giới, không bỏ các phí/thuế khác.

**Param tùy chọn:**

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

Theo công thức v1: tax_base = giá khớp × contract_multiplier × số hợp đồng
× margin_rate / 2; PIT = tax_base × pit_rate. Mỗi khoản phí theo hợp đồng
nhân với số hợp đồng khớp trong lượt đó; mở và đóng là hai lượt riêng.
Các mức trên là cấu hình mô phỏng lấy từ tài liệu v1 hiện tại.
`account.equity` trong cây điều kiện vẫn là trạng thái engine tính ra;
không đổi thành `accounting.equity`. Đầu vào mới đã được kiểm tra cấu trúc;
U08 đã nối cây quy tắc vào engine; U06 lưu/đọc kết quả hợp đồng.

### trade_data / market_data

các nến đầu vào; field bars[].close là close trong từng phần tử bars.

**Params bắt buộc:**

- `resolution`: Timeframe. `"5"`= 5 phút;`"D"`= ngày hỗ trợ.
- `bars` : Mảng nến có thứ tự thời gian.
- `bars[].time` : Số nguyên Unix tại lúc mở nến.
- `bars[].open`, `bars[].high`, `bars[].low`, `bars[].close` : Mỗi trường là chuỗi giá thập phân hữu hạn, OHLC hợp lệ.
- `bars[].volume` (khi dùng mfi/quy tắc khối lượng): Số không âm.
- `trade_data.contract_map` (khi tách hợp đồng v1): Bảng ánh xạ theo data contract, không tự suy từ OHLCV.

**Params tùy chọn:**

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

**Params bắt buộc (trường hợp áp dụng ghi tại từng field):**

- `entry`,`exit` : Theo mục 6–7.
- `indicators` (khi quy tắc dùng chỉ báo): Object chứa các khai báo như sma20, ema5, bb
- `sizing` (khi mở vị thế có số lượng): V1 dùng risk_and_margin; không có quy tắc ngầm mua 1 hợp đồng.

**Params tùy chọn:**

- `warmup_bars`: Số nến lịch sử tối thiểu của chuỗi chỉ báo (VNINDEX đối với v1) mà chiến lược yêu cầu trước khi được xét mở vị thế, tính cả nến đang xét đã đóng. V1 điền 150. Nếu bỏ, không áp thêm ngưỡng số nến riêng từ field này; chỉ xét khi các chỉ báo được dùng đã có giá trị hợp lệ.
- `daily_limits`.

Mọi chỉ báo cần `type`và`source`. Dưới đây là các loại đã có schema kiểm tra;
SMA/EMA/BB/MACD/MFI/HIGHEST/LOWEST đã có hàm tính trong `domain/indicators.py`:

| type (keyword cố định) | source được dùng                              | Tham số phải điền                                                                                        | Đầu ra để ref                          |
| ------------------------- | ------------------------------------------------- | ------------------------------------------------------------------------------------------------------------ | ------------------------------------------ |
| `SMA`                   | Một cột số OHLCV của trade_data/market_data   | `period`: số nguyên dương                                                                              | Tên chỉ báo                             |
| `HIGHEST` / `LOWEST`    | Một cột số OHLCV của trade_data/market_data   | `period`: số nguyên dương                                                                              | Tên chỉ báo                             |
| `EMA`                   | Một cột giá của trade_data/market_data        | `period`: số nguyên dương                                                                              | Tên chỉ báo                             |
| `BB`                    | Một cột giá của trade_data/market_data        | `period`,`stddev_multiplier` > 0                                                                         | tên.middle, tên.upper, tên.lower        |
| `MACD`                  | Một cột giá của trade_data/market_data        | `fast_period`,`slow_period`,`signal_period`: fast < slow;`histogram`: chỉ`"line"` trong mẫu này | tên.line, tên.signal, tên.histogram     |
| `MFI`                   | `"trade_data"`hoặc`"market_data"`, đủ HLCV | `period`: nguyên dương                                                                                  | Tên chỉ báo                             |

Ví dụ v1: SMA20, EMA5, BB(20,2), MACD(12,26,9), MFI14. Keyword
`histogram: "line"` nghĩa là histogram bằng MACD line theo quyết định v1.

## 6. Điền entry

Mô tả: điều kiện mở vị thế sau Close. Các giá trị bên dưới là của mẫu v1.

**Params bắt buộc (trường hợp áp dụng ghi tại từng field):**

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

**Params bắt buộc (trường hợp áp dụng ghi tại từng field):**

- `allow_overnight`(cho v1):`false `.
- `targets`(khi có target_touch): Với v1 có`LONG `và`SHORT `, mỗi hướng có`TP1 `,`TP2 ` là cây trả mức giá.
- `intrabar` (khi stop/target trong nến): V1 phải có; điều kiện là các hành động ở bảng dưới.
- `bar_close` (khi thoát theo điều kiện tại close): V1 phải có; conditions chứa các cây đúng/sai.
- `flat_by`(khi hạn hết vị thế): Giờ`HH:MM `; v1`"14:30"`.

Trong mỗi nhóm intrabar/bar_close:

**Params bắt buộc (trường hợp áp dụng ghi tại từng field):**

- `conditions` : Tên điều kiện → định nghĩa; tên thoát là nhãn để tham chiếu.
- `any` : Danh sách tên có trong conditions, không rỗng.
- `bar_close.quantity`:`"remaining"` trong mẫu hiện tại.
- `bar_close.fill_policy`: Chỉ`"next_open"` trong mẫu hiện tại.
- `priority` (khi có nhiều điều kiện có thể cùng đạt): Liệt kê các tên trong any theo thứ tự xử lý, không trùng/thiếu.

V1: intrabar ưu tiên PROTECTIVE_STOP → TP1 → TP2; bar_close ưu tiên
MARGIN_BREACH → FORCED_EXIT → TIME_STOP.

### Hành động trong intrabar.conditions

**Params bắt buộc (trường hợp áp dụng ghi tại từng field):**

- `type`: `"protective_stop"` hoặc`"target_touch"`.
- `quantity`:`"remaining"` hoặc object chia số lượng dưới đây.
- `distance_points`(với protective_stop): Số dương; v1`6 `, đơn vị điểm.
- `level`(với target_touch):`"TP1"`hoặc`"TP2"`, phải có trong targets của hướng đang giữ.
- `requires`(khi phụ thuộc khớp trước): Mẫu chỉ có`"TP1_filled"` ở TP2; TP1 bỏ trường này.

**Params tùy chọn:**

- `trailing` (tùy chọn cho stop).

**Vị trí:** `strategy.exit.intrabar.conditions.TP1.quantity`.
**Params:** cả ba trường đều bắt buộc khi chọn quantity dạng object:

| Trường                   | Điền gì?                   |
| -------------------------- | ----------------------------- |
| `if_initial_quantity_eq` | Số nguyên dương           |
| `then`                   | `"remaining"`               |
| `else`                   | Cây trả số lượng nguyên |

Không phải cú pháp if tổng quát.

### Các trường trailing khi khai báo

**Vị trí:** `strategy.exit.intrabar.conditions.PROTECTIVE_STOP.trailing`.
**Params bắt buộc:**

| Trường                                                                           | Keyword / giá trị v1         |
| ---------------------------------------------------------------------------------- | ------------------------------ |
| `activate_after`                                                                 | Chỉ`"TP1_fill"`             |
| `distance_points`                                                                | Số dương, v1`6`           |
| `seed`                                                                           | Chỉ`"TP1_price"`            |
| `extrema_from`                                                                   | Chỉ`"bar_after_TP1"`        |
| `update_at`                                                                      | Chỉ`"bar_close"`            |
| `effective_from`                                                                 | Chỉ`"next_bar"`             |
| `combine`                                                                        | Chỉ`"tightest"`             |
| `allow_widening`                                                                 | `false`trong thiết kế này |
| không tự thay thế cho nhau. Trailing không lấy High/Low của chính nến TP1. |                                |

## 8. sizing và daily_limits

**Vị trí:** `strategy.sizing`và`strategy.daily_limits`.
**Mô tả:** tính số hợp đồng và giới hạn mở mới trong ngày.

**Params bắt buộc (trường hợp áp dụng ghi tại từng field):**

- `type`: `"risk_and_margin"` cho mô hình hợp đồng hoặc `"fixed_fractional"`
  cho mô hình chuẩn hóa.
- `risk_fraction`: Tỷ lệ > 0 và <= 1; v1`0.01 ` = 1%.
- `stop_points`: Số dương, v1`6 `; phải khớp stop ban đầu để tính rủi ro.
- `margin_buffer` : .
- `max_contracts` : Số hợp đồng được giữ tối đa.
- `pyramiding`(cho v1):`false `, không thêm vào vị thế.`daily_limits`khi có phải chứa`stop_new_entry`, giá trị là cây điều kiện.

Với `fixed_fractional`, điền `risk_fraction` và `stop_loss_fraction`. Số lượng
bằng phần nguyên của vốn chịu rủi ro chia rủi ro trên một đơn vị, sau đó giới
hạn tiếp bởi số lượng mua được sau phí.

V1 dùng any của P/L ròng ngày <= −2% equity đầu ngày và số lần khớp mở >= 3.
Đạt giới hạn chỉ ngừng mở mới, vẫn quản trị vị thế đang giữ. Không cần gửi
`manage_existing_position` để bật hành vi này.

## 9. execution — cách khớp lệnh

Mô tả: cách khớp lệnh mở và trượt giá.

| Trường execution | Yêu cầu trong mẫu |
| ------------------ | -------------------- |
| `entry_fill_policy`  | Bắt buộc           |
| `slippage_rate`  | Bắt buộc           |

Chưa có keyword để tự chọn mọi loại lệnh/thời điểm khớp. Định nghĩa hiện tại
vẫn phải thực thi đúng thứ tự xử lý, giá gap stop/target, làm tròn bước giá,
phí/ký quỹ và lịch trong [tài liệu thực thi v1](canslim-v1-execution-accounting.md).

**Ví dụ:**

```json
{"execution": {"entry_fill_policy": "next_open", "slippage_rate": "0"}}
```

## 10. Kiểm tra trước khi gửi

1. JSON đúng cú pháp, không dùng dấu ba chấm hoặc chú thích trong JSON gửi chạy.
2. Mỗi chỉ báo có type/source và đủ tham số theo type; mọi ref có nguồn rõ ràng.
3. Mỗi phép toán đủ toán hạng và đúng kiểu; all/any không chứa cây trả số.
4. Tên trong any/priority tồn tại; không dùng ref vị thế ở entry khi chưa có vị thế.
5. Không đọc nến tương lai; đủ lịch sử VNINDEX và dữ liệu khớp đúng hợp đồng.
6. V1 giữ 150 nến tính cả t, tối đa 5 hợp đồng và kỳ báo cáo sáu tháng.
7. Hai nến minh họa chưa đủ lịch sử chạy thật; contract_map đã được điền.
