# Đặc tả API backtest — nhận dữ liệu và định nghĩa chiến lược trực tiếp

Cập nhật: 28/09/2026. **Thiết kế đầu vào mới; source hiện vẫn dùng API đã triển
khai ngày 26/09.** Phần 8 ghi rõ khác biệt. Lượt này sửa đặc tả, chưa triển khai
bộ đọc quy tắc JSON hoặc thay luồng chạy hiện tại.

## 1. Quyết định về đầu vào

- Truyền dữ liệu trực tiếp bằng JSON; không yêu cầu nhập hoặc lưu bộ dữ liệu trước.
- Tách `trade_data` (chuỗi giao dịch) và `market_data` (VNINDEX tham chiếu).
  `market_data` bắt buộc khi quy tắc dùng nó; chiến lược không dùng có thể bỏ qua.
- Không yêu cầu `dataset_id`, `dataset_version`, `strategy_id`, `strategy_version`
  trong yêu cầu chạy mới.
- Truyền định nghĩa chiến lược và các tham số của lần thử, kể cả chiến lược chưa
  từng được lưu thành mẫu. Tên chiến lược nếu có chỉ phục vụ hiển thị.
- Kiểm tra dựa trên nội dung dữ liệu, chỉ báo, quy tắc và khả năng thực thi;
  không kiểm tra điều kiện chiến lược phải tồn tại trong danh sách mẫu.
- Mẫu lưu sẵn là tiện ích điền lại nội dung. Chọn mẫu hay tự tạo đều đưa cùng
  nội dung đầy đủ vào luồng kiểm tra và chạy.
- Lưu kết quả hoặc mẫu là việc riêng; không cần tạo mẫu trước khi thử chiến lược.

Các yêu cầu bắt buộc ID/phiên bản và chọn chiến lược đã đăng ký trong thiết kế
ngày 26/09 không còn là hướng thiết kế API mới. Source cũ chưa được đổi theo
quyết định này; lịch sử đã lưu vẫn cần đọc được.

## 2. Phân biệt tham số và định nghĩa chiến lược

Hướng dẫn điền từng trường, keyword hợp lệ, cây phép toán và tham chiếu dấu
chấm: [Hướng dẫn payload chiến lược](strategy-payload-guide.md).

`{"period": 20}` chỉ cung cấp một giá trị, chưa cho biết tính chỉ báo nào, dùng
chuỗi nào, điều kiện vào/thoát lệnh hoặc khối lượng giao dịch. Bỏ strategy_id
nhưng chỉ giữ strategy_params vẫn chưa đủ để chạy một chiến lược mới.

Vì vậy, phần `strategy` cần chứa định nghĩa có thể thực thi, gồm các thành phần
chiến lược thực sự sử dụng: chỉ báo/công thức, điều kiện, hành động, cách tính
khối lượng và trạng thái liên quan. Không bắt mọi chiến lược có cùng bộ chỉ báo
hoặc các trường tham số CANSLIM.

**Hướng đề xuất cho API JSON:** truyền quy tắc có cấu trúc và các tham số ngay
trong yêu cầu. Một bộ đọc quy tắc chung chuyển nội dung này thành phần đánh giá
mà engine hiện có gọi. Không tạo một lớp Python và mục đăng ký riêng cho mỗi
bộ quy tắc người dùng muốn thử.

Chiến lược chưa lưu vẫn kiểm tra và chạy được nếu các thành phần nó sử dụng
đã được hỗ trợ. Chỉ báo, toán tử hoặc hành động mới chưa có phần tính tương ứng
phải được bổ sung vào khả năng của hệ thống; việc lưu một mẫu không giải quyết
được thiếu sót này.

Đã chọn cách biểu diễn bằng `all`/`any` và các nút phép toán cho CANSLIM v1;
`entry` và `exit` là hai trường bắt buộc trong `strategy`. Không coi JSON tùy ý
hoặc một mô tả bằng văn bản là định nghĩa đã đủ để thực thi. Mã Python dùng trực tiếp trong
notebook là một giao diện khác; không thể truyền nguyên đối tượng lớp/hàm qua
JSON như khi gọi thư viện trong cùng tiến trình.

## 3. Các nhóm dữ liệu trong yêu cầu mới

Tên nhóm dưới đây là đề xuất kỹ thuật, chưa phải mẫu JSON gửi chạy được.

| Nhóm       | Nội dung                                                                                                              |
| ----------- | ---------------------------------------------------------------------------------------------------------------------- |
| trade_data  | Bắt buộc: chuỗi OHLCV giao dịch trực tiếp bằng JSON, khung thời gian, đơn vị và thời gian khả dụng      |
| market_data | VNINDEX tham chiếu bằng JSON; bắt buộc nếu chiến lược sử dụng, có thể bỏ hoặc null nếu không sử dụng |
| strategy    | Định nghĩa chỉ báo/quy tắc/hành động và các tham số dùng trong lần thử                                  |
| report      | Tùy chọn: start_date/end_date để chọn kỳ báo cáo; bỏ hoặc null thì xét toàn khoảng trade_data            |
| execution   | Quy tắc khớp, trượt giá và xử lý phiên/đáo hạn áp dụng cho lần chạy                                    |
| initial_cash | Số vốn ban đầu của tài khoản backtest; giữ ngoài accounting |
| accounting | Hệ số hợp đồng, tỷ lệ ký quỹ, thuế suất và phí sàn/bù trừ/môi giới |

Cách tính tiền được xác định rõ từ cấu hình tài khoản, không suy từ tên chiến
lược. VN30F1M chạy mô hình v0 vẫn khác mô hình tiền hợp đồng của v1.
Thông số phái sinh tuân theo [tài liệu tính tiền v1](canslim-v1-execution-accounting.md).

### 3.1. Payload minh họa

Đây là **mẫu cấu trúc đề xuất**, chưa gửi chạy được vào API hiện tại. Giá và khối
lượng là dữ liệu giả minh họa; hai nến không đủ để chạy các chỉ báo v0/v1.
`strategy` dưới đây biểu diễn CANSLIM v1 theo cách `all`/`any`: SMA20, EMA5,
BB(20,2), MACD, MFI14; vào long/short và thoát theo stop/TP/trailing/thời gian.
Các con số lấy từ [rule v1](../strategies/canslim-v1-rules.md). Tên trường/nút mới
là thiết kế biểu diễn, chưa có bộ thực thi tương ứng trong source.

`trade_data.daily_bars` và `trade_data.contract_map` đang để mảng rỗng làm chỗ
điền dữ liệu ngày trước và bảng mã hợp đồng thực theo data contract v1. Khi chạy
thật phải có đủ đầu vào này và lịch sử 150 nến VNINDEX; không coi mẫu hai nến
là bộ dữ liệu đủ điều kiện. Lịch phiên và thông số phí/ký quỹ lấy từ cấu hình v1
đã chốt, không thêm accounting_model vào request. Broker fee 0 trong ví dụ là
lựa chọn mô phỏng tường minh; vốn demo là 100.000.000 VND.

```json
{
  "trade_data": {
    "symbol": "VN30F1M",
    "resolution": "5",
    "bars": [
      {
        "open_time": 1773800100,
        "open": "1300.0",
        "high": "1302.0",
        "low": "1299.0",
        "close": "1301.0",
        "volume": 1000
      },
      {
        "open_time": 1773800400,
        "open": "1301.0",
        "high": "1303.0",
        "low": "1300.0",
        "close": "1302.0",
        "volume": 1200
      }
    ],
    "daily_bars": [],
    "contract_map": []
  },
  "market_data": {
    "resolution": "5",
    "bars": [
      {
        "open_time": 1773800100,
        "open": "1249.0",
        "high": "1252.0",
        "low": "1248.0",
        "close": "1250.0",
        "volume": 10000
      },
      {
        "open_time": 1773800400,
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
      "mfi14": {"type": "MFI", "source": "market_data", "period": 14},
      "daily_pivot": {
        "type": "CLASSIC_PIVOT",
        "source": "trade_data.daily_bars",
        "session": "previous_completed",
        "match": "contract_code"
      }
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
          "TP1": {"max": [{"ref": "daily_pivot.r1"}, {"add": [{"ref": "position.entry_price"}, 6]}]},
          "TP2": {"max": [{"ref": "daily_pivot.r2"}, {"add": [{"ref": "position.entry_price"}, 12]}]}
        },
        "SHORT": {
          "TP1": {"min": [{"ref": "daily_pivot.s1"}, {"sub": [{"ref": "position.entry_price"}, 6]}]},
          "TP2": {"min": [{"ref": "daily_pivot.s2"}, {"sub": [{"ref": "position.entry_price"}, 12]}]}
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
  "execution": {"entry_fill_at": "next_open", "slippage_rate": "0"},
  "initial_cash": "100000000",
  "accounting": {
    "contract_multiplier": "100000",
    "margin_rate": "0.17",
    "pit_rate": "0.001",
    "exchange_fee_per_contract": "2700",
    "clearing_fee_per_contract": "2550",
    "broker_fee_per_contract": "0"
  }
}
```

Trong phạm vi hiện tại, `market_data` quy ước là VNINDEX nên không cần nhập lại
symbol của chuỗi này. Nó là dữ liệu tham chiếu, không phải tài sản nhận lệnh.
Ví dụ giữ OHLCV giả minh họa của VNINDEX để thể hiện trường market_data trong API.
CANSLIM v1 bắt buộc market_data: SMA/EMA/BB/MACD lấy market_data.close,
MFI lấy HLCV market_data; các so sánh Close ở entry cũng dùng VNINDEX.
Giá khớp, stop, trailing và P/L vẫn lấy hợp đồng trong trade_data. Daily pivot
lấy từ trade_data.daily_bars để tạo mức giá chốt lời trên chính hợp đồng.
Giá truyền bằng chuỗi thập phân; bộ tiếp nhận mới cần chuyển thành Decimal và
kiểm tra số hữu hạn. Đây không phải định dạng raw VNDIRECT mà validate_bars()
hiện đang nhận; không coi hai định dạng đã dùng thay nhau được.

### Phần rút gọn và lịch sử khởi tạo

Payload chỉ giữ tham số cần thay khi thử chiến lược. `warmup_bars: 150` là số
nến đã đóng tối thiểu, **tính cả nến t**, không phải chu kỳ EMA150. Đây là yêu
cầu riêng của v1; không đặt 150 làm mặc định cho mọi chiến lược. Khi bỏ trường
này, không áp thêm ngưỡng số nến riêng; các chỉ báo được tham chiếu vẫn phải
có giá trị hợp lệ. Ví dụ SMA với period=20 cần 20 mẫu để tính, ref có shift=1
còn cần giá trị nến trước. Đó là yêu cầu của công thức đã khai báo, không phải
mặc định ngầm cho warmup_bars. V1 vẫn truyền 150 và phải đáp ứng cả ngưỡng
này lẫn điều kiện đủ dữ liệu của từng chỉ báo.

SMA200 cần
200 mẫu VNINDEX, nền giá cần 65 nến trước và khối lượng cần 50 nến trước.
Thiếu mẫu thì chưa đánh giá được. V1 giữ kỳ báo cáo sáu tháng; lịch sử khởi
tạo không phải lý do tự lùi ngày bắt đầu báo cáo.

Các chi tiết sau được định nghĩa một lần trong thành phần thực thi, không
bắt người gọi lặp lại trong mỗi payload:

- Chỉ báo: mặc định dùng nến đã đóng hiện tại (`shift=0`), EMA khởi tạo bằng
  SMA N mẫu, BB dùng `ddof=0`, MFI xử lý dòng tiền bằng 0 theo rule đã chốt.
  Chu kỳ, nguồn dữ liệu và hệ số BB vẫn truyền được. `histogram: "line"` vẫn
  giữ tường minh vì đây là cách biểu diễn riêng đã chọn cho v1.
- Kiểm tra dữ liệu: thiếu đầu vào thì không đánh giá; lịch sử chỉ báo v1 lấy VNINDEX; daily pivot tách theo
  hợp đồng và loại nến theo data contract, không biến chúng thành cờ bật/tắt.
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

Đây là ngữ nghĩa của các thành phần được mô tả trong thiết kế này, chưa phải
hành vi đã triển khai. Engine không chọn rule theo tên CANSLIM hoặc symbol.
Các ngưỡng, ưu tiên thoát, trailing, giờ giao dịch và giới hạn vị thế vẫn nằm
trong strategy. Cấu hình thực tế sau khi bổ sung mặc định phải lưu cùng kết
quả để chạy lại được; không chỉ lưu payload rút gọn.

### Diễn giải các điều kiện v1

- `indicators` nằm trong strategy; phần thực thi công thức sẽ đặt ở indicators.py.
  EMA/MACD/BB/MFI chưa được triển khai chỉ vì đã xuất hiện trong payload.
  SMA/EMA/BB/MACD/MFI cần 150 nến VNINDEX đã đóng tính cả t, không dùng
  ATO/ATC; không khởi tạo lại chuỗi chỉ báo khi hợp đồng giao dịch chuyển kỳ.
- EMA seed bằng SMA N mẫu đầu, tính tiếp từ N+1. BB chia phương sai cho N.
  MACD line = EMA12 − EMA26; histogram bằng line; signal EMA9 chỉ hiển thị.
  MFI theo TP=(H+L+C)/3 và dòng tiền TP×Volume; TP không đổi thì bỏ dòng đó;
  hai dòng cùng bằng 0 ưu tiên MFI=50 trước hai quy tắc một dòng bằng 0.
- CLASSIC_PIVOT là thành phần dự kiến: P=(H+L+C)/3, R1=2P−L, R2=P+(H−L),
  S1=2P−H, S2=P−(H−L). Chỉ lấy daily phiên trước của cùng hợp đồng đã khả dụng.
- `entry` và `exit` bắt buộc. `all` yêu cầu tất cả điều kiện đạt; `any` yêu cầu
  ít nhất một điều kiện đạt. Giá trị là mảng không rỗng, có thể lồng các nhóm.
  Chuỗi trong any tham chiếu conditions trong cùng nhóm, không tra mẫu đã lưu.
- `gt/gte/lt/lte` là >, >=, <, <=; `add/sub/div/mul` là cộng, trừ, chia, nhân;
  min/max chọn mức giá và floor làm tròn xuống. Các phép hai ngôi nhận hai toán
  hạng; floor nhận một. `ref.shift: 1` lấy giá trị chỉ báo của nến trước trong
  cùng chuỗi VNINDEX. Số thập phân cần đọc bằng Decimal, không tính qua float.
- `entry.conditions.LONG/SHORT` là hai nhánh AND. any xét hai hướng; cả hai đạt
  thì không giao dịch và ghi SIGNAL_CONFLICT. Chỉ xét khi flat, không pending,
  đủ input kể cả daily pivot, trong giờ tín hiệu gồm hai đầu. LONG mở mua, SHORT
  mở bán; không tăng thêm vị thế hoặc đổi hướng/vào lại trong nến vừa thoát.
- `exit.targets` tạo tại entry fill: long max(R1, entry+6), max(R2, entry+12);
  short min(S1, entry−6), min(S2, entry−12). Không cập nhật lại target mỗi nến.
  Thiếu daily pivot thì không mở lệnh. Target/stop active ngay sau Open fill.
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

Đây mới là biểu diễn được chọn trong đặc tả; chưa triển khai bộ tiếp nhận này.
Các cấu trúc protective_stop/target_touch/risk_and_margin là khai báo cho các
thành phần thực thi cần bổ sung; chưa phải phép toán engine hiện tại hiểu được.

### Thời gian và đơn vị: trường bắt buộc/tùy chọn

Áp dụng riêng cho mỗi chuỗi trade_data/market_data trong thiết kế mới:

Khung thời gian dùng `resolution` theo cách ghi của VNDIRECT: `"5"` là 5 phút,
`"D"` là ngày. Cả trade_data và market_data dùng cùng tên trường này, không dùng
`timeframe` hoặc giá trị `"5m"` trong payload mới. `resolution` bắt buộc cho mỗi
chuỗi; ký hiệu dữ liệu ngày không có nghĩa engine đã hỗ trợ mọi cách sử dụng daily.

| Trường            | Bắt buộc                                          | Khi không truyền                                                                                 |
| ------------------- | --------------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| bars[].open_time    | Có                                                 | Không suy thời điểm mở nến                                                                   |
| bars[].close_time   | Không, với nến 5 phút theo quy ước đã chốt | open_time + 300 giây                                                                              |
| bars[].available_at | Không, với cùng quy ước mô phỏng             | Bằng close_time sau khi xác định thời điểm đóng                                           |
| timestamp_unit      | Không                                              | "s": Unix giây; truyền "ms" nếu dữ liệu dùng mili giây, không tự đoán qua độ dài số |
| timezone            | Không trong phạm vi thị trường Việt Nam       | "Asia/Ho_Chi_Minh", dùng xác định ngày báo cáo và giờ phiên                              |
| price_unit          | Không cho thử logic trên giá                    | Không tự gán đơn vị hoặc nhân/chia giá; giữ giá trị đầu vào                         |

Ví dụ payload trên bỏ các trường tùy chọn này. Với open_time=1773800100,
hệ thống xác định close_time=1773800400 và available_at=1773800400. Nếu khai báo
timestamp_unit="ms", quy đổi về cùng đơn vị nội bộ trước khi cộng thời lượng.
Khi cung cấp thời gian tường minh, kiểm tra open_time < close_time <= available_at;
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

### 3.3. Có cần loại chứng khoán không?

Đối với tầng dữ liệu giá/chỉ báo/điều kiện, không cần trường `asset_class` bắt buộc
hoặc danh sách đóng chỉ nhận HPG/VN30F1M. Chiến lược tham chiếu `trade_data` và
`market_data`; kiểm tra các cột/chu kỳ/đơn vị mà nó sử dụng, không dựa vào tên
loại chứng khoán để chọn công thức. CANSLIM vẫn cần khối lượng khi có điều kiện
khối lượng/MFI; "quan tâm giá" không có nghĩa chỉ một cột Close là đủ cho mọi rule.

Tầng khớp lệnh/tài khoản vẫn cần mô hình đã chọn và các thông số thực sự ảnh hưởng
kết quả. Mô hình chuẩn hóa phù hợp để thử luồng trên chuỗi giá; không diễn giải
P/L đó thành tiền hợp đồng v1. V1 vẫn cần hệ số hợp đồng, bước giá, phí, ký quỹ,
lịch phiên/đáo hạn và dữ liệu hợp đồng thực theo các quyết định đã chốt. Các thông
số thuộc execution/account và bảng dữ liệu đi kèm, không bắt suy từ asset_class.

Nhãn symbol có thể tùy chọn cho thử giá, nhưng mã hợp đồng thực hoặc bảng ánh xạ
vẫn cần khi quy tắc yêu cầu tách lịch sử từng hợp đồng. Không bỏ yêu cầu này của
v1 chỉ vì API không bắt nhập symbol ở cấp chung.

### Dữ liệu trực tiếp

- Mỗi chuỗi có tên để quy tắc tham chiếu; đó là tên trong yêu cầu, không phải
  ID của một bộ dữ liệu đã lưu trên máy chủ.
- OHLCV được truyền trong JSON. Dữ liệu phụ cũng truyền trong yêu cầu khi
  chiến lược cần; không tự thêm VNINDEX chỉ vì symbol là VN30F1M.
- `trade_data` và `market_data` có thể khác số nến, khung thời gian và giờ phiên.
  Tại thời điểm quyết định t chỉ lấy bản ghi market có available_at <= t; không
  ghép theo số thứ tự dòng hoặc dùng Close cuối ngày khi ngày đó chưa kết thúc.
  Mỗi nến thị trường chỉ là một mẫu chỉ báo, không nhân bản để khớp số nến trade.
  Thiếu market_data mà quy tắc có tham chiếu thì báo lỗi; thiếu lịch sử cần thiết
  thì chưa đánh giá được, không tự coi điều kiện thị trường đã đạt.
- VNINDEX không thay dữ liệu daily của hợp đồng. V1 dùng chỉ báo 5 phút VNINDEX, đồng thời vẫn cần OHLC ngày trước của cùng hợp đồng để tính pivot.
  `market_data` không tự được dùng thay đầu vào daily đó.
- Nến intraday phải xác định thời điểm mở/đóng và thời điểm dữ liệu được phép
  sử dụng. Có thể khai báo quy ước chung nếu áp dụng đồng nhất theo hợp đồng dữ
  liệu; không mặc định mọi chuỗi có cùng thời gian khả dụng.
- Timestamp Unix mặc định giây; khai báo timestamp_unit nếu dùng mili giây.
  Phiên giao dịch/kỳ báo cáo theo timezone đã truyền hoặc mặc định Việt Nam;
  không suy ngày phiên từ ngày UTC một cách ngầm định.
- Lịch phiên, bảng mã hợp đồng/đáo hạn, ký quỹ và chi phí có thể nằm trong các
  bảng JSON đi kèm khi mô hình cần. Không bắt đăng ký chúng bằng dataset_version.
- Vẫn kiểm tra số hữu hạn, OHLC hợp lệ, thứ tự/trùng thời gian, dữ liệu cần thiết
  và phiên thiếu theo hợp đồng dữ liệu. Không tự ghép nguồn hoặc điền giá thiếu.

Tiếp nhận JSON không thay đổi [quy ước dữ liệu v0](../data/vn30f1m/data-contract.md)
hoặc [quy ước dữ liệu v1](../data/vn30f1m/data-contract-v1.md).
Thiếu lịch sử được xử lý theo quy tắc chiến lược; không tự rút ngắn báo cáo hoặc
đổi chu kỳ chỉ báo. V1 giữ kỳ sáu tháng đã chốt. Ngoại lệ rút kỳ chỉ thuộc lần
chạy VN30F1M với CANSLIM v0.

## 4. Tham khảo hai thư viện và đối chiếu source

| Thành phần                | Backtrader                                                                | Backtesting.py                                                                                | Source hiện tại                                                                    |
| --------------------------- | ------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------ |
| Dữ liệu                   | Đưa đối tượng dữ liệu vào Cerebro                                | Đưa DataFrame vào Backtest                                                                 | API chọn bộ đã lưu; thiết kế mới chuyển sang JSON trực tiếp               |
| Chỉ báo                   | Lớp Indicator, có chỉ báo dựng sẵn và có thể tự viết lớp mới | Nhận hàm tính chỉ báo qua Strategy.I(); có thể tự viết hoặc dùng thư viện ngoài | Các hàm sma, highest, lowest trong domain/indicators.py                            |
| Chiến lược               | Lớp Strategy với logic do người viết cung cấp                       | Lớp Strategy, thường định nghĩa init()/next()                                           | Lớp CanslimStrategy và hàm run; API chọn qua danh sách đăng ký               |
| Lưu mẫu trước khi chạy | Không phải yêu cầu của việc gọi thư viện                         | Không phải yêu cầu của việc gọi thư viện                                             | API hiện buộc có mục đăng ký; đây là giới hạn cần bỏ khỏi luồng mới |

Nguồn chính thức:

- [Backtrader — Indicator Development](https://www.backtrader.com/docu/inddev/).
- [Backtrader — Quickstart](https://www.backtrader.com/docu/quickstart/quickstart/).
- [Backtesting.py — Quick Start, phần Strategy](<https://kernc.github.io/backtesting.py/doc/examples/Quick%20Start%20User%20Guide.html>).
- [Backtesting.py — Strategy.I và Backtest](https://kernc.github.io/backtesting.py/doc/backtesting/backtesting.html).

Backtesting.py không bắt tự viết mọi chỉ báo: Strategy.I nhận hàm trả chuỗi giá
trị, có thể là hàm của TA-Lib hoặc thư viện khác. Wrapper này quản lý cách công
bố/hiển thị kết quả; không thay người viết định nghĩa công thức chỉ báo.

**Project dùng engine tự viết.** Xét cách tổ chức chỉ báo, nó gần hướng hàm tính
của Backtesting.py; không dùng thư viện đó và chưa có cơ chế tương đương Strategy.I.
CANSLIM phối hợp các hàm thành snapshot riêng rồi đánh giá điều kiện. Engine
cấp phần dữ liệu đã khả dụng và xử lý tín hiệu, khớp lệnh, tài khoản.

Giữ các hàm chỉ báo đang có là đủ cho phần đã hỗ trợ. Chỉ cần lớp có trạng thái
khi thật sự phải cập nhật tích lũy từng nến hoặc chia sẻ trạng thái tính toán;
không đổi tất cả chỉ báo thành lớp chỉ để giống Backtrader.

## 5. Kiểm tra chiến lược chưa lưu

Luồng đề xuất:

`JSON đầu vào → kiểm tra dữ liệu/quy tắc → tạo phần đánh giá → engine → kết quả`

1. Kiểm tra cấu trúc và kiểu dữ liệu trong yêu cầu.
2. Kiểm tra tham chiếu chuỗi/chỉ báo/tham số có tồn tại ngay trong nội dung gửi lên.
3. Kiểm tra chu kỳ, đơn vị, số hữu hạn và quan hệ tham số theo thành phần được dùng.
4. Kiểm tra toán tử, hành động và cách tính tiền engine đã hỗ trợ.
5. Kiểm tra thời gian khả dụng, lịch sử khởi tạo và thứ tự thực thi.

Không có bước bắt chiến lược tồn tại trong kho mẫu. Có thể dùng cùng bộ kiểm tra
cho xem trước và chạy; người gọi không bắt buộc gọi một API kiểm tra riêng trước.
Hợp lệ có nghĩa đủ cấu trúc và khả năng để thực thi, không khẳng định có lợi nhuận
hoặc chứng minh mọi thuật toán tùy ý đều không sử dụng dữ liệu tương lai.

Các quy tắc chặn dữ liệu tương lai vẫn phải nằm tại ranh giới cấp dữ liệu cho
chỉ báo/chiến lược và được kiểm tra bằng các tình huống cắt chuỗi tại thời điểm t.

## 6. Mẫu có sẵn và kết quả

Mẫu có sẵn chỉ giúp lấy nhanh nội dung `strategy`, sau đó sửa/thử như một yêu
cầu mới. Việc lưu hoặc cập nhật mẫu không nằm trong điều kiện chạy backtest.

Kết quả lưu nội dung dữ liệu, định nghĩa chiến lược và cấu hình thực tế đã dùng,
hoặc liên kết nội bộ tới bản sao bất biến của nội dung đó. Nếu cần mã băm hoặc
mã nhận diện để lưu và mở lại kết quả, máy chủ tự tạo; người gọi không phải quản
lý phiên bản dữ liệu/chiến lược. Chỉ lưu mã băm mà bỏ nội dung không đủ để chạy lại.

Giữ run_id để đọc lại kết quả là độc lập với việc bắt nhập dataset_id/strategy_id.
Không sửa kết quả v0 đã lưu. Các trường kết quả tài khoản phái sinh theo đặc tả v1.

## 7. Phần cần định nghĩa tiếp

- Các phép so sánh, all/any, tham chiếu, entry/exit và tham số quản trị v1 đã
  biểu diễn tại mục 3.1. Cần triển khai kiểm tra cấu trúc và các thành phần có
  trạng thái (stop/target/trailing/sizing), không chỉ bộ tính boolean.
- Phép giao cắt chỉ bổ sung khi có chiến lược cần; v1 hiện dùng so sánh.
- Ánh xạ mẫu chuỗi giá tại mục 3.1 vào bộ tiếp nhận và cấu trúc bảng phụ v1
  (daily hợp đồng, lịch, ký quỹ) theo hợp đồng dữ liệu.

Đây là các quyết định về cách biểu diễn, không yêu cầu người dùng chốt lại quy
tắc CANSLIM v1 đã có. Chưa thêm một ngôn ngữ công thức hoặc cơ chế thực thi mã
Python từ HTTP trong lượt sửa tài liệu này.

## 8. Source hiện có và phần chưa triển khai

Hiện POST /api/backtests vẫn nhận:

```text
dataset_id, dataset_version, symbol, start_date, end_date,
strategy_id, strategy_version, strategy_params, initial_cash, fee_rate, slippage_rate
```

API hiện tra danh sách đăng ký trước khi kiểm tra tham số. Đã hỗ trợ tham số riêng
của v0 và lưu/đọc lại chúng; chưa nhận dữ liệu JSON trực tiếp hoặc định nghĩa
chiến lược mới ngay trong yêu cầu. GET /api/strategies hiện trả các chiến lược
đã đăng ký, không phải bộ kiểm tra mọi chiến lược do người dùng gửi.
Request hiện cũng chưa có `trade_data` hoặc `market_data`; VNINDEX đang được
nạp từ bộ dữ liệu đã lưu. Hai trường mới ở mục 3 là thiết kế cần triển khai.

Các kiểm thử từ lượt 26/09 chỉ xác nhận luồng tham số đã triển khai; không chứng
minh thiết kế ngày 28/09 đã chạy. Phần tham số đó có thể tái sử dụng ở các thành
phần chỉ báo/quy tắc, nhưng không dùng sự tồn tại của mẫu làm điều kiện kiểm tra.

Bảng kiểm triển khai nằm riêng tại `.agents/checklists/engine-upgrade-checklist.md`.
