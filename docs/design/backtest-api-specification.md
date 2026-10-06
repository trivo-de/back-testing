# Đặc tả API backtest

## 1. Tổng quan

API nhận dữ liệu giá và định nghĩa chiến lược bằng JSON để kiểm tra đầu vào,
mô phỏng giao dịch và trả kết quả backtest. Người gọi không cần đăng ký bộ
dữ liệu hoặc mẫu chiến lược trước khi chạy.

Tài liệu dành cho người chuẩn bị request, tích hợp API và kiểm tra kết quả.
Luồng sử dụng: chuẩn bị dữ liệu → kiểm tra request → chạy → đọc kết quả.
Hai endpoint POST dùng cùng cấu trúc request.

- Chỉ dùng dữ liệu đã khả dụng tại thời điểm quyết định.
- Tín hiệu sau Close chỉ khớp tại Open kế tiếp theo quy tắc thực thi.
- Tín hiệu, lệnh, lần khớp và giao dịch đã đóng là các đối tượng khác nhau.
- Không tự tải hoặc điền dữ liệu giá bị thiếu.
- `accounting.model` chọn mô hình tính tiền; symbol không chọn chiến lược.

Quy tắc CANSLIM thuộc [quy tắc v1](../strategies/canslim-v1-rules.md) và
[quy tắc normalized](../strategies/canslim-rules.md). Quy ước nguồn, phiên và
đáo hạn thuộc [hợp đồng dữ liệu](../data/vn30f1m/data-contract-v1.md).
Các ví dụ dưới đây không thay đổi quy tắc đã chốt.

## 2. Endpoint

Request dùng `Content-Type: application/json`; response trả JSON.
Đường dẫn tính từ địa chỉ máy chủ API.

### 2.1. POST /api/backtests

Kiểm tra, chạy backtest đồng bộ và lưu kết quả. HTTP 201 chỉ được trả khi
chạy và lưu thành công.

| Thuộc tính   | Giá trị                              |
| -------------- | -------------------------------------- |
| Phương thức | `POST`                               |
| Đường dẫn  | `/api/backtests`                     |
| Body           | Một đối tượng JSON theo mục 3    |
| Thành công   | `201 Created`, kết quả theo mục 8 |
| Lỗi           | `422` hoặc `503`, xem mục 7      |

### 2.2. POST /api/backtests/validate

Kiểm tra cấu trúc, dữ liệu, tham chiếu và tổ hợp thực thi.

| Thuộc tính   | Giá trị                                     |
| -------------- | --------------------------------------------- |
| Phương thức | `POST`                                      |
| Đường dẫn  | `/api/backtests/validate`                   |
| Body           | Cùng cấu trúc với endpoint chạy          |
| Thành công   | `200 OK`, kết quả kiểm tra theo mục 8.1 |
| Lỗi           | `422` hoặc `503`, xem mục 7             |

Lưu ý:

- `STRUCTURE_VALID` không bảo đảm mọi nến đủ lịch sử chỉ báo, có giao dịch hoặc
  mô phỏng không gặp lỗi thực thi.
- `runnable` cho biết máy chủ có bộ chạy chiến
  lược, không phải kết luận mọi điều kiện vào lệnh đánh giá được.

### 2.3. Đọc kết quả đã lưu

| Endpoint                              | Nội dung khi thành công                                          |
| ------------------------------------- | ------------------------------------------------------------------- |
| `GET /api/backtests`                | Danh sách các lần chạy thành công theo thứ tự kho lưu trữ |
| `GET /api/backtests/{run_id}`       | Kết quả một lần chạy                                           |
| `GET /api/backtests/{run_id}/input` | Đầu vào đầy đủ và thông tin chính sách đã lưu         |
| `GET /api/backtests/{run_id}/chart` | Dữ liệu biểu đồ của lần chạy                                |

`run_id` là UUID. Các endpoint đọc không chạy lại chiến lược. Lần chạy thất
bại hoặc đang chạy không có trong danh sách thành công: đọc chi tiết trả 404.

## 3. Cấu trúc request

**Payload nhận một JSON object với các trường chính dưới đây.**
Tên trường và từ khóa phân biệt hoa/thường. Trường ngoài cấu trúc cho phép sẽ bị từ chối và trả lỗi 422.

| Nhóm            | Kiểu JSON        | Bắt buộc                                  | Nội dung                                                      |
| ---------------- | ----------------- | ------------------------------------------- | -------------------------------------------------------------- |
| `trade_data`   | object            | Có                                         | Chuỗi giá dùng giao dịch                                   |
| `market_data`  | object hoặc null | Khi được chỉ báo/biểu thức sử dụng | Chuỗi thị trường tham chiếu                               |
| `strategy`     | object            | Có                                         | Chỉ báo, vào/thoát lệnh, số lượng và giới hạn ngày |
| `execution`    | object            | Có                                         | Cách khớp và trượt giá                                   |
| `accounting`   | object            | Có                                         | Mô hình tính tiền và phí                                 |
| `initial_cash` | số thập phân   | Có                                         | Vốn ban đầu, lớn hơn 0                                    |
| `report`       | object hoặc null | Không                                      | Khoảng ngày báo cáo                                        |

### 3.1. trade_data

Chuỗi OHLCV của mã giao dịch. Các trường cũng áp dụng cho market_data.

| Trường           | Kiểu       | Bắt buộc | Mặc định khi bỏ    | Ý nghĩa/ràng buộc                                                              |
| ------------------ | ----------- | ---------- | ---------------------- | ---------------------------------------------------------------------------------- |
| `bars`           | array       | Có        | —                     | Mảng nến không rỗng, tăng dần theo thời gian                                |
| `resolution`     | string      | Không     | `"5"`                | `"5"`: 5 phút; `"D"`: ngày                                                   |
| `symbol`         | string/null | Không     | null                   | Nhãn mã, không chọn quy tắc                                                   |
| `timestamp_unit` | string      | Không     | `"s"`                | `"s"`: giây; `"ms"`: mili giây                                               |
| `timezone`       | string      | Không     | `"Asia/Ho_Chi_Minh"` | Tên múi giờ IANA hợp lệ                                                       |
| `price_unit`     | string/null | Không     | null                   | Nhãn đơn vị, không tự nhân/chia giá                                        |
| `contract_map`   | array       | Không     | `[]`                 | Bảng mã và ngày đáo hạn khi dữ liệu thuộc dạng chứng khoán phái sinh |

**Mỗi phần tử bars:**

| Trường                               | Kiểu                       | Bắt buộc            | Ý nghĩa/ràng buộc                                             |
| -------------------------------------- | --------------------------- | --------------------- | ----------------------------------------------------------------- |
| `time`                               | integer                     | Có                   | Unix tại lúc mở nến, theo timestamp_unit                      |
| `open`, `high`, `low`, `close` | số/chuỗi thập phân      | Có                   | Mỗi giá hữu hạn, lớn hơn 0                                  |
| `volume`                             | số/chuỗi thập phân/null | Khi được sử dụng | Không âm; bắt buộc cho MFI hoặc tham chiếu volume           |
| `close_time`                         | integer/null                | Với nến ngày       | Thời điểm đóng; nến 5 phút bỏ thì bằng time + 300 giây |
| `available_at`                       | integer/null                | Với nến ngày       | Thời điểm khả dụng; nến 5 phút bỏ thì bằng close_time   |

Dữ liệu OHLC được xem là hợp lệ khi thỏa các điều kiện sau:

- `low <= min(open, close) <= max(open, close) <= high`.
- `time < close_time <= available_at`, không trùng, đảo thứ tự hoặc chồng lấn.
- Có `close_time` và `available_at` (đối với chứng khoán cơ sở).
- Timestamp đúng format Unix tuyệt đối.

**Mỗi phần tử contract_map:**

| Trường | Kiểu | Bắt buộc | Ý nghĩa |
| --- | --- | --- | --- |
| `contract_code` | string | Có | Mã xác định hợp đồng tương lai theo kỳ đáo hạn. Ví dụ `VN30F2603` là hợp đồng tương lai VN30 đáo hạn tháng 03/2026. |
| `expiry_date` | string ngày | Có | Ngày đáo hạn của hợp đồng, tức ngày giao dịch cuối cùng của hợp đồng đó. Định dạng `YYYY-MM-DD`. |
| `expiry_unix` | integer | Có | Mốc thời gian Unix tính bằng giây biểu diễn ngày đáo hạn, giúp hệ thống đối chiếu với thời gian của các nến để xác định hợp đồng tương ứng. |

Khi có bảng, API đối chiếu lịch phiên máy chủ, nến thiếu lưu vào field `data_gaps`. Chi tiết theo hợp đồng dữ liệu v1.

Ngoài bars dạng mảng nến, API nhận mảng cột `t/o/h/l/c/v` tại nhóm dữ liệu,
trong `raw`, hoặc trong `bars` dạng object. Các mảng phải không rỗng, bằng độ
dài, thời gian tăng dần; `s` nếu có phải là `"ok"`.  

Ví dụ **riêng nhóm dữ liệu**:

```json
{"trade_data":{"resolution":"5","t":[1773800100],"o":[1300],"h":[1302],"l":[1299],"c":[1301],"v":[1000]}}
```

### 3.2. market_data  

`market_data` chứa dữ liệu giá và khối lượng của chỉ số thị trường, chẳng hạn VNINDEX, để chiến lược đánh giá xu hướng thị trường chung trước khi mở vị thế trên mã giao dịch trong `trade_data`.  
`market_data` và `trade_data` có thể được nhận vào với khoảng thời gian và số nến khác nhau, do `market_data` phụ thuộc vào các chỉ báo mà yêu cầu về dữ liệu. Do đó, `market_data` được khuyến nghị  phải được đảm bảo để có đủ dữ liệu khởi tạo chỉ báo.
Tại quyết định t, chỉ lấy nến thị trường có available_at <= t.

### 3.3. strategy

| Trường                        | Kiểu                | Bắt buộc          | Khi bỏ                                       |
| ------------------------------- | -------------------- | ------------------- | --------------------------------------------- |
| `indicators`                  | object               | Khi dùng chỉ báo | `{}`                                        |
| `entry`, `exit`, `sizing` | object               | Có                 | —                                            |
| `daily_limits`                | object/null          | Không              | Không áp giới hạn ngày từ trường này |
| `warmup_bars`                 | integer dương/null | Không              | Không áp ngưỡng lịch sử bổ sung        |

warmup_bars đếm mẫu tối thiểu, gồm mẫu hiện tại đã đóng; không phải chu kỳ
chỉ báo. Chỉ báo vẫn cần đủ mẫu theo công thức. Ngưỡng xét trên chuỗi chỉ báo
sử dụng; nếu không có chỉ báo thì xét chuỗi được tham chiếu.
Khoảng thiếu dữ liệu hoặc đổi mã hợp đồng làm khởi tạo lại lịch sử của chính
chuỗi đó; đổi hợp đồng giao dịch không tự khởi tạo lại chỉ báo VNINDEX.
Cấu trúc chi tiết ở mục 5.

### 3.4. execution

| Trường              | Kiểu                  | Bắt buộc | Giá trị hỗ trợ                                |
| --------------------- | ---------------------- | ---------- | ------------------------------------------------- |
| `entry_fill_policy` | string                 | Có        | Chỉ`"next_open"`                               |
| `slippage_rate`     | số/chuỗi thập phân | Có        | Từ 0 đến dưới 1; contract hiện chỉ nhận 0 |

next_open chờ Open kế tiếp sau Close tạo tín hiệu. Với nến liền nhau, hai
mốc có thể cùng timestamp nhưng là hai sự kiện theo thứ tự; không khớp bằng
Open của nến đã dùng quyết định. Normalized điều chỉnh mua lên/bán xuống
theo tỷ lệ trượt giá. Stop/target trong nến có quy tắc tại mục 5.3.

### 3.5. accounting

model bắt buộc: `"normalized"` hoặc `"contract"`. Chỉ truyền trường của mô
hình chọn, không trộn hai nhóm phí.

| Trường normalized | Kiểu                  | Bắt buộc | Ý nghĩa                                          |
| ------------------- | ---------------------- | ---------- | -------------------------------------------------- |
| `model`           | string                 | Có        | `"normalized"`                                   |
| `fee_rate`        | số/chuỗi thập phân | Có        | Không âm, phí trên giá trị mỗi lượt khớp |

Normalized dùng BUY, sizing fixed_fractional và thoát toàn bộ bằng SELL tại
Open sau điều kiện Close. Không hỗ trợ intrabar. Tiền theo đơn vị giá mô phỏng.

| Trường contract             | Kiểu                  | Bắt buộc | Mặc định  | Ý nghĩa/ràng buộc                         |
| ----------------------------- | ---------------------- | ---------- | ------------ | --------------------------------------------- |
| `model`                     | string                 | Có        | —           | `"contract"`                                |
| `contract_multiplier`       | số/chuỗi thập phân | Không     | `"100000"` | Hệ số điểm sang tiền, > 0                |
| `margin_rate`               | số/chuỗi thập phân | Có        | —           | Tỷ lệ ký quỹ, > 0 và <= 1                |
| `pit_rate`                  | số/chuỗi thập phân | Có        | —           | Thuế suất từ 0 đến 1                     |
| `exchange_fee_per_contract` | số/chuỗi thập phân | Có        | —           | Phí sàn mỗi hợp đồng/lượt, >= 0       |
| `clearing_fee_per_contract` | số/chuỗi thập phân | Có        | —           | Phí bù trừ mỗi hợp đồng/lượt, >= 0   |
| `broker_fee_per_contract`   | số/chuỗi thập phân | Có        | —           | Phí môi giới mỗi hợp đồng/lượt, >= 0 |

Contract mở LONG/SHORT, đóng CLOSE, dùng risk_and_margin; trade_data hiện
chỉ hỗ trợ resolution 5. Hệ số dùng tính tiền/rủi ro/ký quỹ, không nhân OHLC.
Cơ sở thuế mỗi lượt = giá khớp × hệ số × số hợp đồng × margin_rate / 2;
thuế bằng cơ sở nhân pit_rate. Phí mỗi hợp đồng nhân số lượng khớp của lượt.
Chi tiết làm tròn/phân bổ ở [đặc tả tính tiền](canslim-v1-execution-accounting.md).

### 3.6. initial_cash

Vốn hữu hạn lớn hơn 0, nằm ngoài accounting. Ví dụ `"100000000"`.
Contract dùng VND; normalized dùng đơn vị giá mô phỏng.

### 3.7. report

| Trường       | Kiểu        | Bắt buộc khi có report | Ý nghĩa             |
| -------------- | ------------ | ------------------------- | --------------------- |
| `start_date` | string ngày | Có                       | YYYY-MM-DD bắt đầu |
| `end_date`   | string ngày | Có                       | YYYY-MM-DD kết thúc |

Khoảng gồm hai đầu theo ngày địa phương trade_data và nằm trong phạm vi
chuỗi này. Bỏ/null lấy ngày đầu đến cuối trade_data, không tự dời đến lúc
đủ chỉ báo. Nến trước kỳ chỉ khởi tạo, không tạo giao dịch/P/L trước kỳ;
nến sau kỳ không dùng quyết định/khớp. Thay đầu kỳ là thay backtest và
khởi tạo tài khoản cho khoảng mới, không đơn thuần lọc dòng kết quả.

## 4. Payload minh họa

Ví dụ giữ cấu hình CANSLIM v1: chỉ báo/điều kiện thị trường dùng VNINDEX,
giá thực thi dùng VN30F1M, tiền theo hợp đồng. Giá nến minh họa không phải
bộ dữ liệu nghiệm thu hoặc kết quả đầu tư.

**Hai chuỗi chỉ có hai nến để dễ đọc cấu trúc**, không đủ warmup_bars 150
hoặc lịch sử chỉ báo. Khi chạy bản rút gọn này không kỳ vọng tín hiệu vào
lệnh. Để đánh giá, thay dữ liệu đầy đủ theo hợp đồng dữ liệu, giữ lịch sử
khởi tạo và gửi report cho kỳ cần báo cáo. Ví dụ bỏ report nên lấy ngày
có trong trade_data. Không phải mọi trường tùy chọn đều nằm trong ví dụ.

```json
{
  "trade_data": {
    "symbol": "VN30F1M",
    "resolution": "5",
    "bars": [
      {
        "time": 1773800100,
        "open": "1300.0",
        "high": "1302.0",
        "low": "1299.0",
        "close": "1301.0",
        "volume": 1000
      },
      {
        "time": 1773800400,
        "open": "1301.0",
        "high": "1303.0",
        "low": "1300.0",
        "close": "1302.0",
        "volume": 1200
      }
    ],
    "contract_map": [
      {"contract_code": "VN30F2601", "expiry_date": "2026-01-15", "expiry_unix": 1768410000},
      {"contract_code": "VN30F2602", "expiry_date": "2026-02-13", "expiry_unix": 1770915600},
      {"contract_code": "VN30F2603", "expiry_date": "2026-03-19", "expiry_unix": 1773853200},
      {"contract_code": "VN30F2604", "expiry_date": "2026-04-16", "expiry_unix": 1776272400},
      {"contract_code": "VN30F2605", "expiry_date": "2026-05-21", "expiry_unix": 1779296400},
      {"contract_code": "VN30F2606", "expiry_date": "2026-06-18", "expiry_unix": 1781715600},
      {"contract_code": "VN30F2607", "expiry_date": "2026-07-16", "expiry_unix": 1784134800},
      {"contract_code": "VN30F2608", "expiry_date": "2026-08-20", "expiry_unix": 1787158800},
      {"contract_code": "VN30F2609", "expiry_date": "2026-09-17", "expiry_unix": 1789578000},
      {"contract_code": "VN30F2610", "expiry_date": "2026-10-15", "expiry_unix": 1791997200},
      {"contract_code": "VN30F2611", "expiry_date": "2026-11-19", "expiry_unix": 1795021200},
      {"contract_code": "VN30F2612", "expiry_date": "2026-12-17", "expiry_unix": 1797440400}
    ]
  },
  "market_data": {
    "resolution": "5",
    "bars": [
      {
        "time": 1773800100,
        "open": "1249.0",
        "high": "1252.0",
        "low": "1248.0",
        "close": "1250.0",
        "volume": 10000
      },
      {
        "time": 1773800400,
        "open": "1250.0",
        "high": "1253.0",
        "low": "1249.0",
        "close": "1251.0",
        "volume": 12000
      }
    ]
  },
  "strategy": {
    "warmup_bars": 150,
    "indicators": {
      "sma20": {"type": "SMA", "source": "market_data.close", "period": 20},
      "ema5": {"type": "EMA", "source": "market_data.close", "period": 5},
      "bb": {"type": "BB", "source": "market_data.close", "period": 20, "stddev_multiplier": 2},
      "macd": {
        "type": "MACD",
        "source": "market_data.close",
        "fast_period": 12,
        "slow_period": 26,
        "signal_period": 9,
        "histogram": "line"
      },
      "mfi14": {"type": "MFI", "source": "market_data", "period": 14}
    },
    "entry": {
      "require_flat": true,
      "require_no_pending": true,
      "signal_windows": [["09:05", "11:20"], ["13:05", "14:00"]],
      "conditions": {
        "LONG": {
          "all": [
            {"gt": [{"ref": "market_data.close"}, {"ref": "sma20"}]},
            {"gt": [{"ref": "ema5"}, {"ref": "sma20"}]},
            {"gt": [{"sub": [{"ref": "market_data.close"}, {"ref": "bb.upper"}]}, 0]},
            {"lte": [{"sub": [{"ref": "market_data.close"}, {"ref": "bb.upper"}]}, 3]},
            {"gt": [{"ref": "macd.line"}, 0]},
            {"gt": [{"ref": "macd.line"}, {"ref": "macd.line", "shift": 1}]},
            {"gte": [{"ref": "mfi14"}, 55]}
          ]
        },
        "SHORT": {
          "all": [
            {"lt": [{"ref": "market_data.close"}, {"ref": "sma20"}]},
            {"lt": [{"ref": "ema5"}, {"ref": "sma20"}]},
            {"gt": [{"sub": [{"ref": "bb.lower"}, {"ref": "market_data.close"}]}, 0]},
            {"lte": [{"sub": [{"ref": "bb.lower"}, {"ref": "market_data.close"}]}, 3]},
            {"lt": [{"ref": "macd.line"}, 0]},
            {"lt": [{"ref": "macd.line"}, {"ref": "macd.line", "shift": 1}]},
            {"lte": [{"ref": "mfi14"}, 45]}
          ]
        }
      },
      "any": ["LONG", "SHORT"],
      "on_conflict": "SIGNAL_CONFLICT",
      "reentry": "next_bar_close_after_exit",
      "pending": {"max_execution_bars": 1, "cross_lunch": false, "cross_cutoff": false, "cross_session": false}
    },
    "exit": {
      "targets": {
        "LONG": {
          "TP1": {"add": [{"ref": "position.entry_price"}, 6]},
          "TP2": {"add": [{"ref": "position.entry_price"}, 12]}
        },
        "SHORT": {
          "TP1": {"sub": [{"ref": "position.entry_price"}, 6]},
          "TP2": {"sub": [{"ref": "position.entry_price"}, 12]}
        }
      },
      "intrabar": {
        "conditions": {
          "PROTECTIVE_STOP": {
            "type": "protective_stop",
            "distance_points": 6,
            "trailing": {
              "activate_after": "TP1_fill",
              "distance_points": 6,
              "seed": "TP1_price",
              "extrema_from": "bar_after_TP1",
              "update_at": "bar_close",
              "effective_from": "next_bar",
              "combine": "tightest",
              "allow_widening": false
            },
            "quantity": "remaining"
          },
          "TP1": {
            "type": "target_touch",
            "level": "TP1",
            "quantity": {
              "if_initial_quantity_eq": 1,
              "then": "remaining",
              "else": {"floor": [{"div": [{"ref": "position.initial_quantity"}, 2]}]}
            }
          },
          "TP2": {"type": "target_touch", "level": "TP2", "requires": "TP1_filled", "quantity": "remaining"}
        },
        "any": ["PROTECTIVE_STOP", "TP1", "TP2"],
        "priority": ["PROTECTIVE_STOP", "TP1", "TP2"]
      },
      "bar_close": {
        "conditions": {
          "MARGIN_BREACH": {"lt": [{"ref": "account.equity"}, {"ref": "account.required_margin"}]},
          "FORCED_EXIT": {"gte": [{"ref": "clock.local_time"}, "14:20"]},
          "TIME_STOP": {"gte": [{"ref": "position.held_bars"}, 18]}
        },
        "any": ["MARGIN_BREACH", "FORCED_EXIT", "TIME_STOP"],
        "priority": ["MARGIN_BREACH", "FORCED_EXIT", "TIME_STOP"],
        "quantity": "remaining",
        "fill_policy": "next_open"
      },
      "flat_by": "14:30",
      "allow_overnight": false
    },
    "sizing": {
      "type": "risk_and_margin",
      "risk_fraction": 0.01,
      "stop_points": 6,
      "margin_buffer": 1.1,
      "max_contracts": 5,
      "pyramiding": false
    },
    "daily_limits": {
      "stop_new_entry": {
        "any": [
          {"lte": [{"ref": "day.net_pnl"}, {"mul": [{"ref": "day.start_equity"}, -0.02]}]},
          {"gte": [{"ref": "day.entry_fill_count"}, 3]}
        ]
      }
    }
  },
  "execution": {"entry_fill_policy": "next_open", "slippage_rate": "0"},
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

Ví dụ bổ sung kỳ báo cáo khi dữ liệu đã bao phủ đủ khoảng này:

```json
{"report":{"start_date":"2026-03-15","end_date":"2026-09-15"}}
```

Đây là phần bổ sung vào request, không phải request đầy đủ. Không thêm khoảng
này vào bản hai nến vì vượt phạm vi dữ liệu.

## 5. Strategy

Các trường nằm trong strategy. Tên trường như indicators, conditions, type
là cố định. Khóa chỉ báo như sma20 là tên người gọi chọn; nhãn điều kiện thoát
như TIME_STOP được khai báo trong nhóm tương ứng. Riêng hướng BUY/LONG/SHORT
và mức đích TP1/TP2 là từ khóa cố định.

### 5.1. indicators

Mỗi khóa khai báo một chỉ báo. Tên bắt đầu bằng chữ cái, sau đó chỉ có chữ
cái, số hoặc `_`; không dùng trade_data, market_data, position, account, day,
clock. Mỗi chỉ báo phải có type, source và đúng bộ tham số; không truyền thêm
tham số của loại khác hoặc null cho tham số bắt buộc.

| type                    | source hợp lệ                   | Tham số bổ sung bắt buộc                                                            | Đầu ra ref                           |
| ----------------------- | --------------------------------- | --------------------------------------------------------------------------------------- | -------------------------------------- |
| `SMA`                 | Cột OHLCV trade_data/market_data | period nguyên dương                                                                  | Tên chỉ báo                         |
| `HIGHEST`, `LOWEST` | Cột OHLCV trade_data/market_data | period nguyên dương                                                                  | Tên chỉ báo                         |
| `EMA`                 | Cột OHLC trade_data/market_data  | period nguyên dương                                                                  | Tên chỉ báo                         |
| `BB`                  | Cột OHLC trade_data/market_data  | period nguyên dương, stddev_multiplier > 0                                           | tên.middle, tên.upper, tên.lower    |
| `MACD`                | Cột OHLC trade_data/market_data  | fast_period, slow_period, signal_period nguyên dương; fast < slow; histogram: "line" | tên.line, tên.signal, tên.histogram |
| `MFI`                 | "trade_data" hoặc "market_data"  | period nguyên dương; đủ HLCV                                                       | Tên chỉ báo                         |

Ví dụ một khai báo trong indicators:

```json
{"sma20":{"type":"SMA","source":"market_data.close","period":20}}
```

source truyền chuỗi cho công thức; ref đọc giá trị kết quả. EMA khởi tạo bằng
SMA N mẫu đầu; BB dùng phương sai chia N. MACD.histogram hiện bằng line theo
cấu hình hỗ trợ, không phải line trừ signal.

MFI dùng giá điển hình `(high + low + close) / 3` và volume; cần N+1 mẫu để
có N lần so sánh. Giá điển hình không đổi không cộng dòng tiền; hai dòng bằng
0 trả 50, chỉ dòng âm bằng 0 trả 100, chỉ dòng dương bằng 0 trả 0.
Trong contract, chỉ báo 5 phút dùng nến phiên liên tục, không dùng ATO/ATC.

### 5.2. entry

Điều kiện mở được xét sau Close khi không giữ vị thế và không có lệnh chờ
đang xử lý. Số lượng được xác định lúc khớp, không gửi trong entry.

| Trường               | Kiểu             | Bắt buộc             | Ý nghĩa/giá trị hợp lệ                                                           |
| ---------------------- | ----------------- | ---------------------- | -------------------------------------------------------------------------------------- |
| `conditions`         | object            | Có                    | Nhánh BUY cho normalized; LONG/SHORT cho contract; mỗi nhánh là expression boolean |
| `any`                | array string      | Có                    | Đúng các nhánh conditions, không rỗng/trùng                                     |
| `details`            | object            | Không; mặc định {} | Tên → expression số, lưu giá trị lúc tín hiệu mở                             |
| `require_flat`       | boolean/null      | Không                 | Nếu truyền chỉ nhận true                                                           |
| `require_no_pending` | boolean/null      | Không                 | Nếu truyền chỉ nhận true                                                           |
| `signal_windows`     | array cặp string | Không                 | Khoảng HH:MM gồm hai đầu, tăng dần, không chồng nhau                           |
| `on_conflict`        | string/null       | Khi có nhiều nhánh  | Chỉ SIGNAL_CONFLICT; nhiều hướng cùng đạt thì không mở                       |
| `reentry`            | string/null       | Không                 | Chỉ next_bar_close_after_exit; ngăn vào lại tại Close nến vừa thoát            |
| `pending`            | object/null       | Không                 | Quy tắc lệnh mở chờ                                                                |

Khi có pending, cần đủ bốn trường:

| Trường               | Giá trị hỗ trợ |
| ---------------------- | ------------------ |
| `max_execution_bars` | Số nguyên 1      |
| `cross_lunch`        | false              |
| `cross_cutoff`       | false              |
| `cross_session`      | false              |

Giờ tín hiệu lấy theo thời điểm xét sau Close, không phải giờ mở nến.
Tên entry.details cùng quy tắc chữ cái/số/`_` như chỉ báo. Ví dụ:

```json
{"details":{"pivot":{"ref":"pivot","shift":1}}}
```

Cần chỉ báo pivot đã khai báo. Giá trị lưu lúc tín hiệu được đọc bằng
position.entry_pivot sau khi khớp, không tự tính lại theo nến hiện tại.

### 5.3. exit

Phải có ít nhất một trong intrabar hoặc bar_close.

| Trường            | Kiểu        | Bắt buộc                       | Ý nghĩa                                             |
| ------------------- | ------------ | -------------------------------- | ----------------------------------------------------- |
| `targets`         | object       | Khi dùng target_touch           | Hướng → TP1/TP2 → expression giá; mặc định {} |
| `intrabar`        | object/null  | Khi dùng stop/target trong nến | Chỉ hỗ trợ contract                                |
| `bar_close`       | object/null  | Khi thoát theo Close            | Điều kiện đóng và thứ tự ưu tiên            |
| `flat_by`         | string/null  | Không                           | Hạn hết vị thế HH:MM                              |
| `allow_overnight` | boolean/null | Không                           | Nếu truyền chỉ nhận false                         |

Targets tính từ position.entry_price khi khớp mở, giữ nguyên cho vị thế.
Ví dụ LONG có TP1 bằng giá vào cộng 6:

```json
{"LONG":{"TP1":{"add":[{"ref":"position.entry_price"},6]}}}
```

#### 5.3.1. Thoát trong nến — intrabar

Cần conditions, any, priority. Conditions ánh xạ nhãn sang hành động;
any và priority chứa đúng các nhãn, không trùng. Priority xác định thứ tự.

| Loại hành động  | Trường bắt buộc                              | Tùy chọn                     |
| ------------------- | ------------------------------------------------ | ------------------------------ |
| `protective_stop` | type, distance_points > 0, quantity: "remaining" | trailing                       |
| `target_touch`    | type, level: "TP1" hoặc "TP2", quantity         | requires: "TP1_filled" cho TP2 |

Bộ chạy cần đúng một protective stop đặt trước target. Chuỗi đích hỗ trợ:
không có target, TP1, hoặc TP1 rồi TP2. Phải khai báo mức đích cho mọi hướng
vào. Distance_points của stop bằng sizing.stop_points. Không trùng stop/target.

Quantity của target nhận "remaining" hoặc đối tượng chia số lượng:

```json
{"if_initial_quantity_eq":1,"then":"remaining","else":{"floor":[{"div":[{"ref":"position.initial_quantity"},2]}]}}
```

Đối tượng cần đủ ba trường: if_initial_quantity_eq nguyên dương, then chỉ
"remaining", else là expression số chỉ dùng ref position.initial_quantity.

Trailing cần có hành động TP1 và đủ các trường:

| Trường            | Giá trị hỗ trợ |
| ------------------- | ------------------ |
| `activate_after`  | "TP1_fill"         |
| `distance_points` | Số dương        |
| `seed`            | "TP1_price"        |
| `extrema_from`    | "bar_after_TP1"    |
| `update_at`       | "bar_close"        |
| `effective_from`  | "next_bar"         |
| `combine`         | "tightest"         |
| `allow_widening`  | false              |

Stop/target có hiệu lực sau khớp mở. Gap qua stop khớp Open; chạm stop trong
nến khớp mức stop. Gap qua target vẫn khớp target. TP1 đóng một phần thì cập
nhật số lượng trước TP2. Trailing không dùng cực trị nến khớp TP1; từ nến sau
cập nhật tại Close, áp dụng nến kế tiếp, không nới stop. Bước giá/làm tròn
thuộc [đặc tả thực thi](canslim-v1-execution-accounting.md).

#### 5.3.2. Thoát theo Close — bar_close

| Trường        | Kiểu        | Bắt buộc | Ý nghĩa                                     |
| --------------- | ------------ | ---------- | --------------------------------------------- |
| `conditions`  | object       | Có        | Nhãn → expression boolean                   |
| `any`         | array string | Có        | Đúng các nhãn conditions, không trùng   |
| `priority`    | array string | Có        | Đúng các nhãn any theo thứ tự ưu tiên |
| `quantity`    | string       | Có        | Chỉ "remaining"                              |
| `fill_policy` | string       | Có        | Chỉ "next_open"                              |

Chọn điều kiện đầu tiên đạt theo priority, tạo một lệnh đóng phần còn lại ở
Open kế tiếp: contract dùng CLOSE, normalized dùng SELL. Xét sau thoát trong
nến nếu còn vị thế. Nến mở là nến giữ thứ nhất; nghỉ trưa không tính thành nến.

flat_by là hạn thực thi, không tự tạo tín hiệu đóng. Cần điều kiện thoát đủ
sớm và có nến khớp. Thiếu nến thoát bắt buộc, lỡ hạn hoặc còn vị thế cuối kỳ
khi cấm qua đêm làm lần chạy lỗi.

### 5.4. sizing

Không mặc định mở một hợp đồng. Type chọn bộ trường bắt buộc:

| type                 | Trường bắt buộc                                                  | Ràng buộc                                                                                                       |
| -------------------- | -------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------- |
| `fixed_fractional` | risk_fraction, stop_loss_fraction                                    | 0 < risk_fraction <= 1; 0 < stop_loss_fraction < 1                                                                |
| `risk_and_margin`  | risk_fraction, stop_points, margin_buffer, max_contracts, pyramiding | 0 < risk_fraction <= 1; stop_points > 0; margin_buffer >= 1; max_contracts nguyên dương; pyramiding chỉ false |

Normalized chọn số lượng nguyên theo ngân sách rủi ro và tiền đủ mua sau phí.
Stop_loss_fraction dùng tính lượng mua, **không tự tạo điều kiện stop**;
điều kiện thoát vẫn phải khai báo trong exit.

Contract chọn số hợp đồng nguyên theo ngân sách rủi ro, chi phí ước tính hai
lượt, ký quỹ có dự phòng và trần max_contracts. Không đủ một hợp đồng hoặc
không đủ ký quỹ sau phí mở thì từ chối lệnh. Số lượng dựa trên tài khoản và
giá tại lúc khớp. Công thức thuộc [đặc tả tính tiền](canslim-v1-execution-accounting.md).

### 5.5. daily_limits

Khi có nhóm này, cần stop_new_entry là expression boolean. Khi đạt, ngừng
mở mới nhưng vẫn quản trị vị thế cũ. Ví dụ:

```json
{"stop_new_entry":{"any":[{"lte":[{"ref":"day.net_pnl"},{"mul":[{"ref":"day.start_equity"},-0.02]}]},{"gte":[{"ref":"day.entry_fill_count"},3]}]}}
```

Ngừng mở mới khi lỗ ròng ngày đạt 2% giá trị đầu ngày hoặc đã có ba lần khớp
mở trong ngày. Đây là cấu hình mẫu v1, không phải mặc định mọi chiến lược.
Số lần khớp mở khác số tín hiệu hoặc số lần thoát.

## 6. Expression

Cây JSON dùng tính giá trị hoặc kiểm tra điều kiện. Một nút phép toán có một
khóa và mảng toán hạng. Không nhận mã Python, chuỗi "close > sma20" hoặc các
phép chưa hỗ trợ như eq, not, cross_over.

### 6.1. ref / shift

| Trường  | Kiểu        | Bắt buộc            | Ý nghĩa                                      |
| --------- | ------------ | --------------------- | ---------------------------------------------- |
| `ref`   | string       | Có                   | Tên dữ liệu/chỉ báo/trạng thái hỗ trợ |
| `shift` | integer >= 0 | Không; mặc định 0 | Lùi số mẫu trong chuỗi tham chiếu         |

Trade_data.close viết gọn cột trade_data.bars[].close, không phải trường
close trực tiếp dưới trade_data. Với hai Close 1301 và 1302 đã khả dụng:

| Khai báo tại mẫu thứ hai                    | Giá trị               |
| ----------------------------------------------- | ----------------------- |
| `{"ref":"trade_data.close"}`                  | 1302                    |
| `{"ref":"trade_data.close","shift":1}`        | 1301                    |
| `"source":"trade_data.close"` trong chỉ báo | Chuỗi Close để tính |

Shift theo chuỗi tham chiếu, không theo số dòng giao dịch, không vượt ranh
giới khởi tạo lại lịch sử. Không cho shift âm hoặc khai báo shift trên trạng
thái position/account/day/clock, kể cả shift 0.

| Nhóm          | Ref hỗ trợ                                                                                                                 |
| -------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| Giá/volume    | trade_data.open, trade_data.high, trade_data.low, trade_data.close, trade_data.volume; market_data có các cột tương tự |
| Chỉ báo      | Tên khai báo; BB dùng tên.middle/upper/lower; MACD dùng tên.line/signal/histogram                                      |
| Vị thế       | position.entry_price, position.initial_quantity, position.held_bars                                                          |
| Giá trị lưu | position.entry_<tên> từ entry.details.<tên>                                                                               |
| Tài khoản    | account.equity, account.required_margin                                                                                      |
| Ngày          | day.net_pnl, day.start_equity, day.entry_fill_count                                                                          |
| Giờ           | clock.local_time                                                                                                             |

Trạng thái được hệ thống tính, không phải trường gửi thêm trong request.
Các giá trị vị thế chỉ có khi mở vị thế; không dùng giá vào, lượng đầu hoặc
số nến giữ để quyết định mở mới. Targets chỉ cho ref position.entry_price.

### 6.2. gt / gte / lt / lte

Đúng hai toán hạng cùng kiểu số hoặc cùng kiểu giờ; kết quả boolean.

| Phép   | Ý nghĩa | Ví dụ                                                                 |
| ------- | --------- | ----------------------------------------------------------------------- |
| `gt`  | >         | `{"gt":[{"ref":"market_data.close"},{"ref":"sma20"}]}`                |
| `gte` | >=        | `{"gte":[{"ref":"mfi14"},55]}`                                        |
| `lt`  | <         | `{"lt":[{"ref":"account.equity"},{"ref":"account.required_margin"}]}` |
| `lte` | <=        | `{"lte":[{"ref":"mfi14"},45]}`                                        |

Giờ dùng chuỗi HH:MM, ví dụ `{"gte":[{"ref":"clock.local_time"},"14:20"]}`;
không so giờ với số.

### 6.3. add / sub / mul / div

Đúng hai toán hạng số, theo thứ tự trái rồi phải; kết quả số.

| Phép   | Ý nghĩa | Ví dụ                                             |
| ------- | --------- | --------------------------------------------------- |
| `add` | Cộng     | `{"add":[{"ref":"position.entry_price"},6]}`      |
| `sub` | Trừ      | `{"sub":[{"ref":"position.entry_price"},6]}`      |
| `mul` | Nhân     | `{"mul":[{"ref":"day.start_equity"},0.01]}`       |
| `div` | Chia      | `{"div":[{"ref":"position.initial_quantity"},2]}` |

Toán hạng là số JSON hữu hạn, ref số hoặc expression số. Chia 0 bị từ chối;
mẫu số chỉ bằng 0 lúc chạy thì lỗi phát sinh lúc chạy. Không thay lỗi bằng 0.

### 6.4. min / max / floor

| Phép     | Số toán hạng số | Ý nghĩa         | Ví dụ                  |
| --------- | ------------------- | ----------------- | ------------------------ |
| `min`   | 2                   | Chọn nhỏ hơn   | `{"min":[5,3]}` → 3   |
| `max`   | 2                   | Chọn lớn hơn   | `{"max":[5,3]}` → 5   |
| `floor` | 1                   | Làm tròn xuống | `{"floor":[2.5]}` → 2 |

Floor làm tròn về phía âm vô cùng: -2,5 thành -3.

### 6.5. all / any

Trong expression, nhận mảng **không rỗng** các expression boolean. All yêu
cầu tất cả đúng; any yêu cầu ít nhất một đúng. Có thể dùng tên điều kiện dạng
chuỗi khi có trong conditions của cùng nhóm; không tra sang nhóm khác hoặc
tham chiếu vòng. Mọi toán hạng được đánh giá, không dựa vào nhánh trước để
bỏ qua nhánh thiếu dữ liệu.

Any của nhóm entry/exit là danh sách tên; any trong expression là phép kết
hợp boolean. Priority của exit xác định thứ tự hành động, không là toán tử.

### 6.6. Ví dụ lồng expression

Close VNINDEX vượt dải trên BB nhưng không quá 3 điểm; cần bb đã khai báo:

```json
{
  "all": [
    {"gt": [{"sub": [{"ref": "market_data.close"}, {"ref": "bb.upper"}]}, 0]},
    {"lte": [{"sub": [{"ref": "market_data.close"}, {"ref": "bb.upper"}]}, 3]}
  ]
}
```

Sub tính khoảng vượt, gt kiểm tra dương, lte giới hạn 3, all yêu cầu cả hai.
Close 1251 và bb.upper 1250 cho khoảng 1 nên đạt; chỉ dùng giá trị đã khả dụng.

## 7. Validation

### 7.1. Nội dung kiểm tra

| Nhóm         | Kiểm tra                                                                                          |
| ------------- | -------------------------------------------------------------------------------------------------- |
| Cấu trúc    | JSON, trường bắt buộc, kiểu, từ khóa, trường thừa                                        |
| Dữ liệu     | OHLC, thời gian/thứ tự, volume khi cần, report, map hợp đồng và lịch phiên khi áp dụng |
| Chiến lược | Tham số chỉ báo, ref/toán tử, kiểu/số toán hạng, thứ tự thoát, phụ thuộc target      |
| Thực thi     | Tổ hợp accounting/sizing/hướng, resolution, trượt giá, thời điểm khả dụng              |

Validate không chạy mô phỏng. Thiếu lịch sử chỉ báo có thể được ghi
UNEVALUABLE khi chạy; lỗi thực thi bắt buộc vẫn có thể xảy ra sau validate.

### 7.2. Các lỗi chính

Bảng nêu mã thường gặp; lỗi cấu trúc còn có loại lỗi của bộ kiểm tra request.
Một số mã thêm thông tin sau dấu `:`.

| Mã/loại lỗi                                                                                     | Điều kiện                                                                                        |
| -------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| `json_invalid`, `missing`, `extra_forbidden`                                                 | Sai JSON, thiếu trường hoặc có trường thừa                                                  |
| `INVALID_OHLC`                                                                                   | Quan hệ giá không hợp lệ                                                                       |
| `INVALID_BAR_TIMES`                                                                              | Không thỏa time < close_time <= available_at                                                      |
| `UNORDERED_OR_OVERLAPPING_BARS`                                                                  | Nến trùng, đảo thứ tự, chồng lấn                                                            |
| `DAILY_EXPLICIT_TIMES_REQUIRED`                                                                  | Nến ngày thiếu thời điểm đóng/khả dụng                                                    |
| `MISSING_REQUIRED_DATA`, `MISSING_REQUIRED_VOLUME`                                             | Thiếu chuỗi/volume được sử dụng                                                              |
| `INVALID_REPORT_RANGE`, `REPORT_DATA_MISSING`                                                  | Kỳ sai phạm vi hoặc không có nến trong kỳ                                                    |
| `INVALID_CONTRACT_MAP`, `CONTRACT_MAP_MONTH_MISSING`, `CONTRACT_MAP_COVERAGE_MISSING`        | Map sai, thiếu tháng/phạm vi                                                                     |
| `REPORT_OUTSIDE_STATIC_CALENDAR`, `SESSION_POLICY_MISSING`, `UNEXPECTED_BAR`                 | Kỳ ngoài lịch, thiếu chính sách phiên hoặc nến sai phiên                                  |
| `INDICATOR_PARAMETERS_MISMATCH`, `UNSUPPORTED_INDICATOR_SOURCE`                                | Tham số/nguồn chỉ báo sai                                                                       |
| `UNKNOWN_REF`, `INVALID_SHIFT`, `UNSUPPORTED_OPERATOR`                                       | Ref, shift, phép toán không hỗ trợ                                                             |
| `INVALID_OPERAND_COUNT`, `EXPRESSION_TYPE_MISMATCH`, `COMPARISON_TYPE_MISMATCH`              | Sai số toán hạng/kiểu                                                                           |
| `CYCLIC_CONDITION`, `EXPRESSION_TOO_DEEP`, `EXPRESSION_TOO_LARGE`                            | Tham chiếu vòng, sâu quá 32 cấp hoặc vượt ngân sách 4096 nút của cây được kiểm tra |
| `DIVISION_BY_ZERO`, `INVALID_ARITHMETIC`                                                       | Phép tính không hợp lệ                                                                         |
| `INVALID_ENTRY_DIRECTIONS`, `MISSING_CONFLICT_POLICY`                                          | Hướng vào sai hoặc thiếu chính sách xung đột                                               |
| `MISSING_EXIT_ACTIONS`, `INVALID_EXIT_PRIORITY`, `SIZING_STOP_MISMATCH`                      | Thiếu thoát, sai thứ tự hoặc stop không khớp sizing                                          |
| `NORMALIZED_REQUIRES_BUY_FIXED_FRACTIONAL_AND_BAR_CLOSE_EXIT`                                    | Tổ hợp normalized không hỗ trợ                                                                 |
| `CONTRACT_REQUIRES_LONG_SHORT_AND_RISK_AND_MARGIN`                                               | Tổ hợp contract không hỗ trợ                                                                   |
| `UNSUPPORTED_CONTRACT_RESOLUTION`, `UNSUPPORTED_CONTRACT_SLIPPAGE`                             | Contract không dùng 5 phút hoặc trượt giá khác 0                                            |
| `PRIMARY_AVAILABILITY_DELAY_UNSUPPORTED`                                                         | Chuỗi giao dịch có thời điểm khả dụng khác Close                                           |
| `MISSING_REQUIRED_EXIT_BAR`, `MISSING_POSITION_EXECUTION_BAR`                                  | Thiếu nến cần khớp/quản trị vị thế                                                          |
| `FLAT_DEADLINE_MISSED`, `OVERNIGHT_POSITION_INVALID`, `END_OF_REPORT_POSITION_REQUIRES_EXIT` | Vi phạm hạn hoặc yêu cầu không qua đêm                                                      |
| `INLINE_STRATEGY_RUNTIME_NOT_IMPLEMENTED`                                                        | Máy chủ chưa nối bộ chạy chiến lược                                                        |

### 7.3. Status code của hai endpoint POST

| Endpoint                    | HTTP status              | Mã/trạng thái                    | Điều kiện và response                                                   |
| --------------------------- | ------------------------ | ----------------------------------- | --------------------------------------------------------------------------- |
| `/api/backtests/validate` | 200 OK                   | STRUCTURE_VALID                     | Qua kiểm tra, trả body mục 8.1                                           |
| `/api/backtests/validate` | 422 Unprocessable Entity | Lỗi cấu trúc/nội dung           | Không chạy/lưu; trả detail lỗi                                         |
| `/api/backtests/validate` | 503 Service Unavailable  | INLINE_POLICY_UNAVAILABLE           | Không đọc được chính sách phiên cần dùng; detail là chuỗi      |
| `/api/backtests`          | 201 Created              | —                                  | Chạy và lưu xong; trả kết quả mục 8.2                                |
| `/api/backtests`          | 422 Unprocessable Entity | Lỗi cấu trúc/nội dung/thực thi | Không công bố kết quả một phần là thành công                      |
| `/api/backtests`          | 503 Service Unavailable  | BACKTEST_STORAGE_UNAVAILABLE        | Lỗi lưu trữ/ghi thuộc nhóm được xử lý; detail là object có code |

Ví dụ lỗi cấu trúc do trường thừa:

```json
{"detail":[{"type":"extra_forbidden","loc":["body","auto_fetch_data"],"msg":"Extra inputs are not permitted","input":true}]}
```

Ví dụ lỗi nội dung trong hàm xử lý:

```json
{"detail":"UNSUPPORTED_CONTRACT_SLIPPAGE: expected 0"}
```

Ví dụ lỗi lưu trữ khi chạy:

```json
{"detail":{"code":"BACKTEST_STORAGE_UNAVAILABLE"}}
```

Lỗi schema thường có detail dạng mảng chứa vị trí/thông báo; lỗi nội dung
trong hàm xử lý có detail dạng chuỗi; một số lỗi lưu trữ có detail dạng object.
Đây là dạng API hiện trả, không phải một cấu trúc lỗi thống nhất.

### 7.4. Status code khi đọc kết quả

| Endpoint GET               | HTTP status | Mã/nội dung                        | Điều kiện                                                                |
| -------------------------- | ----------- | ------------------------------------ | --------------------------------------------------------------------------- |
| Tất cả endpoint mục 2.3 | 200         | Body tương ứng                    | Đọc thành công                                                          |
| Danh sách/chi tiết       | 409         | detail.code: RESULT_STORAGE_INVALID  | Kho/chỉ mục sai hoặc không đọc được                                |
| Chi tiết/input            | 404         | detail: "run not found"              | Không có lần chạy thành công tương ứng                             |
| Input                      | 409         | detail: "INPUT_STORAGE_INVALID"      | Input thiếu/sai hash/schema; lịch sử phiên bản 1 không có input JSON |
| Chart                      | 404         | detail.code: RUN_NOT_FOUND           | Không có lần chạy/chart khả dụng                                      |
| Chart                      | 409         | detail.code: CHART_DATA_INCONSISTENT | Nến/lần khớp không khớp dữ liệu lần chạy                           |
| Chart                      | 500         | detail.code: CHART_STORAGE_ERROR     | Lỗi đọc khác; không lộ chi tiết nội bộ                             |
| Endpoint có run_id        | 422         | Mảng detail lỗi                    | run_id không phải UUID                                                    |

## 8. Response

Số thập phân trong kết quả chạy trả bằng **chuỗi**; số lượng/số đếm là số
nguyên. UUID là chuỗi; ngày dùng ISO YYYY-MM-DD, thời điểm dùng ISO 8601 có
múi giờ. Mảng không có sự kiện trả []; không tạo fill cho lệnh chưa khớp.

### 8.1. Kết quả POST /api/backtests/validate

| Trường        | Kiểu        | Ý nghĩa                                                                                    |
| --------------- | ------------ | -------------------------------------------------------------------------------------------- |
| `status`      | string       | STRUCTURE_VALID khi qua kiểm tra                                                            |
| `runnable`    | boolean      | Máy chủ có bộ chạy chiến lược                                                        |
| `data_status` | string       | RESOLVED khi đã ánh xạ dữ liệu                                                         |
| `data`        | object       | Kỳ báo cáo, số nến khởi tạo, chỉ báo, map, khoảng thiếu và giả định dữ liệu |
| `pending`     | array string | [] khi có bộ chạy; nếu chưa có trả U08_STRATEGY_RUNTIME                               |
| `payload`     | object       | Request đã chuẩn hóa, kèm mặc định schema, loại trường null                       |

Ví dụ **trích riêng trường trạng thái**; body đầy đủ còn có data và payload:

```json
{"status":"STRUCTURE_VALID","runnable":true,"data_status":"RESOLVED","pending":[]}
```

Payload chuẩn hóa mặc định cấp cấu trúc; không có nghĩa mọi thời điểm suy ra
đã được ghi tường minh vào từng nến.

### 8.2. Cấu trúc kết quả POST /api/backtests

| Trường              | Kiểu                       | Nội dung                                         |
| --------------------- | --------------------------- | ------------------------------------------------- |
| `schema_version`    | integer                     | 2 cho kết quả JSON mới                         |
| `metadata`          | object                      | Định danh, cấu hình, thông tin dữ liệu     |
| `signals`           | array object                | Tín hiệu đã phát                             |
| `orders`            | array object                | Kết quả xử lý lệnh                           |
| `fills`             | array object                | Lần khớp thực tế trong mô phỏng             |
| `trades`            | array object                | Giao dịch/phần đóng đã hiện thực hóa P/L |
| `open_position`     | object/null                 | Vị thế còn mở; null nếu không còn          |
| `equity_history`    | array object                | Giá trị tài khoản theo điểm ghi nhận       |
| `summary`           | object                      | Tổng hợp cuối kỳ                              |
| `evaluations`       | array object, khi có       | Thời điểm, trạng thái, lý do, chỉ báo     |
| `evaluation_status` | object, khi có evaluations | Tổng hợp trạng thái/số nến đánh giá      |

Metadata gồm thông tin dữ liệu từ validate và:

| Trường                          | Kiểu                     | Ý nghĩa                                                        |
| --------------------------------- | ------------------------- | ---------------------------------------------------------------- |
| `run_id`                        | string UUID               | Định danh để đọc lại                                      |
| `engine_version`                | string                    | Phiên bản bộ thực thi                                        |
| `accounting_profile`            | string                    | normalized_v0 hoặc contract_v1                                  |
| `input_hash`, `policy_hash`   | string/null theo trường | Dấu kiểm tra đầu vào/chính sách                           |
| `accounting`                    | object                    | Thông số đã áp dụng                                        |
| `initial_cash`                  | chuỗi thập phân        | Vốn ban đầu                                                   |
| `money_unit`, `quantity_unit` | string                    | Contract: VND/contracts; normalized: price_unit/normalized_units |
| `fill_time_convention`          | string                    | Quy ước thời điểm khớp                                     |

Ví dụ **trích cấu trúc sự kiện và summary** cho kết quả không giao dịch;
không phải body đầy đủ và không phải kết quả payload mục 4:

```json
{
  "schema_version": 2,
  "signals": [], "orders": [], "fills": [], "trades": [],
  "open_position": null,
  "summary": {
    "initial_cash": "100000000", "final_equity": "100000000",
    "realized_pnl": "0", "unrealized_pnl": "0",
    "total_return": "0", "total_fees": "0"
  }
}
```

### 8.3. signals

| Trường             | Kiểu                               | Ý nghĩa                                               |
| -------------------- | ----------------------------------- | ------------------------------------------------------- |
| `signal_id`        | string UUID                         | Định danh tín hiệu                                  |
| `sequence_no`      | integer                             | Thứ tự sự kiện                                      |
| `signal_time`      | thời điểm ISO                    | Thời điểm phát                                      |
| `side`             | string                              | BUY/SELL cho normalized; LONG/SHORT/CLOSE cho contract  |
| `reason`           | string                              | Lý do, ví dụ ENTRY hoặc nhãn thoát                |
| `strategy_details` | object, khi có                     | Giá trị bổ sung của chiến lược                   |
| `pivot`            | chuỗi thập phân/null, normalized | Pivot nếu có trong details; contract không tự thêm |

Tín hiệu là ý định giao dịch, chưa chứng minh đã khớp.

### 8.4. orders

| Trường             | Kiểu                   | Ý nghĩa                                                                        |
| -------------------- | ----------------------- | -------------------------------------------------------------------------------- |
| `order_id`         | string UUID             | Định danh lệnh                                                                |
| `signal_id`        | string UUID             | Tín hiệu tạo lệnh                                                            |
| `created_time`     | thời điểm ISO        | Thời điểm tạo                                                                |
| `side`             | string                  | Hành động                                                                     |
| `status`           | string                  | filled/rejected; pending ở contract hoặc unfilled ở normalized nếu còn chờ |
| `reason`           | string/null, contract   | Lý do trạng thái                                                              |
| `rejection_reason` | string/null, normalized | Lý do từ chối/chưa khớp                                                     |
| `position_id`      | string UUID, khi có    | Vị thế liên quan; không có ở mọi lệnh bị từ chối                      |

Lệnh bị từ chối không có fill. Lệnh mở còn chờ cuối báo cáo được chuyển
rejected với lý do END_OF_REPORT.

### 8.5. fills

| Trường                                                    | Kiểu                        | Ý nghĩa                                                                      |
| ----------------------------------------------------------- | ---------------------------- | ------------------------------------------------------------------------------ |
| `fill_id`, `order_id`, `position_id`                  | string UUID                  | Định danh khớp/lệnh/vị thế                                               |
| `side`                                                    | string                       | Hành động khớp                                                             |
| `signal_time`                                             | thời điểm ISO             | Thời điểm tín hiệu gốc                                                   |
| `fill_time`                                               | thời điểm ISO             | Open cho thị trường/gap; contract ghi chạm stop/target trong nến ở Close |
| `bar_time`                                                | thời điểm ISO             | Open nến chứa khớp, dùng vị trí biểu đồ                               |
| `fill_price`                                              | chuỗi thập phân           | Giá khớp                                                                     |
| `quantity`                                                | integer                      | Số lượng khớp > 0                                                          |
| `fee`                                                     | chuỗi thập phân           | Tổng phí/thuế lượt khớp                                                  |
| `direction`                                               | string, contract             | LONG/SHORT của vị thế                                                       |
| `contract_code`                                           | string/null, contract        | Mã từ map                                                                    |
| `exchange_fee`, `clearing_fee`, `broker_fee`, `pit` | chuỗi thập phân, contract | Từng khoản chi phí                                                          |

Fill_time của chạm trong nến là quy ước ghi nhận OHLC, không xác định chính
xác thời điểm chạm bên trong nến. Dùng bar_time gắn mũi tên biểu đồ.

### 8.6. trades

| Trường                            | Kiểu                        | Ý nghĩa                                         |
| ----------------------------------- | ---------------------------- | ------------------------------------------------- |
| `trade_id`, `position_id`       | string UUID                  | Định danh phần giao dịch đã đóng/vị thế |
| `entry_fill_id`, `exit_fill_id` | string UUID                  | Liên kết lần khớp mở/đóng                  |
| `entry_date`, `exit_date`       | ngày/thời điểm ISO       | Mốc mở/đóng                                   |
| `entry_price`, `exit_price`     | chuỗi thập phân           | Giá mở/đóng                                   |
| `quantity`                        | integer                      | Số lượng phần đóng                          |
| `fees`                            | chuỗi thập phân           | Chi phí mở phân bổ cộng chi phí đóng      |
| `net_pnl`                         | chuỗi thập phân           | Lãi/lỗ đã thực hiện sau chi phí            |
| `close_reason`                    | string                       | Lý do thoát                                     |
| `direction`                       | string, contract             | LONG/SHORT                                        |
| `contract_code`                   | string/null, contract        | Mã hợp đồng                                   |
| `allocated_entry_cost`            | chuỗi thập phân, contract | Chi phí mở phân bổ                            |

Normalized đóng toàn bộ trong một trade. Contract có thể đóng từng phần:
TP1/TP2 tạo hai trades cùng position_id/entry_fill_id nhưng khác exit_fill_id.
Số dòng trades không đồng nghĩa số vị thế mở.

Liên kết: orders.signal_id → signals.signal_id; fills.order_id → orders.order_id;
trades.entry_fill_id/exit_fill_id → fills.fill_id.

### 8.7. Equity — equity_history

Khóa API là equity_history, không phải equity ở ngoài cùng.

| Trường mỗi điểm | Kiểu                  | Áp dụng  | Ý nghĩa                         |
| -------------------- | ---------------------- | ---------- | --------------------------------- |
| `trading_date`     | ngày/thời điểm ISO | Cả hai    | Close của nến được ghi nhận |
| `cash`             | chuỗi thập phân     | Cả hai    | Tiền tài khoản                 |
| `quantity`         | integer                | Cả hai    | Lượng còn giữ                 |
| `unrealized_pnl`   | chuỗi thập phân     | Cả hai    | Lãi/lỗ chưa thực hiện        |
| `equity`           | chuỗi thập phân     | Cả hai    | Giá trị tài khoản             |
| `market_value`     | chuỗi thập phân     | Normalized | Giá trị thị trường vị thế  |
| `required_margin`  | chuỗi thập phân     | Contract   | Ký quỹ yêu cầu                |
| `available_cash`   | chuỗi thập phân     | Contract   | Tiền khả dụng sau ký quỹ     |
| `margin_breach`    | boolean                | Contract   | equity < required_margin          |

Open_position khi có giữ position_id, entry_fill_id, giá/thời điểm mở,
số lượng còn lại và P/L chưa thực hiện. Contract thêm direction, contract_code,
initial_quantity, remaining_entry_cost và strategy_details khi có.
Normalized thêm market_value, entry_pivot. Vị thế mở không phải trade đã đóng.

### 8.8. summary

| Trường           | Kiểu              | Ý nghĩa                                    |
| ------------------ | ------------------ | -------------------------------------------- |
| `initial_cash`   | chuỗi thập phân | Vốn ban đầu                               |
| `final_equity`   | chuỗi thập phân | Giá trị cuối kỳ                          |
| `realized_pnl`   | chuỗi thập phân | Lãi/lỗ đã thực hiện                    |
| `unrealized_pnl` | chuỗi thập phân | Lãi/lỗ vị thế còn mở                   |
| `total_return`   | chuỗi thập phân | (final_equity - initial_cash) / initial_cash |
| `total_fees`     | chuỗi thập phân | Tổng chi phí đã ghi nhận                |

Total_return "0.05" là 5%. Không trừ total_fees lần nữa khỏi P/L/equity đã
bao gồm chi phí.

### 8.9. Trạng thái đánh giá

Mỗi evaluation có time, status, reason, market_sample_count,
market_available_at, indicator_times, indicators. Chỉ báo chưa có giá trị
có thể là null; dữ liệu được ghi theo thời điểm khả dụng.

| evaluation_status.status | Ý nghĩa                       |
| ------------------------ | ------------------------------- |
| EVALUABLE                | Không có bản ghi UNEVALUABLE |
| PARTIALLY_EVALUABLE      | Một phần bản ghi UNEVALUABLE |
| UNEVALUABLE              | Tất cả bản ghi UNEVALUABLE   |

Unevaluable_bars/evaluated_bars đếm theo trạng thái. EVALUABLE không khẳng
định có giao dịch/lợi nhuận hoặc mọi nến được xét mở: reason còn có thể là
OUTSIDE_ENTRY_WINDOW hoặc DAILY_ENTRY_LIMIT. Không giao dịch cần đọc cả
trạng thái và lý do.
