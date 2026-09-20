# Data Contract — VN30F1M 5 phút

> **Storage 18/09/2026:** [Parquet + JSON](../../plans/technical-plan.md#6-persistence-parquet-json) thay target pickle trong kế hoạch bên dưới. Raw nguồn giữ nguyên; SQLite/PostgreSQL cho metadata/session agent còn chờ chốt. Nội dung implementation/mốc cũ giữ để truy vết; chưa migrate code hoặc nghiệm thu storage mới.


Cập nhật: 18/09/2026. Contract dữ liệu này không tự quyết định strategy.

**Xác nhận 18/09:** strategy/execution chính dùng VN30F1M 5 phút; 1D chỉ hỗ trợ,
không thay bằng backtest daily. Ưu tiên source → API → notebook, chưa cần agent.
C01–C03 đã chốt window 200/65/50 nến 5 phút; C04 đã chốt Open + 5 phút,
ATC và price points; user cho phép rollover map tham khảo, giữ vị thế qua đáo hạn.
Policy tại [runtime-policy.json](runtime-policy.json). Source/API/notebook đã
implement và test fixture; report 15/03–15/09 còn thiếu lịch sử trước 18/03.
Thứ tự triển khai tại [Technical Plan](../../plans/technical-plan.md).

## Snapshot warm-up mới được phép lấy — C06

### JSON user cung cấp và assumption C04/C06 mới

- Kỳ báo cáo đã chốt: **15/03/2026–15/09/2026**, inclusive theo UTC+7.
- `data/30f1m_5&from=1772323200&to=1789516800.json`: 6.076 rows,
  18/03 09:00–15/09 14:45; SHA-256
  `0a64c66974969070dbcdf811be40e3c6400d541f5b2834430c3fac188c4e9557`.
- `data/VNINDEX_5&from=1772323200&to=1789516800.json`: 6.227 rows,
  18/03 09:15–15/09 15:05; SHA-256
  `c5810cdcf96b42936c9d403092ee3361fcd694d108c269f1adb1af5098a5def6`.
- Cả hai có 124 ngày quan sát, không có warm-up trước report start. Source
  extraction time chưa xác nhận: null; import time là field riêng.
- Timestamp đầu bar; bar_close_at/available_at = bar_open_at + 5 phút là
  assumption user chốt cho mô phỏng, áp dụng cả record ATC 14:45. Không bỏ
  record; chưa mô phỏng auction matching. Giá futures là index points như raw.
- Market SMA200 tính trên nến VNINDEX riêng; tại futures Close chỉ dùng market
  bar có available_at <= decision. Thiếu 200 nến là UNEVALUABLE, không daily fallback.
- C05 dùng policy JSON tĩnh: schema_version=1, timezone=Asia/Ho_Chi_Minh,
  trading_dates (ngày được phép giao dịch), sessions cho mỗi symbol với
  required_times/optional_times là label HH:MM, rollover ranges có start/end
  ngày inclusive và contract. Không lấy observed dates làm lịch đã xác nhận.
- Runtime policy có nguồn lịch nghỉ HNX và map user cung cấp. User chốt
  rollover_action=hold, cho phép mã tham khảo như assumption; không forced exit.
- User xác nhận giữ report 15/03–15/09 và bổ sung intraday history. Với input
  hiện tại actual POST /api/backtests trả 422 MISSING_EXPECTED_BAR ngày 16/03.
  Không đổi range, fill hoặc dùng daily để tạo run thành công. Runbook tại
  [API/notebook](../../plans/vn30f1m-backtest-runbook.md).
- Thiếu policy/map, expected bar/session hoặc range map không phủ input thì
  fail validation trước core. Không pin dữ liệu thiếu thành run thành công.


- VN30F1M: `https://dchart-api.vndirect.com.vn/dchart/history?resolution=5&symbol=VN30F1M&from=1772323200&to=1789516800`
- VNINDEX: `https://dchart-api.vndirect.com.vn/dchart/history?resolution=5&symbol=VNINDEX&from=1772323200&to=1789516800`
- Capture offline giữ raw bytes riêng theo content hash và extraction time UTC.
  Manifest bundle JSON có schema/validator version, source URL, symbol/timeframe,
  dataset ID/version/hash/count/range/timezone cho từng input; publish chỉ sau
  khi cả hai payload pass schema. Không đổi raw/hash/manifest của chart cũ.
- Timestamp semantics và volume unit vẫn unconfirmed; manifest capture không
  đồng nghĩa snapshot đã đủ điều kiện backtest. Không tự infer session/holiday
  hoặc rollover map từ chuỗi giá.
- R1 cần 200 nến market 5 phút; R2/R3 cần 65/50 nến trước t. Chưa dùng 1D.
  Report range và warm-up coverage phải được kiểm tra riêng trước nghiệm thu.

## 1. Snapshot đã chốt cho MVP

- Source: [VNDIRECT dchart](https://dchart-api.vndirect.com.vn/dchart/history?resolution=5&symbol=VN30F1M&from=1773594000&to=1789463924);
  `symbol=VN30F1M`; `resolution=5`.
- Query window: Unix `1773594000..1789463924`.
- Payload quan sát: 6.174 rows, 126 ngày, từ `2026-03-16 09:00` đến
  `2026-09-15 14:45` theo UTC+7; 49 records/ngày.
- SHA-256 payload đã lấy: `5930f355e7e5bbc8663835a60fca654a31cc5a83184d534008c284a8d3bbaad5`.
- Dataset ID: `vndirect-vn30f1m-5m-20260316-20260915`; version phải bất biến
  và đổi cùng hash nếu payload thay đổi.

## 2. Bar contract

Mỗi row cần timestamp Unix và finite `open/high/low/close/volume`; price `> 0`,
volume `>= 0`, `high >= max(open, close)`, `low <= min(open, close)`. Arrays
`t/o/h/l/c/v` phải cùng độ dài; timestamp unique và tăng nghiêm ngặt.

Payload quan sát mỗi ngày có các timestamp 09:00–11:25, 13:00–14:25 theo bước 5
phút và một record 14:45. Ý nghĩa record 14:45 và bộ timestamp strategy thực sự sử
dụng phải được rule được duyệt quyết định; data layer không tự loại record.

## 3. Provenance và giới hạn

- Core không gọi live endpoint; snapshot được lưu cùng URL, extraction time, hash,
  count/range/timezone và validator version.
- `VN30F1M` không cung cấp actual contract/roll map trong payload; mọi strategy
  phải ghi rõ cách xử lý rollover và vị thế qua ngày.
- Chưa coi volume unit, timestamp label semantics hoặc record 14:45 đã được nguồn
  xác nhận. Không tự suy diễn hoặc sửa payload.
- Pickle chỉ persist validated snapshot/result; không thay raw immutable artifact.

## 4. Run/result contract

Theo xác nhận 17/09, run giữ mô hình tiền normalized trong
[CANSLIM Rule](../../strategies/canslim-rules.md). Run config tối thiểu gồm dataset
ID/version/hash cho mọi snapshot VN30F1M và VN-Index, symbol, timeframe nguồn,
strategy/execution 5 phút, timeframe từng indicator/support series, timezone,
kỳ báo cáo/warm-up, mapping và assumption đã xác nhận, strategy ID/parameters, initial_cash,
fee_rate, slippage_rate và nhãn `normalized simulation`. Không yêu cầu multiplier,
margin/tax/settlement phái sinh cho mô hình này.

Result giữ metadata, signals, orders, fills/quantity, trades, equity history và
summary. Nếu lưu timestamp intraday, phải giữ UTC offset hoặc timezone rõ ràng;
đánh giá/equity theo Close bar 5 phút hợp lệ; tập bar/session chờ C04–C05.
Đây là contract mục tiêu, chưa phải
bằng chứng runtime đã hỗ trợ VN30F1M.

### Dữ liệu strategy đã chốt và còn thiếu

- Giữ VN-Index cho R1. Snapshot VN30F1M không chứa VN-Index; chọn market series
  như cũ chưa xác nhận snapshot VN-Index nào có đủ thời gian phủ và warm-up.
- Nguồn, strategy và execution chính là 5 phút. C01–C03 đã xác nhận window
  200/65/50 nến 5 phút. Alignment với VN-Index và available_at còn thiếu C04;
  không tự ghép dữ liệu để tạo đủ history. Các phương án daily dưới đây là
  giải thích lịch sử, không phải mapping đã chọn hiện tại.
- Nếu R1 dùng 1D, cần ít nhất 200 VN-Index daily closes đã available. VN30F1M
  1D không thay VN-Index; dữ liệu cùng range 126 phiên không đủ SMA200 daily.
- Nếu R2/R3 giữ window daily, cần đủ 65/50 phiên trước decision và chốt phép
  so volume cùng kỳ đo; không tự so volume 5 phút với daily average.
- Support snapshot có manifest/version/hash/extraction/range riêng, được pin
  cùng run. Tại decision t chỉ dùng dữ liệu available_at <= t; không dùng daily
  Close/High/Low/Volume của phiên chưa hoàn tất. Một daily bar dùng làm context
  cho nhiều decision không trở thành nhiều mẫu daily để tính indicator.
- Có thể mở rộng lịch sử trước kỳ báo cáo để warm-up mà giữ kỳ báo cáo.
  Nguồn/range được phép lấy chờ C06; không tự fetch hoặc fill missing data.

### Lịch sử đề xuất gộp daily — không thay luồng 5 phút

Gộp daily nghĩa là lấy toàn bộ bar hợp lệ của một phiên để tạo một OHLCV ngày:
Open của bar đầu, High lớn nhất, Low nhỏ nhất, Close của bar cuối, và tổng Volume
(chỉ khi volume nguồn được xác nhận là volume từng bar có thể cộng).
Strategy daily sẽ đánh giá sau khi phiên hoàn tất; chart/raw vẫn có thể giữ nến
5 phút. Không được dùng Close/High/Low/Volume cả ngày trước khi phiên đóng.

Đây là giải thích phương án cũ; ngày 18/09 đã chọn 5 phút làm timeframe chính.
Chưa cho phép resample kể cả để tạo support data. Trước implementation cần
chốt timeframe, session boundary, timestamp labels, record 14:45, volume và
phiên thiếu. Nếu được duyệt, dữ liệu daily dẫn xuất phải có provenance/version
riêng liên kết với raw snapshot; không sửa raw hoặc tự bù missing bars.

## 5. Chart snapshot triển khai 17/09

`GET /api/market-chart` trả `{metadata, bars}` cho snapshot đã chốt; chưa gắn run
và không trả fills/equity giả. `start`/`end` là ngày ISO optional, lọc inclusive
theo UTC+7; ngược range/sai ngày trả 422. Khoảng không có bar trả bars rỗng.
Mỗi bar gồm `time` (Unix seconds nguyên), `open/high/low/close/volume`, giữ nguyên
timestamp và giá nguồn. Không loại record 14:45 hoặc tự thêm phiên thiếu.

Mỗi lần đọc kiểm tra hash raw, arrays/status/order/OHLCV và 6.174 records/range
đã chốt. Thiếu hoặc không đọc được file trả 503; integrity lỗi trả 409, không lộ
local path. Raw local vẫn Git ignored, path cấu hình qua VN30F1M_SNAPSHOT_PATH.
Version chart dùng chính content hash; metadata có total/selected bars và mode
market_snapshot. Extraction time chưa có evidence xác nhận nên giữ null; volume
unit và timestamp semantics tiếp tục unknown/unconfirmed. Đây là bằng chứng
chart snapshot, chưa phải acceptance provenance/run đầy đủ hoặc pickle migration.
