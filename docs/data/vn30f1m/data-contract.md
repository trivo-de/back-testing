# Hợp đồng dữ liệu JSON — VN30F1M

API hiện tại theo [hợp đồng khớp ngay hoặc LO](../../design/price-only-contract.md),
đã triển khai B–D: máy chủ luôn lấy dữ liệu 5 phút; POST không nhận nến/file hoặc cờ tự lấy.
Bỏ cả hai ngày dùng sáu tháng gần nhất; có đủ cặp ngày dùng kỳ báo cáo và lịch sử cần thiết.
Chỉ dùng nến đã khả dụng, giữ khoảng thiếu, nguồn và bản ghim để kiểm chứng.
Chính sách không giữ qua ngày yêu cầu lịch phiên nội bộ có độ phủ.
[Kiểm chứng C–D](../../testing/price-only-cd.md) dùng nguồn kiểm thử cố định, chưa nghiệm thu nguồn thật.

**Các mục bên dưới mô tả cấu trúc dữ liệu nội bộ và đầu vào cũ để đối chiếu lịch sử.**
Các ví dụ gửi trực tiếp `trade_data`/`market_data` không còn là request công khai hợp lệ.

API nhận `trade_data`, `market_data` trực tiếp hoặc tự lấy khi `auto_fetch_data=true`. Các trường chi tiết tại [đặc tả API](../../design/backtest-api-specification.md).

## 1. Nến, thời gian và khả dụng

- `trade_data` dùng để khớp/mark; `market_data` là chuỗi tham chiếu độc lập.
- Nhận mảng `bars` hoặc các mảng nguồn `t/o/h/l/c/v`; chuẩn hóa về nến.
- Giá hữu hạn, > 0; `low <= min(open, close) <= max(open, close) <= high`.
  Volume không âm và bắt buộc khi chỉ báo/biểu thức dùng volume.
- Timestamp Unix nguyên, đơn vị giây hoặc mili giây; múi giờ IANA rõ ràng.
  Không nhận nến trùng, đảo thứ tự, chồng lấn hoặc thời điểm khả dụng giảm.
- Với `resolution="5"`, bỏ `close_time` thì Close = Open + 300 giây;
  bỏ `available_at` thì bằng Close. Đây là quy ước mô phỏng.
- Với `resolution="D"`, phải truyền cả Close và available_at; không tự gộp
  dữ liệu trong ngày. Mô hình hợp đồng chỉ nhận chuỗi giao dịch 5 phút.
- `Open < Close <= available_at`; chuỗi giao dịch hiện yêu cầu
  `available_at == Close`. Chuỗi tham chiếu được phép khả dụng trễ.

- Tại quyết định `t`, chỉ đọc nến tham chiếu có `available_at <= t`.
- Mỗi nến tham chiếu chỉ tính một mẫu chỉ báo, kể cả khi được dùng ở nhiều quyết định.
- Chuỗi giữ nguyên các khoảng thiếu của nguồn.

## 2. Kỳ báo cáo và khởi tạo chỉ báo

- `report` gồm hai đầu theo múi giờ `trade_data`; bỏ trường thì dùng ngày đầu/cuối chuỗi giao dịch.
- Ngày bắt đầu lớn hơn kết thúc: `INVALID_REPORT_RANGE`.
- Nguồn thiếu đầu/cuối kỳ: chạy trên nến thực có, giữ `report_range`; `metadata.available_range` ghi phạm vi thực có trong kỳ.
- Theo lịch phiên, nến thiếu được ghi `data_gaps`.
- Kỳ trống nến giao dịch: `REPORT_DATA_MISSING`, kèm kỳ yêu cầu và phạm vi nguồn.
- Nến trước kỳ chỉ khởi tạo chỉ báo; nến sau kỳ được loại khỏi bộ chạy.

- `strategy.warmup_bars` bổ sung ngưỡng lịch sử. CANSLIM v1 dùng 150 nến VNINDEX, gồm nến hiện tại đã khả dụng.
- Thiếu lịch sử hoặc giá trị cần cho entry: `UNEVALUABLE`, bỏ mở lệnh và giữ kỳ báo cáo.

## 3. Lịch phiên và bảng hợp đồng

- Khi có `trade_data.contract_map`, service đọc `INLINE_POLICY_PATH`, mặc định [runtime-policy-v1.json](runtime-policy-v1.json).
- Bảng hợp đồng được kiểm tra ngày đáo hạn, Unix, mã không trùng, thứ tự, tháng liên tiếp và độ phủ cả lịch sử trước kỳ.
- Dòng đầu phủ từ đầu tháng đáo hạn; dòng sau phủ sau ngày đáo hạn trước tới hết ngày đáo hạn hiện tại.
- Muốn lấy lịch sử sớm hơn phải thêm dòng.

- Nguồn giao dịch có bảng hợp đồng phải dùng `Asia/Ho_Chi_Minh`.
- Với mỗi nguồn 5 phút được gửi, `_session_gaps()` kiểm tra cả trade_data và market_data theo lịch/nhãn giờ trong chính sách.
- Lịch mặc định bao phủ 01/03–31/12/2026, có 213 ngày giao dịch.
- Nhãn bắt buộc và tùy chọn của hai nguồn khác nhau; không lấy ngày có dữ liệu làm lịch giao dịch.

- Nến ngoài ngày/giờ hợp lệ hoặc dài khác 5 phút: từ chối `UNEXPECTED_BAR`.
- Kỳ ngoài lịch: `REPORT_OUTSIDE_STATIC_CALENDAR`.
- Nến bắt buộc bị thiếu: ghi `data_gaps` và `data_gap_before`, không tự điền.
  Chuỗi chỉ báo bị ngắt và phải đủ lại lịch sử trước khi đánh giá entry.
- Khi giữ vị thế hợp đồng, thiếu nến cần quản trị/thoát làm lượt chạy lỗi.
- Không có contract_map thì không chạy kiểm tra lịch phiên này.
  Nguồn ngày không được kiểm tra bằng lưới phiên 5 phút.

Chuyển mã hợp đồng ngắt chuỗi giá/chỉ báo trade_data; chuỗi VNINDEX vẫn giữ
lịch sử nếu không có khoảng thiếu. Luồng JSON không đọc
`rollover_action` để tự đóng ở Open ngày đáo hạn. Quy tắc thoát thuộc JSON.

## 4. Tự lấy dữ liệu

MTL/MOK/MAK cần `trade_data.price_limits` theo [API mục 3.4.4](../../design/backtest-api-specification.md#344-lệnh-mtlmokmak):

- Trần/sàn từng ngày và mã hợp đồng, đúng bước giá và có nguồn.
- `available_at`: Unix giây trong ngày, từ trước hoặc đúng sự kiện sử dụng.
- Sai mã, trùng/đảo thứ tự, biên chưa khả dụng hoặc thiếu ngày thực thi: báo lỗi.
- Lịch sử chỉ khởi tạo chỉ báo được miễn bảng biên giá.
- Quy chế đã đối chiếu 05/05/2025–20/10/2026; kỳ ngoài phạm vi cần đối chiếu lại.

Nguồn tự lấy hiện chưa trả bảng trần/sàn; request MTL/MOK/MAK với
`auto_fetch_data=true` bị từ chối bằng `MISSING_PRICE_LIMITS`, không tự ghép
nguồn khác. Các cách tự lấy cho LO/ATO/ATC hiện có giữ nguyên.

`auto_fetch_data=true` thay hai nguồn nhập tay bằng VN30F1M/VNINDEX 5 phút từ VNDIRECT. Nguồn nhập tay được bỏ qua trước kiểm tra; lỗi tải kết thúc yêu cầu.

Khoảng tải và số nến giữ lại:

- Có `report`: lấy lịch sử trước kỳ theo giá trị lớn nhất từ `warmup_bars`, chỉ báo và `shift`.
- MFI cần `period + 1`; MACD cần `slow_period + signal_period - 1`; ATO cần ít nhất một nến liên tục trước kỳ.
- Đếm ngược theo lịch phiên; contract chỉ đếm nến liên tục. Bản ghi đấu giá trong kỳ vẫn được giữ.
- Hai nguồn dùng chung mốc tải sớm nhất; mỗi nguồn giữ số nến khởi tạo cần dùng và toàn bộ nến trong kỳ.
- Lịch sử có thể bắt đầu giữa phiên; kiểm tra khoảng thiếu từ mốc này. Thiếu mẫu hoặc ngắt chuỗi thì báo chưa đánh giá được.
- Kỳ báo cáo và khoảng thiếu giữ nguyên.
- `metadata.auto_fetch.warmup_bars_requested` ghi lượng yêu cầu; từng nguồn ghi `warmup_count`, `retained_count`.
- Mốc cuối là hết `end_date`, hoặc hiện tại nếu là hôm nay. Bỏ `report`: lấy sáu tháng gần nhất.
- Chỉ giữ nến `Open + 300 <= to`; kiểm tra OHLCV và thời gian.

Với `accounting.model="contract"`, service lấy bảng đáo hạn từ
`AUTO_FETCH_POLICY_PATH`, mặc định [runtime-policy.json](runtime-policy.json);
bảng hiện kết thúc 17/12/2026. Kiểm tra phiên dùng chính sách v1 nói trên.
Normalized không được tự gắn bảng hợp đồng.

- Lịch sử khởi tạo contract bị giới hạn bởi ngày đầu lịch phiên và đầu tháng đầu của bảng đáo hạn.
- Mặc định: 01/03/2026, ghi tại `metadata.auto_fetch.history_start_limit`; `from` ghi mốc tải thực tế.
- Kỳ và `warmup_bars` giữ nguyên. Thiếu mẫu: `UNEVALUABLE`; kỳ ngoài lịch/bảng hợp đồng: từ chối.

- `hnx_sessions_v1` hỗ trợ tự lấy dữ liệu và tạo `contract_dates` theo giả định chuyển mã sau ngày đáo hạn. Giả định được lưu cùng nguồn và kết quả.
- ATO lấy Open bản ghi 09:00; ATC lấy Close bản ghi 14:45. Giá đấu giá tách khỏi chỉ báo.
- Thiếu bản ghi cần khớp làm lượt chạy lỗi. Xem [khớp theo phiên HNX](../../design/hnx-session-matching.md).

- `/validate` trả payload đã tải với `auto_fetch_data=false`; dùng payload này để chạy đúng dữ liệu đã kiểm tra.
- Gửi `true` lần nữa có thể lấy dữ liệu khác.
- Chiến lược cần đóng cuối ngày nên chọn ngày báo cáo đã hoàn tất.

## 5. Nguồn gốc và lưu trữ

- Kho ghim payload, chính sách và metadata bằng `input_hash`/`policy_hash`.
- Tự lấy ghi URL, thời điểm, khoảng lấy, mã băm phản hồi và số nến gốc/đóng/bị loại của từng nguồn.
- Phản hồi HTTP gốc chỉ lưu mã băm.
- Nhập tay ghi `input_origin=caller_provided`; bên gọi chịu trách nhiệm về nguồn, đơn vị volume và độ phủ.

Ứng dụng không đọc `data/dataset_manifest.json` khi chạy JSON.
Chart dựng từ đầu vào đã ghim; nhánh đọc kết quả phiên bản 1 vẫn đọc
dataset/Parquet trong kho file. Xem [thiết kế hệ thống](../../design/system-design.md).

Nguồn liên tục gắn mã từ bảng tham khảo cần đối chiếu riêng với dữ liệu từng hợp đồng. Kiểm tra biên giá cho MTL/MOK/MAK theo mục 4; các lượt thiếu giá tham chiếu ghi `price_limit_check: not performed; reference price not supplied`.
