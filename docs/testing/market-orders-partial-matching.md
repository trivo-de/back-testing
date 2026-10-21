# Kiểm thử MTL/MOK/MAK và nhiều lần khớp

Ngày đối chiếu: 20/10/2026. Phạm vi là cơ chế khớp với **lượng đối ứng cố
định**, không phải nghiệm thu thanh khoản hay sổ lệnh thị trường.

- Đặc tả: [phiên HNX mục 7](../design/hnx-session-matching.md#7-đặc-tả-mtlmokmak--a01), [API mục 3.4.4](../design/backtest-api-specification.md#344-lệnh-mtlmokmak), [kế toán mục 6](../design/canslim-v1-execution-accounting.md#6-hợp-đồng-kế-toán-mtlmokmak).
- Ví dụ riêng: [market-fixed.json](../examples/orders/market-fixed.json).

## Phần đã kiểm tra

| Phạm vi | Bằng chứng trong tests/ |
| --- | --- |
| Ma trận MTL/MOK/MAK 0/2/5, BUY/SELL, bước giá, trần/sàn, lỗi giá kể cả lượng 0 | `test_orders.py`, `test_market_orders.py` |
| Nhiều lệnh cùng ngân sách; MOK thiếu lượng/tiền không tiêu ngân sách; Open và Close không dùng lại lượng | `test_market_orders.py` |
| LO/MTL đặt 5 khớp 2+2+1, giữ nguyên một yêu cầu; LO dư không dùng lại nến chuyển đổi | `test_market_orders.py` |
| Giá vốn bình quân cùng lệnh, bảo vệ neo fill đầu, không tăng quá lượng đã nhận; phân bổ phí và đóng từng phần | `test_multi_execution.py`, `test_market_orders.py` |
| Hạn mức đang giữ + mở còn chờ, không đếm hai lần; bộ đếm ngày chỉ tăng một lần | `test_market_orders.py`, `test_multi_execution.py` |
| Bảo vệ/đóng thay đổi vị thế thì hủy mở/đóng dư cùng phần; thiếu ký quỹ ở fill sau giữ nguyên fill trước | `test_market_orders.py`, `test_multi_session.py` |
| Đóng LONG/SHORT giảm đúng vị thế; nghỉ trưa/ATC/kết thúc kỳ không giữ lệnh thị trường chờ thử lại | `test_market_orders.py` |
| Mô hình không hỗ trợ, giá/biên thiếu/sai/chưa khả dụng, nến thực thi thiếu và phản hồi vượt lượng | `test_market_orders.py` |
| Cùng đầu vào cho cùng kết quả; cắt/thay phần tương lai không đổi lệnh/lần khớp đã hoàn tất | `test_market_orders.py`, hồi quy `test_multi_session.py` |
| POST API → lưu → đọc lại → chart → chạy lại bằng payload/policy ghim, không tải nguồn | `test_market_orders.py` |
| Form giữ JSON, MTL pending riêng, MAK/MOK từ chối pending/model sai, chọn fill sau vẫn nối đúng vị thế | `tests/web/backtest-input.test.mjs`, `multi-position.test.mjs`, `language.test.mjs` |

Đã thử đảo điều kiện kiểm tra đủ lượng MOK trong tiến trình riêng: kiểm thử
ma trận thất bại 2 trường hợp đúng dự kiến. Không sửa source trên đĩa khi
thực hiện phép thử này.

## Kiểm tra trình duyệt

IAB với API thật tại localhost:8771, kho thử riêng
`.agents/market-orders-browser-store`; không dùng kho chạy chính.

- Nạp `market-fixed.json`, kiểm tra đầu vào thành công, chạy và tải biểu đồ.
  MTL mở 2+2+1, MAK đóng 2 rồi 2, còn 1 hợp đồng; lịch sử lệnh hiển thị
  MTL → LO giá 1000,1 và lượng MAK đã hủy 3 rồi 1.
- Đổi nhánh mở sang MOK, xóa pending, giữ lượng cố định 2: không khớp,
  không phí, hủy 5. Cấu hình thay đổi được phản ánh vào JSON hành động.
- Tải lại trang, tìm lịch sử và mở lại lượt MTL: bảng/biểu đồ đúng dữ liệu
  đã lưu. Console không có lỗi/cảnh báo. Đã xem ảnh để kiểm tra bảng cuộn ngang.
- Lượt MTL: `575f4ef9-1e11-47f3-9b17-9f59c3fb9509`;
  lượt MOK: `ccf6b670-9743-41bf-a0c5-df22c8f3ddd1`.

## Lệnh kiểm tra

Kết quả cuối: **Python 163/163**, gồm 18 kiểm thử MTL/MOK/MAK;
**web 26/26**. Kiểm tra 8 tài liệu với 70 liên kết/điểm neo nội bộ đạt;
`git diff --check` đạt. Không thêm dependency, không sửa mẫu CANSLIM.

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -q
node --test tests/web/*.test.mjs
git diff --check
```

Kiểm thử API/kho cần quyền ghi thư mục tạm `.agents`. Lần kiểm tra này chạy ngoài sandbox sau khi `tempfile.mkdtemp` bị treo trong sandbox.

- Phạm vi nghiệm thu: cơ chế trên dữ liệu tổng hợp với lượng đối ứng cố định.
- MTL/MOK/MAK cần bảng trần/sàn có nguồn do bên gọi cung cấp. Tự lấy dữ liệu hiện thiếu bảng này nên bị từ chối.
- ATO/ATC, bảo vệ và SIMULATED dùng giả định khớp riêng trong metadata.
