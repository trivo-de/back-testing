# Hợp đồng dữ liệu JSON — VN30F1M

API nhận `trade_data` và `market_data` trong yêu cầu, hoặc tự lấy hai nguồn khi
`auto_fetch_data=true`. Không chọn dữ liệu, chiến lược hoặc cách tính tiền từ
một dataset ID. Các trường chi tiết tại [đặc tả API](../../design/backtest-api-specification.md).

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

Tại quyết định `t`, chỉ đọc nến tham chiếu có `available_at <= t`.
Một nến tham chiếu dùng cho nhiều quyết định vẫn chỉ là một mẫu tính chỉ báo.
Không nội suy, lặp hoặc điền nến thiếu để tạo đủ lịch sử.

## 2. Kỳ báo cáo và khởi tạo chỉ báo

`report` gồm ngày bắt đầu/kết thúc, tính cả hai đầu theo múi giờ trade_data.
Bỏ report thì dùng ngày đầu/cuối của chuỗi giao dịch. Ngày bắt đầu lớn hơn
ngày kết thúc bị từ chối bằng `INVALID_REPORT_RANGE`. Nguồn thiếu ngày đầu
hoặc cuối kỳ vẫn chạy trên các nến thực có, giữ nguyên `report_range` đã yêu cầu;
`metadata.available_range` ghi ngày đầu/cuối của nến giao dịch thực có trong kỳ.
Khi áp dụng lịch phiên, các nến thiếu vẫn được ghi trong `data_gaps`.
Chỉ trả `REPORT_DATA_MISSING` khi không có nến giao dịch nào trong kỳ, kèm kỳ
yêu cầu và ngày đầu/cuối dữ liệu nguồn. Không tự rút ngắn kỳ hoặc tạo nến bù.
Nến trước kỳ được giữ để khởi tạo chỉ báo, không tạo giao dịch;
nến sau ngày kết thúc không vào engine.

`strategy.warmup_bars` là ngưỡng lịch sử bổ sung theo yêu cầu JSON.
Thiếu lịch sử hoặc giá trị cần cho entry thì `UNEVALUABLE`, không tạo entry.
Mẫu CANSLIM v1 dùng 150 nến VNINDEX, tính cả nến hiện tại đã khả dụng.
Không tự thay kỳ báo cáo để che thiếu lịch sử.

## 3. Lịch phiên và bảng hợp đồng

Khi có `trade_data.contract_map`, service đọc `INLINE_POLICY_PATH`, mặc định
[runtime-policy-v1.json](runtime-policy-v1.json). Bảng hợp đồng được kiểm tra
ngày đáo hạn, Unix, mã không trùng, thứ tự, tháng liên tiếp và độ phủ cả lịch sử
trước kỳ. Dòng đầu phủ từ đầu tháng đáo hạn; dòng sau phủ sau ngày đáo hạn
trước tới hết ngày đáo hạn hiện tại. Muốn lấy lịch sử sớm hơn phải thêm dòng.

Nguồn giao dịch có bảng hợp đồng phải dùng `Asia/Ho_Chi_Minh`.
Với mỗi nguồn 5 phút được gửi, `_session_gaps()` kiểm tra cả trade_data và
market_data theo lịch/nhãn giờ trong chính sách. Lịch mặc định bao phủ
01/03–31/12/2026, có 213 ngày giao dịch. Nhãn bắt buộc và tùy chọn của
hai nguồn khác nhau; không lấy ngày có dữ liệu làm lịch giao dịch.

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

`auto_fetch_data=true` ưu tiên thay toàn bộ hai nguồn nhập tay bằng VN30F1M
và VNINDEX 5 phút từ VNDIRECT. Hai nguồn nhập tay bị bỏ qua trước kiểm tra.
Tải lỗi thì dừng; không chuyển sang dùng dữ liệu nhập tay hoặc ghép nguồn.

Khi có `report`, chỉ lùi mốc tải đủ số nến khởi tạo cần dùng: lấy giá trị lớn
nhất giữa `warmup_bars`, số nến tối thiểu của chỉ báo và phần nhìn lùi `shift`.
MFI cần `period + 1`, MACD cần `slow_period + signal_period - 1`; ATO cần ít
nhất một nến liên tục trước kỳ để có giá tham chiếu. Đếm ngược theo lịch phiên,
bỏ ngày nghỉ; mô hình contract chỉ đếm nến trong giờ liên tục. Hai nguồn dùng
chung mốc tải sớm nhất cần thiết, rồi mỗi nguồn chỉ giữ số nến khởi tạo cần dùng
và toàn bộ dữ liệu trong kỳ. Không tính bản ghi đấu giá vào số nến khởi tạo
contract; vẫn giữ các bản ghi này trong kỳ. Lịch sử có thể bắt đầu giữa phiên;
không báo thiếu các nhãn trước mốc đó, nhưng vẫn kiểm tra khoảng thiếu phía sau.
Thiếu nến nguồn hoặc bị ngắt chuỗi thì vẫn báo chưa đánh giá được, không tự
điền nến hoặc kéo dài lịch sử qua khoảng thiếu. Không đổi kỳ báo cáo.
`metadata.auto_fetch.warmup_bars_requested` ghi số nến yêu cầu; `warmup_count`
và `retained_count` của mỗi nguồn ghi số nến khởi tạo và tổng số nến giữ lại.
Mốc cuối là hết `end_date` hoặc thời điểm hiện tại nếu đó là hôm nay. Khi không
có `report`, khoảng báo cáo mặc định vẫn là sáu tháng gần nhất, không phải sáu
tháng khởi tạo bổ sung. Chỉ giữ nến `Open + 300 <= to`; OHLCV/thời gian vẫn phải hợp lệ.

Với `accounting.model="contract"`, service lấy bảng đáo hạn từ
`AUTO_FETCH_POLICY_PATH`, mặc định [runtime-policy.json](runtime-policy.json);
bảng hiện kết thúc 17/12/2026. Kiểm tra phiên dùng chính sách v1 nói trên.
Normalized không được tự gắn bảng hợp đồng.

Khi có `report`, phần lịch sử khởi tạo tự tải của mô hình contract bắt đầu
không sớm hơn ngày đầu lịch phiên và đầu tháng đầu tiên trong bảng đáo hạn.
Với chính sách mặc định, giới hạn này là 01/03/2026, được ghi tại
`metadata.auto_fetch.history_start_limit`; `from` ghi mốc tải thực tế.
Kỳ báo cáo và ngưỡng `warmup_bars` giữ nguyên; thiếu mẫu vẫn báo
`UNEVALUABLE`. Kỳ báo cáo ngoài lịch/bảng hợp đồng vẫn bị từ chối.

Khớp theo phiên `hnx_sessions_v1` cũng hỗ trợ tự lấy dữ liệu. Service tạo
`contract_dates` theo bảng đáo hạn, giữ mã đến hết ngày đáo hạn rồi chuyển mã từ
ngày sau đó; đây là giả định đã được người dùng đồng ý, được ghi trong nguồn dữ
liệu và kết quả. ATO dùng Open bản ghi nhãn 09:00; ATC dùng Close bản ghi nhãn
14:45. Giá đấu giá bị tách khỏi chuỗi chỉ báo; thiếu bản ghi đang cần làm lượt
chạy lỗi, không lấy giá gần nhất thay thế. Chi tiết tại
[khớp theo phiên HNX](../../design/hnx-session-matching.md).

`/validate` trả payload đã tải với `auto_fetch_data=false`; gửi lại payload này
để chạy đúng snapshot đã kiểm tra. Gửi `true` lần nữa có thể lấy dữ liệu khác.
Không tạo thêm nến đóng vị thế khi lấy giữa phiên; nên chọn ngày báo cáo đã
hoàn tất nếu chiến lược cần đóng cuối ngày.

## 5. Nguồn gốc và lưu trữ

Kho file ghim payload cụ thể, chính sách và metadata bằng input_hash/policy_hash.
Tự lấy dữ liệu ghi URL, thời điểm/khoảng lấy, mã băm phản hồi, số nến gốc,
số nến đã đóng và số bị loại của từng nguồn. Không lưu riêng toàn bộ phản hồi HTTP.
Đầu vào nhập tay được ghi `input_origin=caller_provided`; API không tự xác
minh vendor, đơn vị volume hoặc tính đầy đủ của lịch sử chỉ từ nhãn symbol.

Ứng dụng không đọc `data/dataset_manifest.json` khi chạy JSON.
Chart dựng từ đầu vào đã ghim; nhánh đọc kết quả phiên bản 1 vẫn đọc
dataset/Parquet trong kho file. Xem [thiết kế hệ thống](../../design/system-design.md).

Biên độ giá chưa được kiểm tra vì không có giá tham chiếu; metadata lưu rõ
`price_limit_check: not performed; reference price not supplied`.
Việc gắn mã từ bảng tham khảo không chứng minh nguồn liên tục VN30F1M đã
được đối chiếu với dữ liệu từng hợp đồng thực tế.
