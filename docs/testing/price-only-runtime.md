# Phần B — hai cách khớp và sổ vị thế theo điểm

Ngày kiểm chứng: 27/10/2026. Theo [hợp đồng đã duyệt](../design/price-only-contract.md).
Phần B hoàn tất T04–T08; chưa phải nghiệm thu toàn bộ chuyển đổi C–F.

## Phạm vi đã chạy

| Phần | Mã sở hữu | Hành vi |
| --- | --- | --- |
| Request và điều kiện | `api/price_schemas.py`, `domain/strategy_terms.py`, `domain/expressions.py` | Alias có nguồn/chu kỳ rõ; so sánh ngắn, khoảng gồm cận, all/any, giao cắt, giới hạn cây và kiểm tra kiểu |
| Lịch sử chỉ báo | `application/inline_strategy.py`, `application/run_backtest.py` | Tái sử dụng chỉ báo hiện có; tính đủ chu kỳ/shift/mẫu trước giao cắt; giữ ngưỡng warmup khai báo, không giảm 150 của CANSLIM |
| Sổ vị thế | `domain/price_portfolio.py` | Một LONG/SHORT, lượng nguyên dương; đóng từng phần, phần chốt/chưa chốt riêng bằng Decimal; không vốn hoặc ký quỹ |
| Khớp và thời gian | `application/price_strategy.py` | IMMEDIATE cùng Close; LO từ nến sau, Open tốt hơn hoặc chạm limit, tối đa 3 nến thực có trong ngày; không qua ngày, không tự tạo lần khớp cuối kỳ |
| API và bản lưu | `api/backtest_routes.py`, `application/run_backtest.py`, `infrastructure/file_repository.py` | Cùng kiểm tra cho validate/chạy; tự lấy nguồn; trả schema 3, lưu snapshot schema 2 và đọc lại theo run_id |

Đường mới nhận `entry` ngay ở cấp request, không có trường chọn accounting.
`POST /api/backtests/validate` trả cấu hình đã giải nghĩa và metadata nguồn, không
trả nến trong payload hoặc tạo run. POST chạy lưu request, nguồn, bảng mã hợp đồng,
lịch phiên và mặc định hiệu lực để tái lập từ bản lưu. Marker và bảng cần được chuyển
ở D; chưa dùng giao diện cũ để nghiệm thu response mới.

SL/TP đơn dùng % và chỉ xét/thoát tại Close. Entry IMMEDIATE chỉ bắt đầu xét bảo vệ
từ nến sau; entry LO được xét tại Close sau khi đã khớp. Thiếu volume để tính chỉ báo
hoặc thiếu mẫu mở vị thế trả UNEVALUABLE; không tự điền. Thiếu dữ liệu quản trị vị thế
hoặc còn vị thế cuối phiên thì báo lỗi. Lịch phiên phải có độ phủ.

## Bằng chứng

- `tests/test_price_strategy.py`: **19/19 đạt**, gồm số học LONG/SHORT và đóng từng phần;
  cả bốn hành động IMMEDIATE; sáu ví dụ giá LO của A; khớp nến thứ 3 và cấm nến thứ 4;
  qua trưa, hết ngày/cuối kỳ; SL/TP theo Close và hủy lệnh chờ khi bảo vệ thoát vị thế.
- Giao cắt kiểm tra bằng nhau, thiếu mẫu, nguồn trễ, ngắt chuỗi tại khoảng thiếu;
  không dùng một mẫu thị trường cho cả hai phía. Có kiểm tra khối lượng thiếu.
- API kiểm tra POST → GET, mở lại kho, chart/input cùng bản lưu, phát hiện sai mã băm,
  tái lập các lần khớp và số học không tải nguồn. Đường mới chạy khi bộ accounting cũ
  được thay bằng hàm luôn báo lỗi; không tạo vốn/hệ số giả.
- So chuỗi đầy đủ với chuỗi cắt: tín hiệu, lần khớp và P&L đã có trước mốc cắt không đổi;
  không so trạng thái hết hạn mới sinh do cắt chuỗi.
- Thử đổi tạm thời hạn LO thành 2 nến: kiểm thử khớp nến thứ 3 phát hiện lỗi;
  đã khôi phục mã gốc và kiểm tra lại.
- Toàn bộ Python: **192/192 đạt**, 24,257 giây; web: **27/27 đạt**.
  Python chạy ngoài sandbox vì Windows TestClient bị kẹt socket nội bộ trong sandbox.
- Hai nguồn và ba cặp run/input lịch sử ở mốc A giữ nguyên mã băm; bản cũ vẫn đọc
  theo schema gốc. Không sửa tệp lịch sử để nâng phiên bản.

Lệnh kiểm tra:

```powershell
.venv/Scripts/python.exe -m unittest discover -s tests -p "test_price_strategy.py" -v
.venv/Scripts/python.exe -m unittest discover -s tests -p "test_*.py"
node --test tests/web/*.test.mjs
git diff --check
```

## Phần còn lại tại mốc B

Các giới hạn dưới đây ghi hiện trạng khi kết thúc B; bảo vệ nâng cao, dữ liệu,
lịch sử theo điểm và web đã được hoàn thiện ở [C–D](price-only-cd.md).
API hiện tại chỉ nhận cấu hình mới; số liệu 192/27 ở trên là mốc lịch sử B.

- T09: trailing, TP nhiều mức, giá bảo vệ tuyệt đối và lượng theo biểu thức chưa hỗ trợ;
  các bảo vệ này trả `FEATURE_NOT_IMPLEMENTED` trước khi lấy dữ liệu/chạy.
- T10–T12: còn nghiệm thu đầy đủ dữ liệu/phiên bản lưu trữ và bộ lọc lịch sử theo điểm.
  `/history` tạm chỉ trả bản cũ; bản mới đọc trực tiếp theo run_id hoặc GET danh sách.
- D–F: giao diện, notebook, ví dụ nâng cao và bỏ đường chạy cũ chưa hoàn tất.
  API tạm nhận cả hai cấu trúc trong quá trình chuyển đổi; không tự đổi payload cũ
  sang nghĩa IMMEDIATE hoặc điểm.
- Chưa chạy nguồn mạng thật, trình duyệt hoặc notebook cho đường mới. Kiểm thử tổng hợp
  không thay nghiệm thu thị trường VN30F1M ở T23. Không sửa rule/ngưỡng CANSLIM.
