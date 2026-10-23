# Đặc tả API backtest

## 1. Tổng quan

API nhận dữ liệu giá và chiến lược JSON, kiểm tra đầu vào, mô phỏng giao dịch và lưu kết quả.

Luồng sử dụng: chuẩn bị dữ liệu → kiểm tra → chạy → đọc kết quả. Hai endpoint POST dùng cùng cấu trúc request.

Xem [sơ đồ tuần tự](system-design.md#11-một-yêu-cầu-post-apibacktests-đi-qua-hàm-nào) để tra lời gọi và thứ tự xử lý từng nến.

- Chỉ dùng dữ liệu đã khả dụng tại thời điểm quyết định.
- Tín hiệu sau Close chỉ khớp tại Open kế tiếp theo quy tắc thực thi.
- Tín hiệu, lệnh, lần khớp và giao dịch đã đóng là các đối tượng khác nhau.
- Chỉ tự tải khi bật `auto_fetch_data`; không điền dữ liệu giá bị thiếu.
- `accounting.model` chọn mô hình tính tiền; symbol không chọn chiến lược.
- [CANSLIM v1](../strategies/canslim-v1-rules.md): quy tắc chiến lược.
- [Tính tiền normalized](normalized-accounting.md): công thức sổ tiền.
- [Hợp đồng dữ liệu](../data/vn30f1m/data-contract-v1.md): nguồn, phiên và đáo hạn.

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

| Endpoint                              | Nội dung khi thành công                                                                    |
| ------------------------------------- | --------------------------------------------------------------------------------------------- |
| `GET /api/backtests`                | Danh sách các lần chạy thành công theo thứ tự kho lưu trữ                           |
| `GET /api/backtests/history`        | Tóm tắt lịch sử có bộ lọc và phân trang; không trả bảng kết quả hoặc chỉ báo |
| `GET /api/backtests/{run_id}`       | Kết quả một lần chạy                                                                     |
| `GET /api/backtests/{run_id}/input` | Đầu vào đầy đủ và thông tin chính sách đã lưu                                   |
| `GET /api/backtests/{run_id}/chart` | Dữ liệu biểu đồ của lần chạy                                                          |

- `run_id` là UUID; các endpoint GET đọc kết quả đã lưu.
- Lượt đang chạy hoặc thất bại: đọc chi tiết trả `404`.

### 2.4. Lọc lịch sử để hiển thị trên web

- Lọc tại máy chủ, kết hợp điều kiện bằng AND; khoảng từ/đến gồm hai đầu.
- Kết quả theo thứ tự kho lưu trữ. UUID không biểu diễn thời gian tạo.

| Tham số query           | Bắt buộc | Ý nghĩa                                                                       |
| ------------------------ | ---------- | ------------------------------------------------------------------------------- |
| `min_total_return_pct` | Không     | Tỷ suất sinh lời tối thiểu theo %, nhập`10` nghĩa là 10%              |
| `max_total_return_pct` | Không     | Tỷ suất sinh lời tối đa theo %                                             |
| `min_equity`           | Không     | Vốn cuối kỳ tối thiểu, so với`summary.final_equity`                     |
| `max_equity`           | Không     | Vốn cuối kỳ tối đa, giữ nguyên đơn vị của kết quả                  |
| `limit`                | Không     | Số tóm tắt tối đa; mặc định 20, hợp lệ từ 1 đến 100                |
| `after`                | Không     | UUID trong`next_cursor` của trang trước; giữ các bộ lọc khi sang trang |

Ví dụ: `/api/backtests/history?min_total_return_pct=0&max_total_return_pct=20&limit=20`.

**Phản hồi**

- Thành công: `200`, gồm `items` và `next_cursor`; `next_cursor: null` là hết kết quả.
- Mỗi item có `run_id`, `symbol`, `resolution`, `start_date`, `end_date`, `money_unit`, `total_return`, `final_equity`, `run_at`. Trường mô tả của lịch sử cũ có thể là null.
- `run_at`: thời điểm bắt đầu chạy, dạng ISO 8601 có múi giờ, lưu tại `metadata.run_at`.
- Lịch sử cũ: dùng ngày tạo file JSON; nếu thiếu thì dùng ngày sửa cuối. File và mã băm cũ giữ nguyên.
- `total_return` và `final_equity` là chuỗi số; `"0.1"` ở `total_return` tương ứng 10%.
- `money_unit` xác định VND hoặc đơn vị giá của mô hình.

**Lỗi**

- `422`: số không hữu hạn, giới hạn từ lớn hơn đến, `limit` ngoài khoảng hoặc `after` sai UUID.
- `409`, mã `RESULT_STORAGE_INVALID`: kho lưu trữ đọc hoặc kiểm tra không hợp lệ.
- Máy chủ kiểm tra tính toàn vẹn từng kết quả. Web dùng trang tóm tắt để giảm dữ liệu tải.

## 3. Cấu trúc request

**Payload nhận một JSON object với các trường chính dưới đây.**
Tên trường và từ khóa phân biệt hoa/thường. Trường ngoài cấu trúc cho phép sẽ bị từ chối và trả lỗi 422.

| Nhóm               | Kiểu JSON        | Bắt buộc                                                          | Nội dung                                                                       |
| ------------------- | ----------------- | ------------------------------------------------------------------- | ------------------------------------------------------------------------------- |
| `auto_fetch_data` | boolean           | Không; mặc định`false`                                        | `true` để ưu tiên tự lấy cả hai nguồn và bỏ qua dữ liệu nhập tay |
| `trade_data`      | object hoặc null | Khi không bật tự lấy                                            | Chuỗi giá dùng giao dịch                                                    |
| `market_data`     | object hoặc null | Khi dữ liệu tự lấy và được chỉ báo/biểu thức sử dụng | Chuỗi thị trường tham chiếu                                                |
| `strategy`        | object            | Có                                                                 | Chỉ báo, vào/thoát lệnh, số lượng và giới hạn ngày                  |
| `execution`       | object            | Có                                                                 | Cách khớp và trượt giá                                                    |
| `accounting`      | object            | Có                                                                 | Mô hình tính tiền và phí                                                  |
| `initial_cash`    | số thập phân   | Có                                                                 | Vốn ban đầu, lớn hơn 0                                                     |
| `report`          | object hoặc null | Không                                                              | Khoảng ngày báo cáo                                                         |

Quy tắc chọn nguồn cho cả `/api/backtests/validate` và `/api/backtests`
(cập nhật 09/10/2026):

- **Nhập tay:** bỏ `auto_fetch_data` hoặc đặt `false`, gửi `trade_data`;
  gửi thêm `market_data` nếu chiến lược sử dụng nguồn này. Cách gửi cũ vẫn hợp lệ.
- **Tự lấy:** đặt `auto_fetch_data: true`. API bỏ qua cả hai nguồn nhập tay trước kiểm tra và dùng hai nguồn tải về.

| `auto_fetch_data`          | Dữ liệu nhập tay                             | Xử lý                                                   |
| ---------------------------- | ----------------------------------------------- | --------------------------------------------------------- |
| `true`                     | Có hoặc không, hợp lệ hoặc chưa hợp lệ | Bỏ qua cả hai nguồn nhập tay, tự tải cả hai nguồn |
| `false` hoặc bỏ trường | Đủ và hợp lệ theo chiến lược            | Dùng dữ liệu nhập tay                                 |
| `false` hoặc bỏ trường | Thiếu hoặc chưa hợp lệ                     | Trả 422 như trước                                     |

- Chiến lược, khớp lệnh, tính tiền, vốn và `report` vẫn được kiểm tra.
- Khi tự lấy, `report` được đối chiếu với dữ liệu tải về. Lỗi tải hoặc dữ liệu sai làm yêu cầu dừng trước khi tạo lượt chạy.
- `auto_fetch_data` chỉ nhận boolean JSON.

Máy chủ lấy **VN30F1M và VNINDEX 5 phút từ VNDIRECT**.

**Khoảng tải**

- Bỏ `report`: `to` là Unix giây lúc bắt đầu lấy; `from` lùi sáu tháng theo `Asia/Ho_Chi_Minh`, giữ giờ/phút/giây.
- Có `report`: lùi `from` theo số nến khởi tạo lớn nhất từ `warmup_bars`, chỉ báo và `shift`. MFI cần `period + 1`; MACD cần `slow_period + signal_period - 1`.
- ATO cần ít nhất một nến liên tục trước kỳ. Đếm nến theo lịch phiên; contract chỉ đếm giờ liên tục.
- Hai nguồn dùng chung mốc tải sớm nhất. Mỗi nguồn giữ số nến khởi tạo cần dùng và toàn bộ dữ liệu trong kỳ.
- Lịch sử có thể bắt đầu giữa phiên; kiểm tra khoảng thiếu từ mốc này. Kỳ báo cáo được kiểm tra đủ phiên.
- `to` là 23:59:59 của `report.end_date`; nếu là hôm nay thì dùng thời điểm hiện tại. Ngày kết thúc trong tương lai bị từ chối.
- Thiếu mẫu khởi tạo: báo chưa đánh giá được, giữ nguyên kỳ báo cáo và ngưỡng. Khoảng thiếu được giữ nguyên.
- `metadata.auto_fetch.warmup_bars_requested` ghi lượng yêu cầu; mỗi nguồn ghi `warmup_count` và `retained_count`.
- Header: `Accept: */*`, `User-Agent: backtest-hpg/0.1`. Mỗi nguồn chờ tối đa 60 giây; lỗi tải kết thúc yêu cầu.

**Kiểm tra dữ liệu**

- Giữ nến đã đóng với `time + 300 <= to`, gồm cả bản ghi ATC. Giữ độ phân giải và các khoảng thiếu của nguồn.
- Từ chối dữ liệu sai trạng thái, OHLCV, thứ tự, mốc 5 phút hoặc vượt khoảng yêu cầu.
- Kiểm tra thứ tự ngày của `report` trước khi gọi nguồn.
- Thiếu dữ liệu đầu/cuối kỳ: chạy trên nến thực có, giữ `report_range`; `available_range` ghi phạm vi thực có.
- Theo lịch phiên, nến thiếu được ghi trong `data_gaps`. Kỳ không có nến giao dịch trả `REPORT_DATA_MISSING`.
- Bỏ `report`: dùng ngày đầu/cuối của nến đã đóng.

Với `accounting.model: "contract"`:

- `AUTO_FETCH_POLICY_PATH` chọn bảng đáo hạn, mặc định `runtime-policy.json`; bảng kết thúc 17/12/2026. Vượt bảng trả `CONTRACT_MAP_COVERAGE_MISSING`.
- `INLINE_POLICY_PATH` chọn lịch phiên, mặc định `runtime-policy-v1.json`, bao phủ 01/03–31/12/2026 theo [lịch nghỉ HNX](https://www.gov.hnx.vn/vi-vn/chi-tiet-lich-nghi-gd-60021971.html?_page=1). Ngoài lịch trả `REPORT_OUTSIDE_STATIC_CALENDAR`.
- Lịch sử khởi tạo giới hạn bởi ngày đầu lịch phiên và đầu tháng đầu của bảng đáo hạn; mặc định 01/03/2026.
- `metadata.auto_fetch.history_start_limit` ghi giới hạn, `from` ghi mốc tải thực tế. Thiếu lịch sử trả `UNEVALUABLE`; kỳ và `warmup_bars` giữ nguyên.
- `hnx_sessions_v1` hỗ trợ tự lấy cho LO với trượt giá `0`.
- `trade_data.contract_dates` dùng giả định chuyển mã sau ngày đáo hạn, lưu cùng nguồn dữ liệu. Giả định này cần đối chiếu riêng với nhà cung cấp.
- ATO/ATC cần bản ghi nhãn 09:00/14:45; thiếu bản ghi làm lượt chạy lỗi. Xem [khớp theo phiên](hnx-session-matching.md).

Mô hình `normalized` tự lấy dữ liệu theo cách hiện có, giữ nguyên mô hình tiền.

- Lấy giữa phiên chỉ dùng nến đã đóng. Contract còn vị thế cuối dữ liệu có thể trả `END_OF_REPORT_POSITION_REQUIRES_EXIT`.
- Để chạy phiên hoàn tất, chọn `report.end_date` là ngày giao dịch đã kết thúc.
- `metadata.input_origin: "auto_fetch"` xác định nguồn tự lấy.
- `metadata.auto_fetch` ghi thời điểm, khoảng lấy, URL, mã băm phản hồi và số nến gốc/đã đóng/bị loại của từng nguồn.
- Kho lưu payload đã chuẩn bị và metadata; phản hồi HTTP gốc chỉ được lưu mã băm.
- `/validate` trả `payload` với `auto_fetch_data: false` và hai nguồn cụ thể. Gửi lại payload này để dùng đúng dữ liệu đã kiểm tra.
- Gửi lại `auto_fetch_data: true` sẽ lấy dữ liệu mới.

### 3.1. trade_data

Chuỗi OHLCV của mã giao dịch. Các trường cũng áp dụng cho market_data.

| Trường           | Kiểu       | Bắt buộc | Mặc định khi bỏ    | Ý nghĩa/ràng buộc                                                              |
| ------------------ | ----------- | ---------- | ---------------------- | ---------------------------------------------------------------------------------- |
| `bars`           | array       | Có        | —                     | Mảng nến không rỗng, tăng dần theo thời gian                                |
| `resolution`     | string      | Không     | `"5"`                | `"5"`: 5 phút; `"D"`: ngày                                                   |
| `symbol`         | string/null | Không     | null                   | Nhãn mã, không chọn quy tắc                                                   |
| `timestamp_unit` | string      | Không     | `"s"`                | `"s"`: giây; `"ms"`: mili giây                                               |
| `timezone`       | string      | Không     | `"Asia/Ho_Chi_Minh"` | Tên múi giờ IANA hợp lệ                                                       |
| `price_unit`     | string/null | Không     | null                   | Đơn vị tiền tệ                                                                |
| `contract_map`   | array       | Không     | `[]`                 | Bảng mã và ngày đáo hạn khi dữ liệu thuộc dạng chứng khoán phái sinh |

**Cấu trúc dữ liệu trong mỗi bar nến**

Kiểu 1: Mảng các JSON Object

| Trường                               | Kiểu                       | Bắt buộc            | Ý nghĩa/ràng buộc                                                            |
| -------------------------------------- | --------------------------- | --------------------- | -------------------------------------------------------------------------------- |
| `time`                               | số nguyên                 | Có                   | Unix tại lúc mở nến, theo timestamp_unit                                     |
| `open`, `high`, `low`, `close` | số/chuỗi thập phân      | Có                   | Mỗi giá hữu hạn, lớn hơn 0                                                 |
| `volume`                             | số/chuỗi thập phân/null | Khi được sử dụng | Không âm; bắt buộc cho MFI hoặc tham chiếu volume                          |
| `close_time`                         | integer/null                | Với nến ngày       | Thời điểm đóng                                                              |
| `available_at`                       | integer/null                | Với nến ngày       | Thời điểm khả dụng; tương đương giá trị close_time với nến 5 phút |

Kiểu 2: JSON Object chứa các mảng (cấu trúc dữ liệu gốc khi lấy từ API)

| Trường | Kiểu           | Bắt buộc | Ý nghĩa/ràng buộc                        |
| -------- | --------------- | ---------- | -------------------------------------------- |
| `t`    | số nguyên     | Có        | Unix tại lúc mở nến, theo timestamp_unit |
| `c`    | số thập phân | Có        | Close                                        |
| `o`    | số thập phân | Có        | Open                                         |
| `h`    | số thập phân | Có        | High                                         |
| `l`    | số thập phân | Có        | Low                                          |
| `v`    | số nguyên     | Có        | Volume                                       |
| `s`    | chuỗi          | Không     | Trạng thái dữ liệu                       |

Dữ liệu OHLC được xem là hợp lệ khi thỏa các điều kiện sau:

- `low <= min(open, close) <= max(open, close) <= high`.
- `time < close_time <= available_at`, không trùng, đảo thứ tự hoặc chồng lấn.
- Nến ngày phải có `close_time` và `available_at`; nến 5 phút dùng mặc định
  Close = Open + 300 giây và available_at = Close khi bỏ các trường này.
- Timestamp đúng format Unix.

**Mỗi phần tử contract_map:**

| Trường          | Kiểu        | Bắt buộc | Ý nghĩa                                                                                                                                                                    |
| ----------------- | ------------ | ---------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `contract_code` | string       | Có        | Mã xác định hợp đồng tương lai theo kỳ đáo hạn. Ví dụ`VN30F2603` là hợp đồng tương lai VN30 đáo hạn tháng 03/2026.                                |
| `expiry_date`   | string ngày | Có        | Ngày đáo hạn của hợp đồng, tức ngày giao dịch cuối cùng của hợp đồng đó. Định dạng`YYYY-MM-DD`.                                                      |
| `expiry_unix`   | integer      | Có        | Mốc thời gian Unix tính bằng giây biểu diễn ngày đáo hạn, giúp hệ thống đối chiếu với thời gian của các nến để xác định hợp đồng tương ứng. |

Khi có bảng, API đối chiếu lịch phiên máy chủ, nến thiếu lưu vào field `data_gaps`. Chi tiết theo hợp đồng dữ liệu v1.

Ví dụ **riêng nhóm dữ liệu**:

```json
{"trade_data":{"resolution":"5","t":[1773800100],"o":[1300],"h":[1302],"l":[1299],"c":[1301],"v":[1000]}}
```

### 3.2. market_data

- `market_data` là OHLCV thị trường tham chiếu, ví dụ VNINDEX.
- Khoảng thời gian và số nến có thể khác `trade_data`; cần đủ lịch sử cho chỉ báo.
- Tại quyết định `t`, chỉ đọc nến có `available_at <= t`.

### 3.3. strategy

| Trường                        | Kiểu                | Bắt buộc          | Khi bỏ                                       |
| ------------------------------- | -------------------- | ------------------- | --------------------------------------------- |
| `indicators`                  | object               | Khi dùng chỉ báo | `{}`                                        |
| `entry`, `exit`, `sizing` | object               | Có                 | —                                            |
| `daily_limits`                | object/null          | Không              | Không áp giới hạn ngày từ trường này |
| `warmup_bars`                 | integer dương/null | Không              | Không áp ngưỡng lịch sử bổ sung        |

Cấu trúc chi tiết ở mục 5.

### 3.4. execution

| Trường                      | Kiểu                  | Bắt buộc                          | Giá trị hỗ trợ                      | Ý nghĩa                                                                                                                                                                                     |
| ----------------------------- | ---------------------- | ----------------------------------- | --------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `entry_fill_policy`         | string/null            | Không                              | `"next_open"`, `"limit"`, `"ato"` | Trường tương thích cũ; cấu hình mới đặt loại lệnh trong `strategy.entry.order` hoặc `actions.<nhãn>.order`                                                                 |
| `slippage_rate`             | số/chuỗi thập phân | Có                                 | Từ 0 đến dưới 1                    | Tỷ lệ trượt giá mô phỏng mức bất lợi giữa giá tham chiếu và giá khớp. Với normalized, giá mua = giá mở cửa × (1 + tỷ lệ), giá bán = giá mở cửa × (1 − tỷ lệ) |
| `matching_model`            | string/null            | Không                              | `"next_open"`, `"hnx_sessions_v1"`  | Bỏ trống tương đương `next_open`; HNX chỉ dùng contract 5 phút, trượt giá 0                                                                                                    |
| `auction_match_quantity`    | integer/null           | Không                              | Số nguyên ≥ 0                        | Giới hạn cố định lượng khớp mỗi lệnh ATO/ATC; bỏ để giả định khớp đủ; đây không phải mô hình thanh khoản thật                                                      |
| `continuous_match_quantity` | integer/null           | Không; bắt buộc với MTL/MOK/MAK | Số nguyên ≥ 0, không nhận boolean  | Ngân sách đối ứng giả định dùng chung theo nến/mã hợp đồng, cả Open và Close; bỏ để giữ LO khớp đủ như trước                                                        |

Stop/target trong nến có quy tắc tại mục 5.3.

#### 3.4.1. Lệnh thuộc hành động của chiến lược

- `strategy.entry.order`: cấu hình chung cho lệnh mở.
- `entry.actions.<nhãn>`: `side` và `order` riêng từng nhánh; nhãn phải khớp `conditions`.
- `side`: `BUY` cho normalized, `LONG`/`SHORT` cho contract.
- `strategy.exit.bar_close` dùng `order` và `actions.<nhãn>.order` tương tự. Hướng đóng được suy từ mô hình tiền và vị thế.

| Trường trong `order`                                                     | Quy tắc                                                                                                |
| ---------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| `type`                                                                     | `SIMULATED`, `LO`, `ATO`, `ATC`, `MTL`, `MOK` hoặc `MAK`                                 |
| `limit_price`                                                              | Cây biểu thức số, bắt buộc riêng cho LO; chốt khi gửi, dương và đúng bước 0,1           |
| `pending.max_execution_bars`                                               | Số nguyên dương; ATO/ATC/MAK/MOK không nhận cấu hình chờ riêng này; MTL áp dụng cho LO dư |
| `pending.cross_lunch`, `pending.cross_cutoff`, `pending.cross_session` | Khi có pending phải khai báo cả ba là false; không cho lệnh vượt ranh giới này               |

`SIMULATED` yêu cầu khớp mô phỏng tại Open kế tiếp theo đường chạy cũ.

| Mô hình tiền / khớp                     | Mở                               | Đóng theo điều kiện          |
| ------------------------------------------- | --------------------------------- | --------------------------------- |
| normalized / next_open                      | SIMULATED                         | SIMULATED                         |
| contract / next_open                        | SIMULATED                         | SIMULATED                         |
| contract / hnx_sessions_v1                  | SIMULATED, LO, ATO, MTL, MOK, MAK | SIMULATED, LO, ATC, MTL, MOK, MAK |
| contract / hnx_sessions_v1, pyramiding=true | LO, ATO, MTL, MOK, MAK            | SIMULATED, LO, ATC, MTL, MOK, MAK |

- Ánh xạ cũ: `next_open → SIMULATED`, `limit → LO`, `ato → ATO`, `atc → ATC`.
- Cấu hình cũ: `entry_fill_policy` cho mở, `bar_close.fill_policy` cho đóng, `limit_price` theo nhóm; `entry.pending` dùng chung hai nhóm.
- Ưu tiên: `actions.<nhãn>.order` → `order` chung → cấu hình cũ.
- Cũ/mới mâu thuẫn về loại, giá hoặc thời hạn: từ chối.
- Chuyển `next_open` sang `SIMULATED` vẫn giữ `hnx_sessions_v1` nếu đang dùng model này.

#### 3.4.2. Nhiều nhánh và nhiều phần vị thế

- `strategy.sizing.pyramiding: true` dùng với contract/HNX và lệnh mở LO/ATO/MTL/MOK/MAK.
- `entry.priority` phải liệt kê đủ nhánh; bỏ `on_conflict` và các cờ `require_flat: true`, `require_no_pending: true`.
- Xử lý nhánh theo `priority`. Lượng đang giữ cộng mở đang chờ tối đa `max_contracts`; nhánh sau nhận phần hạn mức còn lại.
- Chỉ bổ sung cùng hướng với vị thế và lệnh đang chờ.
- Mỗi lần mở giữ `position_id`, giá vốn, phí mở còn lại, stop/TP và số nến giữ riêng.
- `position.*` thuộc phần đang xét; `account.*` và giới hạn ngày thuộc tài khoản chung.
- `quantity: "remaining"` đóng phần còn lại của chính phần vị thế đó.
- Mỗi phần có tối đa một lệnh đóng theo điều kiện đang chờ. Bảo vệ thay đổi lượng thì hủy lệnh đóng chờ với `POSITION_CHANGED`.

Với một vị thế, `on_conflict: "SIGNAL_CONFLICT"` giữ hành vi cũ: nhiều nhánh
đúng thì không mở. Nếu chỉ khai báo `priority`, chọn nhánh đúng đầu tiên.

#### 3.4.3. Cấu hình lưu và chạy lại

- `metadata.order_configuration` ghi model, cấu hình từng nhánh và `source` là đường dẫn trường được chọn.
- `pending_source` ghi `strategy.entry.pending` khi dùng cấu hình chờ cũ.
- Hash bao gồm payload, policy và metadata đã ghim. Metadata mới có thể làm hash khác dù giao dịch giống nhau.
- Lượt đã lưu giữ nguyên; chạy lại dùng payload và policy đã ghim.
- Nhiều phần vị thế: trả `open_positions`, đặt `open_position: null`.
- `evaluations.position_id` xác định phần đang xét đóng; xét mở trả null.
- `evaluation_status` đếm thời điểm phân biệt. Có ít nhất một lượt thiếu dữ liệu thì thời điểm được tính vào `unevaluable_bars`.
- Trạng thái chung: mọi lượt thiếu dữ liệu là `UNEVALUABLE`; còn lượt đánh giá được là `PARTIALLY_EVALUABLE`. Chi tiết giữ trong `evaluations`.

#### 3.4.4. Lệnh MTL/MOK/MAK

Đã triển khai và kiểm thử cơ chế với lượng giả định ngày 20/10/2026.
Quy tắc sàn, phạm vi hiệu lực, ví dụ 0/2/5 và thời điểm khớp thuộc
[mục 7 tài liệu phiên](hnx-session-matching.md#7-đặc-tả-mtlmokmak--a01).

| Cấu hình đích                           | Mở LONG/SHORT                             | Đóng LONG/SHORT theo điều kiện  |
| ------------------------------------------- | ------------------------------------------ | ------------------------------------ |
| contract / hnx_sessions_v1, một vị thế   | MTL, MOK, MAK                              | MTL, MOK, MAK                        |
| contract / hnx_sessions_v1, pyramiding=true | MTL, MOK, MAK theo priority, cùng hướng | MTL, MOK, MAK theo từng position_id |
| contract / next_open                        | Từ chối cả ba                           | Từ chối cả ba                     |
| normalized / mọi model                     | Từ chối cả ba                           | Từ chối cả ba                     |

- `strategy.entry.order`/`actions.<nhãn>.order` và `exit.bar_close` nhận thêm `MTL`, `MOK`, `MAK`.
- Ba loại chỉ dùng cấu hình lệnh mới; giá khớp và giá LO dư MTL do bộ khớp xác định.
- MTL nhận `order.pending` cho LO dư; mặc định một nến từ nến sau chuyển đổi, ba cờ vượt ranh giới là `false`.
- MAK/MOK từ chối `pending` riêng. Với `entry.pending` cũ, chỉ nhận mặc định `max_execution_bars=1` và ba cờ `false`.
- LO/ATO/ATC/SIMULATED giữ hợp đồng cấu hình hiện có.

Để kiểm tra giá khớp và chuyển MTL sát biên, chốt đầu vào mới
`trade_data.price_limits`: mảng một bản ghi cho mỗi cặp ngày/mã hợp đồng
trong kỳ thực thi khi dùng bất kỳ loại mới nào. Không bắt buộc với lượt cũ.

| Trường mỗi bản ghi             | Kiểu / ràng buộc đích                                                                       |
| ---------------------------------- | ------------------------------------------------------------------------------------------------ |
| `trading_date`                   | Ngày ISO `YYYY-MM-DD` theo múi giờ trade_data                                               |
| `contract_code`                  | Mã thực tế, khớp `contract_dates`; không dùng riêng bí danh VN30F1M                    |
| `floor_price`, `ceiling_price` | Số hoặc chuỗi thập phân, hữu hạn, dương, đúng bước 0,1; sàn không lớn hơn trần |
| `available_at`                   | Unix giây nguyên, không muộn hơn sự kiện sử dụng biên giá                             |
| `source`                         | Chuỗi không rỗng ghi nguồn công bố hoặc giả định kiểm thử                            |

- Bảng tăng theo ngày/mã, duy nhất và phủ các ngày/hợp đồng có thể thực thi. Lịch sử khởi tạo được miễn.
- Ghim bảng, nguồn và thời điểm khả dụng vào đầu vào để chạy lại.
- Biên giá phải do bên gọi cung cấp. Tự lấy thiếu bảng này thì báo lỗi.

Bảng dưới quy định phản hồi cho các loại mới. Giữ HTTP 422 và cách trả lỗi hiện có; kiểm tra được từ
payload ở `/validate`, kiểm tra giá/sự kiện khi
chạy ở POST tạo lượt. Không công bố lượt chạy một phần là thành công.

| Mã đích                                                                      | Điều kiện                                                                                           |
| ------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| `ORDER_UNSUPPORTED_BY_MATCHING_MODEL`                                         | Loại mới dùng với next_open; normalized vẫn bị từ chối tại kiểm tra tổ hợp mô hình tiền |
| `MARKET_ORDER_PENDING_NOT_APPLICABLE`                                         | MAK/MOK khai báo pending riêng hoặc cấu hình chờ cũ không mặc định                          |
| `MISSING_PRICE_LIMITS`, `INVALID_PRICE_LIMITS`                              | Thiếu biên; sai kiểu, ngày/mã, độ phủ, thứ tự, giá, nguồn hoặc thời điểm khả dụng    |
| `INVALID_MARKET_MATCH_PRICE`                                                  | Open thiếu, sai bước giá hoặc ngoài biên; xử lý như lỗi giá                                |
| `MATCH_RESPONSE_OUT_OF_RANGE`                                                 | Bộ khớp trả giá/lượng/chiều/mã/thời điểm ngoài hợp đồng; dừng trước hạch toán      |
| `MARKET_ORDER_REQUIRES_MATCH_QUANTITY`, `INVALID_CONTINUOUS_MATCH_QUANTITY` | Thiếu ngân sách cố định cho loại mới hoặc lượng âm/phân số/boolean                       |
| `MARKET_RULES_OUTSIDE_VERIFIED_RANGE`                                         | Kỳ dùng loại mới nằm ngoài 05/05/2025–20/10/2026 đã đối chiếu                              |

- Lượng đặt phải dương; lượng đối ứng có thể bằng 0.
- Chỉ trừ ngân sách khi tài khoản nhận fill. MOK thiếu lượng/tiền giữ ngân sách cho lệnh sau.
- Lệnh cùng thời điểm theo thứ tự gửi, Open trước Close.
- SIMULATED và bảo vệ dùng quy tắc riêng; ATO/ATC giữ giới hạn mỗi lệnh.
- Có `continuous_match_quantity`: order thêm `requested_quantity`, `reference_price`, `effective_order_type`, `converted_limit_price`, `fill_indices`, `fill_ids`, `canceled_quantity`, `rejected_quantity`.
- `requested_quantity` là lượng trước hạn mức; `quantity` là lượng nhận đặt.
- Bảo toàn `quantity = filled_quantity + expired_quantity + canceled_quantity + rejected_quantity + remaining_quantity`.
- `entry_fill_id` giữ fill đầu; `entry_fill_ids` liệt kê các fill mở cùng lệnh.
- Fill LO dư có `order_type: "LO"`; order gốc giữ MTL. Dữ liệu lịch sử và nghĩa `expired_quantity` giữ nguyên.
- Ví dụ: [market-fixed.json](../examples/orders/market-fixed.json).

### 3.5. accounting

| Trường normalized | Kiểu                  | Bắt buộc | Ý nghĩa                                                                                                                                                                                                                         |
| ------------------- | ---------------------- | ---------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `model`           | string                 | Có        | `"normalized"`: chọn mô hình mua/bán theo đơn vị giá mô phỏng. Hiện hỗ trợ `"normalized"` (Mô phỏng mua/bán theo đơn vị giá đầu vào) và `"contract"` (Mô phỏng giao dịch hợp đồng phái sinh) |
| `fee_rate`        | số/chuỗi thập phân | Có        | Không âm, phí trên giá trị mỗi lượt khớp                                                                                                                                                                                |

Normalized dùng BUY, sizing fixed_fractional và thoát toàn bộ bằng SELL tại
Open sau điều kiện Close. Không hỗ trợ intrabar. Tiền theo đơn vị giá mô phỏng.

| Trường contract             | Kiểu                  | Bắt buộc | Mặc định  | Ý nghĩa/ràng buộc                                              |
| ----------------------------- | ---------------------- | ---------- | ------------ | ------------------------------------------------------------------ |
| `model`                     | string                 | Có        | —           | `"contract"`: chọn mô hình tính tiền hợp đồng phái sinh |
| `contract_multiplier`       | số/chuỗi thập phân | Không     | `"100000"` | Hệ số điểm sang tiền, > 0                                     |
| `margin_rate`               | số/chuỗi thập phân | Có        | —           | Tỷ lệ ký quỹ, > 0 và <= 1                                     |
| `pit_rate`                  | số/chuỗi thập phân | Có        | —           | Thuế suất từ 0 đến 1                                          |
| `exchange_fee_per_contract` | số/chuỗi thập phân | Có        | —           | Phí sàn mỗi hợp đồng/lượt, >= 0                            |
| `clearing_fee_per_contract` | số/chuỗi thập phân | Có        | —           | Phí bù trừ mỗi hợp đồng/lượt, >= 0                        |
| `broker_fee_per_contract`   | số/chuỗi thập phân | Có        | —           | Phí môi giới mỗi hợp đồng/lượt, >= 0                      |

- Contract mở LONG/SHORT, đóng CLOSE, dùng risk_and_margin.
- Hệ số dùng tính tiền/rủi ro/ký quỹ.
- Cơ sở thuế mỗi lượt = giá khớp × hệ số × số hợp đồng × margin_rate / 2; thuế bằng cơ sở nhân pit_rate.
- Phí mỗi hợp đồng nhân số lượng khớp của lượt.
- Chi tiết làm tròn/phân bổ ở [đặc tả tính tiền](canslim-v1-execution-accounting.md).

### 3.6. initial_cash

Vốn hữu hạn lớn hơn 0, nằm ngoài accounting. Ví dụ `"100000000"`.
Contract dùng VND; normalized dùng đơn vị giá mô phỏng.

### 3.7. report

| Trường       | Kiểu        | Bắt buộc khi có report | Ý nghĩa             |
| -------------- | ------------ | ------------------------- | --------------------- |
| `start_date` | string ngày | Có                       | YYYY-MM-DD bắt đầu |
| `end_date`   | string ngày | Có                       | YYYY-MM-DD kết thúc |

Khoảng gồm hai đầu theo ngày địa phương trade_data. `start_date > end_date`
trả `INVALID_REPORT_RANGE` cho cả dữ liệu nhập tay và tự lấy, trước khi gọi nguồn.
Chỉ khi không có nến giao dịch nào trong kỳ mới trả HTTP 422:

```json
{"detail":"REPORT_DATA_MISSING:requested=2026-10-08..2026-10-08;available=2026-10-09..2026-10-09"}
```

- Nguồn bắt đầu muộn hoặc kết thúc sớm vẫn được sử dụng, không tự rút ngắn kỳ báo cáo và không tạo nến bù.
- `metadata.report_range` giữ kỳ yêu cầu; `metadata.available_range` ghi ngày đầu/cuối của nến giao dịch thực có trong kỳ.
- Ví dụ yêu cầu 10/04–14/10/2026 nhưng nguồn có từ 15/04 thì hai phạm vi được ghi riêng như vậy.
- Khi áp dụng lịch phiên, `data_gaps` vẫn ghi các nến thiếu đầu/cuối.
- Thiếu lịch sử chỉ báo tại nến trong kỳ vẫn ghi `UNEVALUABLE` khi chạy; đó không phải lỗi thứ tự ngày hoặc lỗi bao phủ kỳ báo cáo.

## 4. Payload minh họa

Ví dụ giữ cấu hình CANSLIM v1: chỉ báo/điều kiện thị trường dùng VNINDEX,
giá thực thi dùng VN30F1M, tiền theo hợp đồng. Giá nến minh họa không phải
bộ dữ liệu nghiệm thu hoặc kết quả đầu tư.

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
        "signal_period": 9
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
      "risk_fraction": 0.02,
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

- Mỗi khóa khai báo một chỉ báo.
- Tên bắt đầu bằng chữ cái, sau đó chỉ có chữ cái, số hoặc `_`; không dùng trade_data, market_data, position, account, day, clock.
- Mỗi chỉ báo phải có type, source và đúng bộ tham số; không truyền thêm tham số của loại khác hoặc null cho tham số bắt buộc.

| type                    | source hợp lệ                   | Tham số bổ sung bắt buộc                                                            | Đầu ra ref                           |
| ----------------------- | --------------------------------- | --------------------------------------------------------------------------------------- | -------------------------------------- |
| `SMA`                 | Cột OHLCV trade_data/market_data | period nguyên dương                                                                  | Tên chỉ báo                         |
| `HIGHEST`, `LOWEST` | Cột OHLCV trade_data/market_data | period nguyên dương                                                                  | Tên chỉ báo                         |
| `EMA`                 | Cột OHLC trade_data/market_data  | period nguyên dương                                                                  | Tên chỉ báo                         |
| `BB`                  | Cột OHLC trade_data/market_data  | period nguyên dương, stddev_multiplier > 0                                           | tên.middle, tên.upper, tên.lower    |
| `MACD`                | Cột OHLC trade_data/market_data  | fast_period, slow_period, signal_period nguyên dương; fast < slow | tên.line, tên.signal, tên.histogram |
| `MFI`                 | "trade_data" hoặc "market_data"  | period nguyên dương; đủ HLCV                                                       | Tên chỉ báo                         |

MACD Histogram = MACD Line − Signal; chưa có giá trị trước khi Signal đủ mẫu.
Trường cũ `histogram: "line"` vẫn được nhận nhưng không chọn công thức hoặc
cách vẽ. JSON mới bỏ trường này. Chạy lại chiến lược dùng `macd.histogram`
có thể đổi kết quả; xem [ghi chú tương thích](strategy-payload-guide.md).

Ví dụ một khai báo trong indicators:

```json
{"sma20":{"type":"SMA","source":"market_data.close","period":20}}
```

### 5.2. entry

Điều kiện mở được xét sau Close khi không giữ vị thế và không có lệnh chờ
đang xử lý. Không gửi số lượng trong entry. SIMULATED tính lượng lúc khớp;
LO/ATO/MTL/MOK/MAK chốt lượng trước theo quy tắc giá dự kiến tương ứng.

| Trường               | Kiểu             | Bắt buộc                               | Ý nghĩa/giá trị hợp lệ                                                                                        |
| ---------------------- | ----------------- | ---------------------------------------- | ------------------------------------------------------------------------------------------------------------------- |
| `conditions`         | object            | Có                                      | Nhãn → expression boolean; mặc định nhãn BUY/LONG/SHORT là hướng, hoặc khai báo `actions.<nhãn>.side` |
| `any`                | array string      | Có                                      | Đúng các nhánh conditions, không rỗng/trùng                                                                  |
| `details`            | object            | Không; mặc định {}                   | Tên → expression số, lưu giá trị lúc tín hiệu mở                                                          |
| `require_flat`       | boolean/null      | Không                                   | Chỉ xét mở lệnh khi không giữ vị thế (flat)                                                                 |
| `require_no_pending` | boolean/null      | Không                                   | Chỉ xét mở lệnh khi không có lệnh chờ khớp (pending)                                                       |
| `signal_windows`     | array cặp string | Không                                   | Khoảng HH:MM gồm hai đầu, tăng dần, không chồng nhau                                                        |
| `on_conflict`        | string/null       | Một vị thế, khi không dùng priority | Chỉ SIGNAL_CONFLICT; nhiều nhánh cùng đạt thì không mở                                                     |
| `priority`           | array string/null | Bắt buộc khi pyramiding=true           | Đủ nhãn trong any, không trùng; duyệt theo thứ tự                                                           |
| `order`, `actions` | object            | Khi không có cấu hình lệnh cũ      | Loại lệnh dùng chung hoặc riêng theo mục 3.4.1                                                                |
| `reentry`            | string/null       | Không                                   | Chỉ next_bar_close_after_exit; ngăn vào lại tại Close nến vừa thoát                                         |
| `pending`            | object/null       | Không                                   | Quy tắc lệnh mở chờ                                                                                             |

Khi có pending, cần đủ bốn trường:

| Trường               | Giá trị hỗ trợ                                   |
| ---------------------- | ---------------------------------------------------- |
| `max_execution_bars` | Số nguyên dương với HNX; next_open chỉ nhận 1 |
| `cross_lunch`        | false                                                |
| `cross_cutoff`       | false                                                |
| `cross_session`      | false                                                |

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

- Stop/target có hiệu lực sau khớp mở.
- Gap qua stop khớp Open; chạm stop trong nến khớp mức stop.
- Gap qua target vẫn khớp target.
- TP1 đóng một phần thì cập nhật số lượng trước TP2.
- Trailing không dùng cực trị nến khớp TP1; từ nến sau cập nhật tại Close, áp dụng nến kế tiếp, không nới stop.
- Bước giá/làm tròn thuộc [đặc tả thực thi](canslim-v1-execution-accounting.md).

#### 5.3.2. Thoát theo Close — bar_close

| Trường        | Kiểu        | Bắt buộc | Ý nghĩa                                                                                                  |
| --------------- | ------------ | ---------- | ---------------------------------------------------------------------------------------------------------- |
| `conditions`  | object       | Có        | Nhãn → expression boolean                                                                                |
| `any`         | array string | Có        | Đúng các nhãn conditions, không trùng                                                                |
| `priority`    | array string | Có        | Đúng các nhãn any theo thứ tự ưu tiên                                                              |
| `quantity`    | string       | Có        | Chỉ "remaining"                                                                                           |
| `fill_policy` | string/null  | Không     | Tương thích cũ: next_open/limit/atc; cấu hình mới dùng `order` hoặc `actions` theo mục 3.4.1 |

Chọn điều kiện đầu tiên đạt theo priority, tạo một lệnh đóng phần còn lại ở
theo cấu hình lệnh đã chọn (SIMULATED dùng Open kế tiếp): contract dùng CLOSE, normalized dùng SELL. Xét sau thoát trong
nến nếu còn vị thế. Nến mở là nến giữ thứ nhất; nghỉ trưa không tính thành nến.

flat_by là hạn thực thi, không tự tạo tín hiệu đóng. Cần điều kiện thoát đủ
sớm và có nến khớp. Thiếu nến thoát bắt buộc, lỡ hạn hoặc còn vị thế cuối kỳ
khi cấm qua đêm làm lần chạy lỗi.

### 5.4. sizing

Không mặc định mở một hợp đồng. Type chọn bộ trường bắt buộc:

| type                 | Trường bắt buộc                                                  | Ràng buộc                                                                                                                 |
| -------------------- | -------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| `fixed_fractional` | risk_fraction, stop_loss_fraction                                    | 0 < risk_fraction <= 1; 0 < stop_loss_fraction < 1                                                                          |
| `risk_and_margin`  | risk_fraction, stop_points, margin_buffer, max_contracts, pyramiding | 0 < risk_fraction <= 1; stop_points > 0; margin_buffer >= 1; max_contracts nguyên dương; pyramiding=true theo mục 3.4.2 |

Normalized chọn số lượng nguyên theo ngân sách rủi ro và tiền đủ mua sau phí.
Stop_loss_fraction dùng tính lượng mua, **không tự tạo điều kiện stop**;
điều kiện thoát vẫn phải khai báo trong exit.

- Contract chọn số hợp đồng nguyên theo ngân sách rủi ro, chi phí ước tính hai lượt, ký quỹ có dự phòng và trần max_contracts.
- Không đủ một hợp đồng hoặc không đủ ký quỹ sau phí mở thì từ chối lệnh.
- Số lượng dựa trên tài khoản và giá tại lúc khớp.
- Công thức thuộc [đặc tả tính tiền](canslim-v1-execution-accounting.md).

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

Giờ dùng chuỗi HH:MM, ví dụ `{"gte":[{"ref":"clock.local_time"},"14:20"]}`.

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

- `all`: Tương đương với cú pháp **AND**.
- `any`: Tương đương với cú pháp **OR**.

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
Một số mã sẽ có thêm thông tin sau dấu `:`.

| Mã/loại lỗi                                                                                     | Điều kiện                                                                                        |
| -------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| `json_invalid`, `missing`, `extra_forbidden`                                                 | Sai JSON, thiếu trường hoặc có trường thừa                                                  |
| `INVALID_OHLC`                                                                                   | Quan hệ giá không hợp lệ                                                                       |
| `INVALID_BAR_TIMES`                                                                              | Không thỏa time < close_time <= available_at                                                      |
| `UNORDERED_OR_OVERLAPPING_BARS`                                                                  | Nến trùng, đảo thứ tự, chồng lấn                                                            |
| `DAILY_EXPLICIT_TIMES_REQUIRED`                                                                  | Nến ngày thiếu thời điểm đóng/khả dụng                                                    |
| `MISSING_REQUIRED_DATA`, `MISSING_REQUIRED_VOLUME`                                             | Thiếu chuỗi/volume được sử dụng                                                              |
| `INVALID_REPORT_RANGE`                                                                           | Ngày bắt đầu lớn hơn ngày kết thúc; kiểm tra trước khi gọi nguồn                      |
| `REPORT_DATA_MISSING`                                                                            | Không có nến giao dịch nào trong kỳ; kèm kỳ yêu cầu và phạm vi dữ liệu nguồn         |
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
| `MISSING_ATO_MATCH_BAR`, `MISSING_ATC_MATCH_BAR`, `ATC_CONTRACT_MISMATCH`                    | Thiếu bản ghi giá đấu giá hoặc sai mã hợp đồng                                           |
| `INVALID_AUCTION_MATCH_QUANTITY`, `AUCTION_MATCH_QUANTITY_REQUIRES_AUCTION_ORDER`              | Giới hạn lượng khớp đấu giá sai hoặc không có lệnh ATO/ATC                              |
| `PRIMARY_AVAILABILITY_DELAY_UNSUPPORTED`                                                         | Chuỗi giao dịch có thời điểm khả dụng khác Close                                           |
| `MISSING_REQUIRED_EXIT_BAR`, `MISSING_POSITION_EXECUTION_BAR`                                  | Thiếu nến cần khớp/quản trị vị thế                                                          |
| `FLAT_DEADLINE_MISSED`, `OVERNIGHT_POSITION_INVALID`, `END_OF_REPORT_POSITION_REQUIRES_EXIT` | Vi phạm hạn hoặc yêu cầu không qua đêm                                                      |
| `INLINE_STRATEGY_RUNTIME_NOT_IMPLEMENTED`                                                        | Máy chủ chưa nối bộ chạy chiến lược                                                        |

### 7.3. Status code của hai endpoint POST

| Endpoint                    | HTTP status              | Mã/trạng thái                                                        | Điều kiện và response                                                                                           |
| --------------------------- | ------------------------ | ----------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------- |
| `/api/backtests/validate` | 200 OK                   | STRUCTURE_VALID                                                         | Qua kiểm tra, trả body mục 8.1                                                                                   |
| `/api/backtests/validate` | 422 Unprocessable Entity | Lỗi cấu trúc/nội dung                                               | Không chạy/lưu; trả detail lỗi                                                                                 |
| `/api/backtests/validate` | 503 Service Unavailable  | INLINE_POLICY_UNAVAILABLE                                               | Không đọc được chính sách phiên cần dùng; detail là chuỗi                                              |
| `/api/backtests`          | 201 Created              | —                                                                      | Chạy và lưu xong; trả kết quả mục 8.2                                                                        |
| `/api/backtests`          | 422 Unprocessable Entity | Lỗi cấu trúc/nội dung/thực thi                                     | Không công bố kết quả một phần là thành công                                                              |
| `/api/backtests`          | 503 Service Unavailable  | BACKTEST_STORAGE_UNAVAILABLE                                            | Lỗi lưu trữ/ghi thuộc nhóm được xử lý; detail là object có code                                         |
| Cả hai POST                | 422 Unprocessable Entity | AUTO_FETCH_INVALID_SOURCE, AUTO_FETCH_NO_CLOSED_BARS                    | Nguồn trả dữ liệu sai hoặc không có nến đã đóng; detail là chuỗi kèm tên nguồn                     |
| Cả hai POST                | 503 Service Unavailable  | AUTO_FETCH_HTTP_ERROR, AUTO_FETCH_NETWORK_ERROR, AUTO_FETCH_UNAVAILABLE | VNDIRECT lỗi HTTP/mạng hoặc máy chủ chưa nối bộ tải; detail là chuỗi, lỗi HTTP kèm mã nguồn trả về |

Ví dụ lỗi cấu trúc do trường thừa:

```json
{"detail":[{"type":"extra_forbidden","loc":["body","unknown_field"],"msg":"Extra inputs are not permitted","input":true}]}
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
| Lịch sử có bộ lọc     | 422         | detail lỗi                          | Query không hợp lệ hoặc khoảng từ lớn hơn đến                     |

## 8. Response

Số thập phân trong kết quả chạy trả bằng **chuỗi**; số lượng/số đếm là số
nguyên. UUID là chuỗi; ngày dùng ISO YYYY-MM-DD, thời điểm dùng ISO 8601 có
múi giờ. Mảng không có sự kiện trả []; không tạo fill cho lệnh chưa khớp.

### 8.1. Kết quả POST /api/backtests/validate

| Trường        | Kiểu        | Ý nghĩa                                                                                                         |
| --------------- | ------------ | ----------------------------------------------------------------------------------------------------------------- |
| `status`      | string       | STRUCTURE_VALID khi qua kiểm tra                                                                                 |
| `runnable`    | boolean      | Máy chủ có bộ chạy chiến lược                                                                             |
| `data_status` | string       | RESOLVED khi đã ánh xạ dữ liệu                                                                              |
| `data`        | object       | Kỳ báo cáo, số nến khởi tạo, chỉ báo, map, khoảng thiếu và giả định dữ liệu                      |
| `pending`     | array string | [] trong ứng dụng chính đã nối bộ chạy; service tùy biến chưa nối bộ chạy trả U08_STRATEGY_RUNTIME |
| `payload`     | object       | Request đã chuẩn hóa, kèm mặc định schema, loại trường null                                            |

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

| Trường                          | Kiểu                         | Ý nghĩa                                                                                         |
| --------------------------------- | ----------------------------- | ------------------------------------------------------------------------------------------------- |
| `run_id`                        | string UUID                   | Định danh để đọc lại                                                                       |
| `run_at`                        | string ISO 8601 có múi giờ | Thời điểm bắt đầu thực thi sau khi chuẩn bị dữ liệu; kết quả mới ghi thời gian UTC |
| `engine_version`                | string                        | Phiên bản bộ thực thi                                                                         |
| `accounting_profile`            | string                        | normalized_v0 hoặc contract_v1                                                                   |
| `input_hash`, `policy_hash`   | string/null theo trường     | Dấu kiểm tra đầu vào/chính sách                                                            |
| `accounting`                    | object                        | Thông số đã áp dụng                                                                         |
| `initial_cash`                  | chuỗi thập phân            | Vốn ban đầu                                                                                    |
| `money_unit`, `quantity_unit` | string                        | Contract: VND/contracts; normalized: price_unit/normalized_units                                  |
| `fill_time_convention`          | string                        | Quy ước thời điểm khớp                                                                      |

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

| Trường               | Kiểu                           | Ý nghĩa                                                                                                                  |
| ---------------------- | ------------------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| `order_id`           | string UUID                     | Định danh lệnh                                                                                                          |
| `signal_id`          | string UUID                     | Tín hiệu tạo lệnh                                                                                                      |
| `created_time`       | thời điểm ISO                | Thời điểm tạo                                                                                                          |
| `side`               | string                          | Hành động                                                                                                               |
| `status`             | string                          | `filled`, `rejected`, `pending`, `canceled`, `expired`; lệnh đấu giá khớp một phần kết thúc `expired` |
| `reason`             | string/null, contract           | Lý do trạng thái                                                                                                        |
| `rejection_reason`   | string/null, normalized         | Lý do từ chối/chưa khớp                                                                                               |
| `position_id`        | string UUID, khi có            | Vị thế liên quan; không có ở mọi lệnh bị từ chối                                                                |
| `order_type`         | string, khớp theo phiên       | `NEXT_OPEN`, `LO`, `ATO`, `ATC`, `MTL`, `MOK`, `MAK` hoặc `PROTECTIVE`                                    |
| `quantity`           | integer/null, khớp theo phiên | Lượng đặt ban đầu; không bị thay bằng lượng khớp                                                               |
| `filled_quantity`    | integer, khớp theo phiên      | Tổng lượng đã khớp                                                                                                   |
| `expired_quantity`   | integer, khớp theo phiên      | Lượng đã hết hiệu lực mà không khớp                                                                              |
| `remaining_quantity` | integer/null, khớp theo phiên | Lượng còn chờ; bằng 0 khi lệnh kết thúc                                                                            |

Lệnh bị từ chối không có fill. Lệnh mở còn chờ cuối báo cáo được chuyển
rejected với lý do END_OF_REPORT. Lệnh ATO/ATC khớp một phần có fill dù trạng
thái cuối là `expired`; `filled_quantity + expired_quantity + remaining_quantity`
bằng `quantity`.

### 8.5. fills

| Trường                                                    | Kiểu                            | Ý nghĩa                                                                      |
| ----------------------------------------------------------- | -------------------------------- | ------------------------------------------------------------------------------ |
| `fill_id`, `order_id`, `position_id`                  | string UUID                      | Định danh khớp/lệnh/vị thế                                               |
| `side`                                                    | string                           | Hành động khớp                                                             |
| `signal_time`                                             | thời điểm ISO                 | Thời điểm tín hiệu gốc                                                   |
| `fill_time`                                               | thời điểm ISO                 | Open cho thị trường/gap; contract ghi chạm stop/target trong nến ở Close |
| `bar_time`                                                | thời điểm ISO                 | Open nến chứa khớp, dùng vị trí biểu đồ                               |
| `fill_price`                                              | chuỗi thập phân               | Giá khớp                                                                     |
| `quantity`                                                | integer                          | Số lượng khớp > 0                                                          |
| `fee`                                                     | chuỗi thập phân               | Tổng phí/thuế lượt khớp                                                  |
| `direction`                                               | string, contract                 | LONG/SHORT của vị thế                                                       |
| `contract_code`                                           | string/null, contract            | Mã từ map                                                                    |
| `exchange_fee`, `clearing_fee`, `broker_fee`, `pit` | chuỗi thập phân, contract     | Từng khoản chi phí                                                          |
| `order_type`, `phase`, `time_precision`               | string, khớp theo phiên        | Loại lệnh, phiên và độ chính xác thời điểm                          |
| `available_at`, `source`                                | thời điểm ISO/string, ATO/ATC | Thời điểm giá đấu giá khả dụng và nguồn OHLCV                       |

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
Normalized thêm market_value, entry_pivot.

### 8.8. summary

| Trường           | Kiểu              | Ý nghĩa                                    |
| ------------------ | ------------------ | -------------------------------------------- |
| `initial_cash`   | chuỗi thập phân | Vốn ban đầu                               |
| `final_equity`   | chuỗi thập phân | Giá trị cuối kỳ                          |
| `realized_pnl`   | chuỗi thập phân | Lãi/lỗ đã thực hiện                    |
| `unrealized_pnl` | chuỗi thập phân | Lãi/lỗ vị thế còn mở                   |
| `total_return`   | chuỗi thập phân | (final_equity - initial_cash) / initial_cash |
| `total_fees`     | chuỗi thập phân | Tổng chi phí đã ghi nhận                |

### 8.9. Trạng thái đánh giá

Mỗi evaluation có time, status, reason, market_sample_count,
market_available_at, indicator_times, indicators. Chỉ báo chưa có giá trị
có thể là null; dữ liệu được ghi theo thời điểm khả dụng.

| evaluation_status.status | Ý nghĩa                                                                                                                                                                                 |
| ------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| EVALUABLE                | Dữ liệu đủ để chạy backtest                                                                                                                                                        |
| PARTIALLY_EVALUABLE      | Các nhóm dữ liệu đủ để chạy backtest duy chỉ có dữ liệu nến chưa đủ để làm warm-up, hoặc thiếu ở vài khoảng không ảnh hưởng đến quá trình chạy backtest |
| UNEVALUABLE              | Thiếu dữ liệu để chạy backtest                                                                                                                                                      |

Unevaluable_bars/evaluated_bars đếm theo trạng thái. EVALUABLE không khẳng
định có giao dịch/lợi nhuận hoặc mọi nến được xét mở: reason còn có thể là
OUTSIDE_ENTRY_WINDOW hoặc DAILY_ENTRY_LIMIT.
