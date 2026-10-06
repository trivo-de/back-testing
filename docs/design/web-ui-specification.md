# Đặc tả giao diện — Backtesting API

## 1. Phạm vi hiện tại

Trang `/` nhận nội dung JSON hoặc file JSON, có nút tải mẫu, kiểm tra và chạy.
Giao diện mở lại kết quả từ lịch sử, hiển thị summary, nến, khối lượng, chỉ báo,
marker giao dịch, equity và bảng đối chiếu. Notebook dùng cùng API.
Giao diện không tính lại chiến lược, chỉ báo hoặc tiền; dữ liệu thuộc cùng một run.

## 2. Luồng người dùng

1. Nhập JSON hoặc đọc một file JSON vào form; mẫu chỉ minh họa cấu trúc.
2. Kiểm tra bằng `POST /api/backtests/validate`; STRUCTURE_VALID không bảo đảm
   mọi nến đã đủ lịch sử chỉ báo.
3. Chạy bằng `POST /api/backtests`; submit khóa trong khi chờ để tránh gửi trùng.
4. Hiển thị result và tải chart theo `metadata.run_id`; làm mới danh sách lịch sử.
5. Mở kết quả đã lưu bằng GET, không chạy lại chiến lược.

## 3. Mapping dữ liệu

| Thành phần | Nguồn | Quy tắc |
| --- | --- | --- |
| Summary | `summary` | Chỉ định dạng số/return |
| Lịch sử | `GET /api/backtests` | Dùng thứ tự repository trả về |
| Nến và volume | `GET /api/backtests/{run_id}/chart` | Đúng nguồn, kỳ báo cáo, resolution và timezone |
| Chỉ báo | `evaluations` và dữ liệu market của run | Dùng giá trị máy chủ; chỉ hiển thị khi có |
| Marker | `fills` | Giá khớp thật; không dùng signal làm giao dịch |
| Giao dịch đóng | `trades` | Hiển thị quantity, phí và lãi/lỗ đã chốt |
| Vị thế mở | `open_position` | Hiển thị lãi/lỗ chưa chốt riêng |
| Audit | `signals`, `orders` | Giữ trạng thái rejected/pending/filled riêng |
| Equity | `equity_history` | Điểm tại Close, trục riêng với giá nến |

Normalized dùng BUY/SELL; contract dùng LONG/SHORT/CLOSE và thông tin hướng,
mã hợp đồng, phí/thuế/ký quỹ khi có. Không diễn giải normalized quantity thành
số hợp đồng. Các run lịch sử được trình bày theo metadata đã lưu.

## 4. Chart và chọn giao dịch

- Kiểm tra run_id và hash/dataset phù hợp trước khi vẽ; không trộn run cũ/mới.
- Marker neo đúng fill_price; nến chứa fill theo bar_time khi có. Không ép giá
  khớp về High/Low nếu trượt giá đưa fill ra ngoài nến.
- Tooltip lấy reason theo fill.order_id → order.signal_id → signal.reason.
- Chọn marker lọc fills cùng ngày, trade chứa fill, signal/order liên quan,
  vị thế mở từ fill và equity tương ứng. Chọn vùng trống để bỏ lọc.
- Giữ bảng fills để đối chiếu. Rejected/unfilled không có marker.
- Volume và chỉ báo volume không dùng trục giá nến; equity có chart riêng.
- Zoom/scroll/resize không làm marker lệch giá/thời gian; dọn chart/listener khi đổi run.
- Thiếu nến hoặc sai OHLC/hash báo lỗi, không tự điền nến, sort hoặc dời marker.
- Nút thu gọn/mở rộng equity chỉ thay cách trình bày, không sửa dữ liệu.

## 5. Trạng thái và lỗi

Chưa có run, đang tải, thành công có giao dịch, thành công không giao dịch,
vị thế mở và lỗi phải phân biệt rõ. No-trade không đồng nghĩa đủ dữ liệu đánh giá;
hiển thị evaluation_status khi có.

Controller dùng sequence để bỏ response đến muộn. POST thành công nhưng chart
GET lỗi thì giữ result/bảng đã tải và cho thử lại bằng GET. Lỗi history hiển thị
riêng. Khi result lỗi, ẩn kết quả/chart cũ để không gắn với run mới.
Thông báo API được hiển thị bằng text; không thực thi HTML từ dữ liệu.

## 6. Tài nguyên và giao diện đã chọn

HTML/CSS/JavaScript ES modules đóng gói trong `backtesting_api/web`, được
FastAPI phục vụ cùng origin tại `/static`. Module .mjs dùng MIME text/javascript.
Lightweight Charts và LICENSE/NOTICE được lưu trong `web/vendor`.

Style theo [DESIGN.md](DESIGN.md): nền cream, chữ espresso, nút amber;
light/dark qua nút có nhãn truy cập. Main nối `create_app(..., preview=True)`
để dùng preview.css và preview-theme.mjs cho giao diện chính. Theme lưu bằng
`backtest-preview-theme`, đồng bộ tab và phát themechange; không tải lại run.
Màu nến/hướng giao dịch giữ ý nghĩa đã chọn. Font dùng tài nguyên máy/fallback;
không yêu cầu tải font ngoài để chạy.

## 7. Nghiệm thu

- Form/validate/run/history dùng đúng hợp đồng JSON và endpoint còn hoạt động.
- Chart, summary và bảng khớp cùng run/hash; marker đúng số fill và giá/thời gian.
- No-fill, rejected, vị thế mở và lỗi chart được trình bày đúng trạng thái.
- Không tạo POST mới khi thử đọc lại chart; response cũ không thay run đang chọn.
- Tài nguyên đóng gói tải được sau cài đặt/Docker, có attribution của thư viện.
- Mở run sau restart vẫn đọc cùng result; keyboard, label, focus, aria-live và
  bố cục mobile là các mục kiểm tra giao diện.

Các phép kiểm tra và giới hạn bằng chứng tại
[kế hoạch chart](../plans/candlestick-ui-plan.md) và
[checklist tích hợp](../plans/legacy-cleanup-checklist.md).
