# Màu sắc và bố cục giao diện

Ứng dụng chính dùng `create_app(..., preview=True)`: nạp
[preview.css](../../src/backtesting_api/web/preview.css) sau các CSS nền,
và phục vụ `preview-theme.mjs` khi trình duyệt yêu cầu `theme.mjs`.
Bảng dưới mô tả CSS đang dùng; không phải thiết kế cho một trang giới thiệu riêng.

## 1. Màu giao diện

| Biến CSS | Sáng | Tối |
| --- | --- | --- |
| `--page` | #f8f7f5 | #1c1812 |
| `--surface` | #ffffff | #261f16 |
| `--control` | #f8f7f5 | #332a1e |
| `--text` | #261b07 | #f8f1e5 |
| `--muted` | #61594a | #c6bbaa |
| `--border` | #e3dfd5 | #514535 |
| `--grid` | #f1eee8 | #382f23 |
| `--accent` | #e89b01 | #f9a600 |
| `--error` | #963b2d | #ffa693 |

Nút submit dùng nền #f9a600, chữ #261b07, khi rê chuột nền #e89b01.
Màu nến và hướng giao dịch giữ ý nghĩa riêng, không đổi dữ liệu khi đổi theme.
Chart lấy màu từ theme hiện tại.

## 2. Chữ và thành phần

- Font khai báo: Interphases Pro Variable, Inter Variable, Inter, system-ui,
  sans-serif; dùng font có sẵn trên máy, không cần tải font ngoài.
- Chữ nền 14 px; tiêu đề h1 co giãn 28–36 px, h2 24 px, h3 20 px.
- Trọng lượng 400 cho chữ thường, 492 cho nhãn/nút, 584 cho tiêu đề.
- Panel/form dùng nền surface, viền border, góc 8 px; khoảng trong thường 24 px.
- Bảng dùng chữ 12 px và số có độ rộng đều; mỗi dòng có viền dưới.
- Focus bàn phím có viền rõ; thông báo trạng thái/lỗi có nhãn truy cập.

## 3. Bố cục và điều khiển

Nội dung rộng tối đa 1200 px. Mục lục dọc xuất hiện từ 1200 px,
cửa sổ nhỏ dùng nút mở mục lục. CSS riêng tại
[backtest-navigation.css](../../src/backtesting_api/web/backtest-navigation.css).
Form nhập tham số dùng [backtest-input.css](../../src/backtesting_api/web/backtest-input.css).
Các bảng cuộn theo trang; equity có nút thu gọn riêng.

VN / ENG và nút sáng/tối cùng nằm ở đầu trang. Ngôn ngữ hiện chọn được đánh
dấu bằng chữ đậm/gạch chân; chọn ngôn ngữ hoặc theme không chạy lại backtest.
Chi tiết lưu lựa chọn, trạng thái, chart và khả năng truy cập tại
[đặc tả giao diện](web-ui-specification.md).

`theme.css`/`theme.mjs` vẫn phục vụ khi tạo app không bật preview.
Không xóa các tài nguyên này chỉ vì ứng dụng chính dùng bảng màu preview.
