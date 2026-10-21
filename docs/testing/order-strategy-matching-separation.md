# Kiểm thử cấu hình lệnh và nhiều phần vị thế

- Hợp đồng đầu vào và kết quả ở [đặc tả API, mục 3.4](../design/backtest-api-specification.md#34-execution).
- Ví dụ đầy đủ: [LO](../examples/orders/lo-auto.json) và [ATO/ATC](../examples/orders/ato-atc-partial-auto.json).
- Hai ví dụ dùng tự lấy dữ liệu; kiểm thử schema không gọi nguồn thị trường.

## Phạm vi và bằng chứng

| Nội dung | Kiểm thử |
| --- | --- |
| Yêu cầu lệnh bất biến, giá LO, bước giá, loại không hỗ trợ; giá/thời điểm/lượng khớp | `tests/test_orders.py` |
| Cũ/mới tương đương: normalized next_open, contract next_open, LO, ATO, ATC và next_open trong HNX; thời hạn khi thiếu nến | `tests/test_order_strategy.py` |
| Nhánh có hướng và loại lệnh riêng; priority một vị thế; từ chối cấu hình mâu thuẫn; ref lồng góp vào warm-up; hai ví dụ hợp lệ | `tests/test_order_strategy.py` |
| Tiền chung, giá vốn/phí riêng, ký quỹ tổng, chặn hướng ngược, đóng chỉ phần chỉ định | `tests/test_contract_book.py` |
| Đang giữ + mở đang chờ không vượt hạn mức; giảm lượng nhánh sau; giải phóng hạn mức; bảo vệ riêng | `tests/test_multi_execution.py`, `tests/test_multi_session.py` |
| Nhiều ATO/ATC, phần không khớp hết hiệu lực, liên kết signal/order/fill/trade và bảo toàn lượng | `tests/test_multi_session.py` |
| Open trước Close; stop tại Open trước LO chạm sau đó; TP tại Open không dùng Low/High tương lai để đổi kết quả | `tests/test_multi_session.py` |
| Giá vốn, stop/TP và số nến giữ riêng; bộ đếm ngày chung; priority và lượng 3+2 | `tests/test_multi_strategy.py` |
| API lưu/đọc, chart, chạy lại bằng payload/policy đã ghim; UUID và open_positions; thống kê không đếm lặp thời điểm | `tests/test_multi_strategy.py` |
| Lặp cùng đầu vào; cắt và thay dữ liệu tương lai giữ nguyên giao dịch đã hoàn tất | `tests/test_order_strategy.py`, `tests/test_multi_session.py`, các hồi quy phiên/engine hiện có |
| Biểu mẫu ↔ JSON cũ/mới, giữ giá/thời hạn khi đổi loại, giữ bản nháp sai; đọc mọi phần vị thế; bản dịch | `tests/web/backtest-input.test.mjs`, `tests/web/multi-position.test.mjs`, `tests/web/language.test.mjs` |

## Cách chạy

Tại gốc repository, dùng môi trường `.venv` đã có:

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
node --test tests/web/*.test.mjs
git diff --check
```

Các kiểm thử kho file tạo thư mục tạm dưới `.agents/`; cần quyền ghi vào thư
mục này trong môi trường chạy kiểm thử. `.agents/` tiếp tục được Git bỏ qua.

## Kết quả đối chiếu ngày 20/10/2026

- Python: 143/143 đạt.
- `test_daily_entry_limit_conflict_and_sizing_without_future_prices`: vốn 100 triệu, giá mở 1.000; rủi ro 1% cho 1 hợp đồng, 2% cho 3 hợp đồng. Đầu vào kiểm thử khai báo rõ tỷ lệ.
- Web: 24/24 đạt. `git diff --check` không có lỗi khoảng trắng.
- Đã thử đảo điều kiện tách giá Open trong một tiến trình riêng: kiểm thử
  `test_open_target_cannot_be_replaced_by_a_later_stop` thất bại đúng như
  mong đợi. Khôi phục hàm trong tiến trình; không sửa file nguồn.
- Trình duyệt local: nạp payload tổng hợp, kiểm tra qua API, chạy thành công,
  hiển thị hai lần khớp LO và hai phần vị thế lượng 3+2. Tải lại trang, tìm
  lịch sử và mở lại kết quả/biểu đồ thành công; không có lỗi JavaScript.
  Kho thử và ảnh bằng chứng đặt local dưới `.agents/`.

- Phạm vi trên dùng dữ liệu tổng hợp; Open/Close theo quy ước OHLC của dự án.
- Giới hạn lượng đấu giá là tham số mô phỏng.
- Phần mở rộng MTL/MOK/MAK và nhiều lần khớp tại [hồ sơ kiểm thử](market-orders-partial-matching.md).
