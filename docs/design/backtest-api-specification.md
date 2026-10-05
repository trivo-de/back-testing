# Đặc tả API backtest — nhận dữ liệu và định nghĩa chiến lược trực tiếp

Cập nhật: 28/09/2026. **U03 đã có schema và POST /api/backtests/validate** để
kiểm tra payload JSON, tham chiếu và cây điều kiện. U04 đã tách khớp lệnh/tính
tiền khỏi vòng lặp. U05/U06 đã nối tiếp nhận JSON, ánh xạ dữ liệu và lưu/đọc kết
quả hợp đồng. U07/U08 (29/09) đã nối bộ thực thi cây JSON và giao diện nhập trực tiếp.
POST /api/backtests chỉ nhận payload JSON trực tiếp. CANSLIM v0 và v1 đều được
biểu diễn bằng `trade_data`, `market_data`, `strategy`, `execution`, `accounting`
và `initial_cash`; không chọn nhánh chạy bằng strategy ID.
Xem [phạm vi U07–U08](../plans/engine-upgrade-u07-u08.md); U09 nghiệm thu dữ liệu thật còn riêng.

Hỗ trợ chứa template các chiến lược có sẵn sẽ được cân nhắc sau khi mở rộng đủ trường hợp cho mọi chiến lược.

Lưu ý khi test API trên notebook: Python dùng trực tiếp trong
notebook là một giao diện khác nên không thể truyền nguyên đối tượng lớp/hàm qua
JSON như khi gọi thư viện trong cùng tiến trình.

## 1. Quyết định về đầu vào

- Truyền dữ liệu trực tiếp bằng JSON; không yêu cầu nhập hoặc lưu bộ dữ liệu trước.
- Tách `trade_data` (chuỗi giao dịch) và `market_data` (VNINDEX tham chiếu).
  `market_data` bắt buộc khi quy tắc dùng nó; chiến lược không dùng có thể bỏ qua.
- Không yêu cầu `dataset_id`, `dataset_version`, `strategy_id`, `strategy_version`
  trong yêu cầu chạy mới.
- Truyền định nghĩa chiến lược và các tham số của lần thử, kể cả chiến lược chưa
  từng được lưu thành mẫu. Tên chiến lược nếu có chỉ phục vụ hiển thị.
- Kiểm tra dựa trên nội dung dữ liệu, chỉ báo, quy tắc và khả năng thực thi.
- Mẫu lưu sẵn là tiện ích điền lại nội dung. Chọn mẫu hay tự tạo đều đưa cùng
  nội dung đầy đủ vào luồng kiểm tra và chạy.

## 2. Hướng dẫn payload

Hướng dẫn điền từng trường, keyword hợp lệ, cây phép toán và tham chiếu dấu
chấm: [Hướng dẫn payload chiến lược](strategy-payload-guide.md).

## 3. Các nhóm dữ liệu

**Bổ sung 02/10/2026:** boolean `auto_fetch_data=false`; khi bật, phải bỏ
`trade_data` và `market_data` ở yêu cầu đầu vào. Máy chủ tải cả VN30F1M và
VNINDEX 5 phút, sau đó chuyển về cùng payload đã kiểm tra để lưu và chạy lại
không cần gọi mạng. Quy định bảng dưới áp dụng chế độ nhập thủ công. Chi tiết tại
[Tự tải dữ liệu](auto-fetch-data.md).

| Nhóm        | Nội dung                                                                                                                                |
| ------------ | ---------------------------------------------------------------------------------------------------------------------------------------- |
| trade_data   | Bắt buộc: chuỗi OHLCV giao dịch trực tiếp bằng JSON, khung thời gian, đơn vị và thời gian khả dụng                        |
| market_data  | VNINDEX tham chiếu bằng JSON; bắt buộc nếu chiến lược sử dụng, có thể bỏ hoặc null nếu không sử dụng                   |
| strategy     | Định nghĩa chỉ báo/quy tắc/hành động và các tham số dùng trong lần thử                                                    |
| report       | Tùy chọn: start_date/end_date để chọn kỳ báo cáo; bỏ hoặc null thì xét toàn khoảng trade_data                              |
| execution    | Quy tắc khớp, trượt giá và xử lý phiên/đáo hạn áp dụng cho lần chạy                                                      |
| initial_cash | Số vốn ban đầu của tài khoản backtest; giữ ngoài accounting                                                                     |
| accounting   | Mô hình tính tiền:`normalized` dùng tỷ lệ phí theo giá trị; `contract` dùng hệ số hợp đồng, ký quỹ, thuế và phí |

### 3.1. Payload minh họa

Dưới đây là minh họa một payload với đầy đủ mọi tham số hiện có trong service:

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

### Phần rút gọn và lịch sử khởi tạo

Các chi tiết sau được định nghĩa một lần trong thành phần thực thi, không
bắt người gọi lặp lại trong mỗi payload:

- Chỉ báo: mặc định dùng nến đã đóng hiện tại (`shift=0`), EMA khởi tạo bằng
  SMA N mẫu, BB dùng `ddof=0`, MFI xử lý dòng tiền bằng 0 theo rule đã chốt.
  Chu kỳ, nguồn dữ liệu và hệ số BB vẫn truyền được. `histogram: "line"` vẫn
  giữ tường minh vì đây là cách biểu diễn riêng đã chọn cho v1.
- Kiểm tra dữ liệu: thiếu đầu vào thì không đánh giá; lịch sử chỉ báo v1 lấy VNINDEX; dữ liệu
  khớp lệnh tách theo hợp đồng và loại nến theo data contract, không biến chúng thành cờ bật/tắt.
- Vào lệnh: đánh giá sau Close; khung giờ gồm cả hai đầu.
- Stop/target: tạo từ giá khớp vào, có hiệu lực ngay sau khớp; target giữ
  nguyên cho vị thế, mỗi mức chốt một lần. Gap stop khớp Open, gap target
  khớp target. Sau mỗi lần đóng một phần, cập nhật vị thế trước khi xét tiếp.
- Thực thi: xử lý lệnh đóng chờ ở Open → lệnh mở chờ → thoát trong nến →
  thoát tại Close → tín hiệu mở tại Close. Có đóng một phần vị thế, không
  khớp một phần lệnh. Nến vào lệnh là nến giữ thứ nhất. Thiếu nến thoát bắt
  buộc thì INVALID; cuối báo cáo hủy lệnh mở chờ với END_OF_REPORT.
- `risk_and_margin`: tính cả chi phí hai lượt ước tính, làm tròn xuống số
  hợp đồng nguyên, từ chối nếu dưới một hợp đồng và kiểm tra ký quỹ sau phí
  mở lệnh. Ngừng mở mới theo giới hạn ngày vẫn tiếp tục quản trị vị thế cũ.

### Diễn giải các điều kiện v1

- `indicators` nằm trong strategy; phần thực thi công thức sẽ đặt ở indicators.py.
  EMA/MACD/BB/MFI chưa được triển khai chỉ vì đã xuất hiện trong payload.
  SMA/EMA/BB/MACD/MFI cần 150 nến VNINDEX đã đóng tính cả t, không dùng
  ATO/ATC; không khởi tạo lại chuỗi chỉ báo khi hợp đồng giao dịch chuyển kỳ.
- EMA seed bằng SMA N mẫu đầu, tính tiếp từ N+1. BB chia phương sai cho N.
  MACD line = EMA12 − EMA26; histogram bằng line; signal EMA9 chỉ hiển thị.
  MFI theo TP=(H+L+C)/3 và dòng tiền TP×Volume; TP không đổi thì bỏ dòng đó;
  hai dòng cùng bằng 0 ưu tiên MFI=50 trước hai quy tắc một dòng bằng 0.
- `entry` và `exit` bắt buộc. `all` yêu cầu tất cả điều kiện đạt; `any` yêu cầu
  ít nhất một điều kiện đạt. Giá trị là mảng không rỗng, có thể lồng các nhóm.
  Chuỗi trong any tham chiếu conditions trong cùng nhóm, không tra mẫu đã lưu.
- `gt/gte/lt/lte` là >, >=, <, <=; `add/sub/div/mul` là cộng, trừ, chia, nhân;
  min/max chọn mức giá và floor làm tròn xuống. Các phép hai ngôi nhận hai toán
  hạng; floor nhận một. `ref.shift: 1` lấy giá trị chỉ báo của nến trước trong
  cùng chuỗi VNINDEX. Số thập phân cần đọc bằng Decimal, không tính qua float.
- `entry.conditions.LONG/SHORT` là hai nhánh AND. any xét hai hướng; cả hai đạt
  thì không giao dịch và ghi SIGNAL_CONFLICT. Chỉ xét khi flat, không pending,
  đủ dữ liệu chỉ báo, trong giờ tín hiệu gồm hai đầu. LONG mở mua, SHORT
  mở bán; không tăng thêm vị thế hoặc đổi hướng/vào lại trong nến vừa thoát.
- `exit.targets` tạo tại entry fill: long entry+6, entry+12;
  short entry−6, entry−12. Không cập nhật lại target mỗi nến.
  Target/stop active ngay sau Open fill.
- `exit.intrabar` chỉ xét khi còn vị thế: protective stop kết hợp stop ban đầu
  cách entry 6 điểm và trailing theo mức chặt hơn (long max, short min).
  Gap stop khớp Open, chạm trong nến khớp stop; gap target vẫn khớp target.
  Làm tròn theo tick 0,1: long stop xuống, short stop lên; long target lên,
  short target xuống, theo tài liệu execution v1.
- Priority intrabar là stop → TP1 → TP2. any báo có điều kiện thoát, không có
  nghĩa dừng sau một phần khớp: TP1 đóng 1 nếu initial quantity=1, nếu từ 2 trở
  lên đóng floor(initial/2); TP2 đóng phần còn lại. Cùng nến hoặc cùng mức giá
  vẫn xử lý TP1 trước TP2, cập nhật quantity sau mỗi fill.
- Trailing bật sau TP1, seed tại giá TP1; không dùng High/Low của chính nến TP1.
  Từ nến kế tiếp, cập nhật cực trị tại Close, trừ/cộng 6 điểm và có hiệu lực nến
  sau; không nới stop. Mọi ref position/day/account/clock là trạng thái backend
  tính theo thời điểm, không phải giá trị do người gọi tự gửi để quyết định lệnh.
- `exit.bar_close` được xét sau TP intrabar nếu còn vị thế: ưu tiên margin breach,
  forced exit rồi time-stop; chỉ một lệnh đóng phần còn lại ở Open kế tiếp.
  Nến entry tính là nến giữ thứ nhất; không tính nghỉ trưa thành nến.
  Forced exit phát tại Close 14:20, khớp Open 14:20 và phải flat trước 14:30.
  So sánh giờ dùng kiểu thời gian UTC+7; thiếu nến thoát đúng phiên thì INVALID,
  không lấy điều kiện >=14:20 làm lý do cho phép thoát trễ hoặc qua đêm.
- `sizing` là thành phần dự kiến tính đúng R07: risk_budget=equity×0,01;
  risk_per_contract=6×100000+chi phí hai lượt ước tính; qty=min(qty_risk,
  qty_margin,5), với qty_margin=floor(available_cash/(entry×100000×im_rate×1,10)).
  Kiểm tra chi phí mở lệnh và ký quỹ trước fill; không đủ một hợp đồng thì từ chối.
  Thuế/phí/ký quỹ theo tài liệu tính tiền v1, không dùng fee_rate v0.
- `daily_limits` ngừng mở mới khi P/L ròng ngày <= −2% equity đầu ngày hoặc đã
  có 3 entry fill; vẫn quản trị vị thế cũ. Không hiểu số entry fill là số tín hiệu
  hoặc số lần thoát. Cách tính P/L lấy từ tầng tài khoản theo tài liệu v1.
- Bộ tiếp nhận kiểm tra toán tử/tham chiếu rồi đánh giá trực tiếp cây JSON;
  không chạy chuỗi bằng eval và không yêu cầu đã lưu mẫu chiến lược.

U03 đã kiểm tra các khai báo này và tính được cây phép toán trên giá trị đã
khả dụng. U04 có khớp stop/target/trailing riêng; việc chuyển toàn bộ strategy
JSON thành hành vi chạy, gồm risk_and_margin, đã triển khai ở U08.

### Thời gian và đơn vị

Áp dụng riêng cho mỗi chuỗi trade_data/market_data trong thiết kế mới:

Khung thời gian dùng `resolution` theo cách ghi của VNDIRECT: `"5"` là 5 phút,
`"D"` là ngày. Cả trade_data và market_data dùng cùng tên trường này, không dùng
`timeframe` hoặc giá trị `"5m"` trong payload mới. `resolution` bắt buộc cho mỗi
chuỗi.

| Trường            | Bắt buộc                                          | Khi không truyền                                                                                 |
| ------------------- | --------------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| bars[].time         | Có                                                 | Thời điểm mở nến                                                                              |
| bars[].close_time   | Không, với nến 5 phút theo quy ước đã chốt | `time + 300` giây                                                                               |
| bars[].available_at | Không, với cùng quy ước mô phỏng             | Bằng close_time sau khi xác định thời điểm đóng                                           |
| timestamp_unit      | Không                                              | "s": Unix giây; truyền "ms" nếu dữ liệu dùng mili giây, không tự đoán qua độ dài số |
| timezone            | Không trong phạm vi thị trường Việt Nam       | "Asia/Ho_Chi_Minh", dùng xác định ngày báo cáo và giờ phiên                              |
| price_unit          | Không cho thử logic trên giá                    | Không tự gán đơn vị hoặc nhân/chia giá; giữ giá trị đầu vào                         |

Ví dụ payload trên bỏ các trường tùy chọn này. Với time=1773800100,
hệ thống xác định close_time=1773800400 và available_at=1773800400. Nếu khai báo
timestamp_unit="ms", quy đổi về cùng đơn vị nội bộ trước khi cộng thời lượng.
Khi cung cấp thời gian tường minh, kiểm tra time < close_time <= available_at;
không ghi đè thời gian công bố đã có bằng giả định close_time.

available_at tự tính là giả định mô phỏng, không phải bằng chứng thời điểm nguồn
thực tế công bố. Không áp dụng cộng 300 giây cho nến daily, nến phiên hoặc loại
dữ liệu khác chưa có quy ước: cần thời gian tường minh hoặc quy tắc đã xác định.
Không suy daily đóng sau 24 giờ kể từ timestamp. Quy ước dữ liệu v1 về phiên/
đấu giá vẫn giữ nguyên.

Unix đã xác định một thời điểm tuyệt đối; timezone không làm dịch timestamp,
chỉ dùng chuyển sang giờ địa phương để xử lý ngày/phiên. Các mặc định thực sự
áp dụng phải được ghi lại cùng kết quả để người xem biết hệ thống đã dùng gì.

price_unit là nhãn đơn vị, không chọn mô hình tiền. Với P/L hợp đồng v1, vẫn
phải xác định giá theo điểm và các thông số hợp đồng trong cấu hình tài khoản;
không bỏ việc kiểm tra đơn vị cần cho phép tính hoặc nhập lặp nếu cấu hình đã có.

### 3.2. Symbol và kỳ báo cáo

| Trường                            | Đề xuất khi truyền dữ liệu trực tiếp                                                                                                                     |
| ----------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| trade_data.symbol                   | Không bắt buộc cho thử logic trên một chuỗi giá; dùng làm nhãn kết quả/biểu đồ, không dùng chọn chiến lược hoặc mặc định HPG           |
| report.start_date / report.end_date | Khi có report thì nhập cả hai ngày, bao gồm hai đầu theo múi giờ trade_data; dùng chọn kỳ báo cáo, không dùng tải dữ liệu                    |
| report bị bỏ hoặc null           | Khoảng báo cáo từ ngày đầu đến ngày cuối của trade_data; không lấy khoảng của market_data và không tự dời đầu kỳ tới lúc đủ chỉ báo |
| resolution / thời gian khả dụng  | Vẫn cần để xác định một nến, tính chu kỳ, đối chiếu dữ liệu phụ và thời điểm được phát tín hiệu                                       |

Nếu gửi thêm nến trước kỳ báo cáo để khởi tạo chỉ báo, cần report để phân biệt
phần đó. Nến trước start_date chỉ phục vụ tính toán, không tạo lệnh/vị thế/P&L
trước kỳ báo cáo. Các nến sau end_date không được dùng để quyết định hoặc khớp
lệnh trong lần chạy. Ngày kết thúc trước ngày bắt đầu hoặc kỳ nằm ngoài phạm vi
trade_data phải báo lỗi; phiên thiếu xử lý theo hợp đồng dữ liệu áp dụng.

Quy tắc mặc định toàn chuỗi là tiện ích API chung, không thay kỳ sáu tháng của v1.
Khi chạy v1 có dữ liệu khởi tạo bên ngoài sáu tháng, truyền report chỉ rõ kỳ đã
chốt; không tự thu hẹp kỳ vì market_data hoặc lịch sử chỉ báo ngắn hơn.

### Dữ liệu trực tiếp

- Mỗi chuỗi có tên để quy tắc tham chiếu; đó là tên trong yêu cầu
- OHLCV được truyền trong JSON.
- `trade_data` và `market_data` có thể khác số nến, khung thời gian và giờ phiên.
  Tại thời điểm quyết định t chỉ lấy bản ghi market có available_at <= t; không
  ghép theo số thứ tự dòng hoặc dùng Close cuối ngày khi ngày đó chưa kết thúc.
  Mỗi nến thị trường chỉ là một mẫu chỉ báo, không nhân bản để khớp số nến trade.
  Thiếu market_data mà quy tắc có tham chiếu thì báo lỗi; thiếu lịch sử cần thiết
  thì chưa đánh giá được, không tự coi điều kiện thị trường đã đạt.
- Nến intraday phải xác định thời điểm mở/đóng và thời điểm dữ liệu được phép
  sử dụng. Có thể khai báo quy ước chung nếu áp dụng đồng nhất theo hợp đồng dữ
  liệu; không mặc định mọi chuỗi có cùng thời gian khả dụng.
- Timestamp Unix mặc định giây; khai báo timestamp_unit nếu dùng mili giây.
  Phiên giao dịch/kỳ báo cáo theo timezone đã truyền hoặc mặc định Việt Nam.
- Lịch phiên, bảng mã hợp đồng/đáo hạn, ký quỹ và chi phí có thể nằm trong các
  bảng JSON đi kèm khi mô hình cần. Không bắt đăng ký chúng bằng dataset_version.
- Vẫn kiểm tra số hữu hạn, OHLC hợp lệ, thứ tự/trùng thời gian, dữ liệu cần thiết
  và phiên thiếu theo hợp đồng dữ liệu. Không tự ghép nguồn hoặc điền giá thiếu.

Tiếp nhận JSON không thay đổi [quy ước dữ liệu v0](../data/vn30f1m/data-contract.md)
hoặc [quy ước dữ liệu v1](../data/vn30f1m/data-contract-v1.md).
Thiếu lịch sử được xử lý theo quy tắc chiến lược; không tự rút ngắn báo cáo hoặc
đổi chu kỳ chỉ báo. V1 giữ kỳ sáu tháng đã chốt. Ngoại lệ rút kỳ chỉ thuộc lần
chạy VN30F1M với CANSLIM v0.

## Phạm vi cây công thức hiện tại

- Các phép so sánh, all/any, tham chiếu, entry/exit đã có bộ kiểm tra và hàm
  tính cây công thức. Stop/target/trailing, sổ tiền, dữ liệu và trạng thái đều
  được nối trong cùng luồng chạy JSON.
- Phép giao cắt chỉ bổ sung khi có chiến lược cần; v1 hiện dùng so sánh.
- Mã hợp đồng lấy từ `trade_data.contract_map`; lịch phiên lấy từ policy máy chủ;
  ký quỹ, phí và hệ số hợp đồng lấy từ `accounting`.

Các việc còn lại là triển khai những quyết định đã có, không yêu cầu người dùng
chốt lại rule. Cây chỉ nhận các toán tử đã liệt kê; không thực thi mã Python từ HTTP.

## 8. Source hiện có

`POST /api/backtests` chỉ nhận payload JSON trực tiếp:

```text
trade_data, market_data, strategy, execution, accounting, initial_cash, report
```

### Ví dụ về output `POST /api/backtests/validate`

```text
status: STRUCTURE_VALID
runnable: true
data_status: RESOLVED
pending: []
data: kỳ báo cáo, số nến trước kỳ, map hợp đồng, các khoảng thiếu dữ liệu
payload: nội dung đã kiểm tra, kèm mặc định công khai như contract_multiplier
```

Sai cấu trúc, toán tử, tham chiếu, kiểu, thứ tự nến, OHLC, thời gian hoặc thiếu
market/volume được rule sử dụng: HTTP 422. Trường không được hỗ trợ cũng bị
từ chối, không bị bỏ qua. Xem schema đầy đủ tại `/docs`, endpoint `/validate`.
Chỉ báo được kiểm tra khai báo ở đây; hàm tính SMA/EMA/BB/MACD/MFI đã có trong indicators.py.
U05 đã ánh xạ thời gian, độ phủ map, lịch phiên và các khoảng thiếu dữ liệu.
`STRUCTURE_VALID` không xác nhận đủ 150 mẫu chỉ báo liên tục hoặc đủ điều kiện
giao dịch; bộ thực thi xét trạng thái đó tại từng nến. Không ghép theo số thứ tự dòng.

### Chạy và đọc kết quả sau U05/U06

- `POST /api/backtests`: chỉ nhận payload JSON trực tiếp, không cần ID/phiên bản;
  thực thi cây quy tắc, trả HTTP 201 và lưu kết quả. `accounting.model=normalized`
  chạy BUY/SELL với `fixed_fractional`; `accounting.model=contract` chạy
  LONG/SHORT/CLOSE với `risk_and_margin`. Tổ hợp chưa hỗ trợ trả HTTP 422.
- `GET /api/backtests` và `GET /api/backtests/{run_id}`: đọc kết quả cũ nguyên
  dạng và kết quả hợp đồng có `schema_version: 2`.
- `GET /api/backtests/{run_id}/input`: trả payload đầy đủ đã áp mặc định, lịch
  đã dùng và thông tin dữ liệu của lần chạy mới, giúp tái lập kết quả.
- `GET /api/backtests/{run_id}/chart`: kết quả mới lấy giá từ bản input đã lưu,
  không cần dataset_version; có cả bars và market_bars. Giao diện U07 đọc các chuỗi này.

Kết quả phiên bản 2 gồm metadata, signals, orders, fills, trades, open_position,
equity_history và summary. Strategy details chỉ xuất khi có. Mỗi fill có
position_id/order_id riêng, direction, contract_code và từng khoản exchange_fee,
clearing_fee, broker_fee, pit; mỗi lần đóng giữ entry_fill_id/exit_fill_id.
Equity có required_margin, available_cash, margin_breach. Không có pivot mặc định.
`evaluations` ghi thời điểm Close, trạng thái đánh giá, lý do và giá trị chỉ báo
đã khả dụng. `evaluation_status` tổng hợp số nến thiếu dữ liệu; không có lệnh
không đồng nghĩa mọi điều kiện đã được đánh giá. `bar_time` trong fill là Open
của nến chứa lần khớp, dùng gắn mũi tên; `fill_time` giữ quy ước khớp thực tế.
Metadata lưu input_hash, policy_hash, accounting và đơn vị. Tệp kết quả kèm
result_hash; hash sai, thiếu input hoặc phiên bản không hỗ trợ trả HTTP 409 khi đọc.

Ứng dụng chung `backtest_hpg.main:app`; `intraday_main:app` là tên tương thích.
`BACKTEST_LEGACY_BACKEND=file|postgres` chỉ chọn nơi đọc lịch sử cũ; không chọn
cách chạy CANSLIM v0 cho yêu cầu mới.
JSON mới dùng `BACKTEST_STORE_PATH`; PostgreSQL không bị chuyển đổi/xóa tự động.

Các kiểm thử từ lượt 26/09 chỉ xác nhận luồng tham số đã triển khai; không chứng
minh thiết kế ngày 28/09 đã chạy. Phần tham số đó có thể tái sử dụng ở các thành
phần chỉ báo/quy tắc, nhưng không dùng sự tồn tại của mẫu làm điều kiện kiểm tra.

Bảng kiểm triển khai nằm riêng tại `.agents/checklists/engine-upgrade-checklist.md`.

## 9. Status code và các trường hợp ngoại lệ

Mỗi endpoint công bố cả record thành công và record lỗi trong cùng bảng. Các lỗi
do FastAPI phát hiện trước khi vào hàm xử lý (body sai JSON/schema hoặc `run_id`
không phải UUID) dùng HTTP 422. Với lỗi nghiệp vụ hoặc lưu trữ, `detail` chứa mã
lỗi đã liệt kê dưới đây:

| Endpoint                              | HTTP status                   | Mã lỗi/record                                                    | Message | Điều kiện và response                                                                                                                                                                                                 |
| ------------------------------------- | ----------------------------- | ------------------------------------------------------------------ | ------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `POST /api/backtests/validate`      | `200 OK`                    | `STRUCTURE_VALID`                                                |         | Payload hợp lệ về cấu trúc và dữ liệu; trả trạng thái kiểm tra, metadata dữ liệu, pending và payload đã chuẩn hóa.                                                                                     |
| `POST /api/backtests/validate`      | `422 Unprocessable Entity`  | Lỗi schema hoặc mã kiểm tra nội dung                          |         | JSON/schema, kiểu, thời gian, OHLC, tham chiếu, toán tử, dữ liệu bắt buộc hoặc tổ hợp execution/accounting không hợp lệ; không chạy và không lưu run.                                                 |
| `POST /api/backtests/validate`      | `503 Service Unavailable`   | `INLINE_POLICY_UNAVAILABLE`                                      |         | Không đọc được policy phiên; không trả kết quả kiểm tra hoàn chỉnh.                                                                                                                                         |
| `POST /api/backtests`               | `201 Created`               | —                                                                 |         | Backtest chạy xong và lưu kết quả; trả result của run.                                                                                                                                                             |
| `POST /api/backtests`               | `422 Unprocessable Entity`  | Lỗi schema hoặc mã lỗi chạy                                   |         | Payload không hợp lệ, thiếu dữ liệu, thiếu warm-up, tổ hợp chưa hỗ trợ, runtime chưa có, execution bị từ chối hoặc run thất bại do lỗi đầu vào; không công bố partial result là thành công. |
| `POST /api/backtests`               | `503 Service Unavailable`   | `BACKTEST_STORAGE_UNAVAILABLE`                                   |         | Lỗi lưu trữ hoặc ghi kết quả; run không được công bố là thành công.                                                                                                                                        |
| `GET /api/backtests`                | `200 OK`                    | —                                                                 |         | Trả danh sách các run thành công theo thứ tự repository.                                                                                                                                                           |
| `GET /api/backtests`                | `409 Conflict`              | `RESULT_STORAGE_INVALID`                                         |         | Kết quả hoặc chỉ mục lưu trữ không đọc được, sai schema hoặc sai integrity.                                                                                                                                 |
| `GET /api/backtests/{run_id}`       | `200 OK`                    | —                                                                 |         | `run_id` tồn tại và kết quả đọc qua kiểm tra integrity.                                                                                                                                                         |
| `GET /api/backtests/{run_id}`       | `404 Not Found`             | `RUN_NOT_FOUND`                                                  |         | Không có run tương ứng.                                                                                                                                                                                              |
| `GET /api/backtests/{run_id}`       | `409 Conflict`              | `RESULT_STORAGE_INVALID`                                         |         | Hash, input, schema, trạng thái hoặc quan hệ result không hợp lệ.                                                                                                                                                  |
| `GET /api/backtests/{run_id}`       | `422 Unprocessable Entity`  | —                                                                 |         | `run_id` không phải UUID hoặc path/request không hợp lệ.                                                                                                                                                          |
| `GET /api/backtests/{run_id}/input` | `200 OK`                    | —                                                                 |         | Trả input đầy đủ và metadata policy của run.                                                                                                                                                                       |
| `GET /api/backtests/{run_id}/input` | `404 Not Found`             | `INPUT_RUN_NOT_FOUND`                                            |         | Không có input/run tương ứng.                                                                                                                                                                                        |
| `GET /api/backtests/{run_id}/input` | `409 Conflict`              | `INPUT_STORAGE_INVALID`                                          |         | Input thiếu, sai hash, sai schema hoặc không tương thích với run.                                                                                                                                                  |
| `GET /api/backtests/{run_id}/input` | `422 Unprocessable Entity`  | —                                                                 |         | `run_id` không phải UUID hoặc path/request không hợp lệ.                                                                                                                                                          |
| `GET /api/backtests/{run_id}/chart` | `200 OK`                    | —                                                                 |         | Trả chart snapshot từ input đã lưu của run.                                                                                                                                                                         |
| `GET /api/backtests/{run_id}/chart` | `404 Not Found`             | `CHART_RUN_NOT_FOUND`                                            |         | Không có run hoặc run không có chart khả dụng.                                                                                                                                                                     |
| `GET /api/backtests/{run_id}/chart` | `409 Conflict`              | `CHART_DATA_INCONSISTENT`                                        |         | Bar, OHLCV hoặc fill trong chart không khớp dữ liệu run.                                                                                                                                                             |
| `GET /api/backtests/{run_id}/chart` | `422 Unprocessable Entity`  | —                                                                 |         | `run_id` không phải UUID hoặc path/request không hợp lệ.                                                                                                                                                          |
| `GET /api/backtests/{run_id}/chart` | `500 Internal Server Error` | `CHART_STORAGE_ERROR`                                            |         | Lỗi đọc storage ngoài nhóm lỗi integrity đã biết; không lộ chi tiết nội bộ.                                                                                                                                 |
| `GET /api/strategies`               | `200 OK`                    | —                                                                 |         | Trả danh mục mẫu chiến lược và capability; danh mục không phải điều kiện để chạy request mới.                                                                                                            |
| `GET /api/strategies/{strategy_id}` | `200 OK`                    | —                                                                 |         | Trả schema/version của strategy được yêu cầu.                                                                                                                                                                      |
| `GET /api/strategies/{strategy_id}` | `404 Not Found`             | `unsupported strategy_id` hoặc `unsupported strategy_version` |         | Không có strategy hoặc version tương ứng trong danh mục mẫu.                                                                                                                                                      |

Đối với các trạng thái `422` phát sinh trong quá trình chạy, record lỗi của run vẫn sẽ được giữ lại nếu repository đã tạo run và endpoint đọc danh sách thành công sẽ trả về kết quả đó là kết quả lỗi
