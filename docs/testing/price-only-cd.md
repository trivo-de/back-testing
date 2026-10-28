# Kiểm chứng phần C–D: cơ chế, lịch sử và giao diện

Ngày 27/10/2026. Phạm vi T09–T16 theo [hợp đồng đã duyệt](../design/price-only-contract.md).
[Mốc A](price-only-baseline.md) và [báo cáo B](price-only-runtime.md) giữ số liệu tại thời điểm tương ứng.

## Cập nhật D08: tự đóng cuối ngày

Sau khi phát hiện mẫu mặc định báo `REQUIRED_EXIT_NOT_FILLED`, bạn yêu cầu engine
tự đóng vị thế khi hết ngày. `price-only-v2` ghim `session_end_action=close_at_close`:
hủy lệnh còn chờ, đóng hết lượng còn giữ tại Close thực của nến cuối phiên liên tục
theo lịch nội bộ, không mở vị thế mới tại Close đó. Lịch hiện tại là 14:30.
Chỉ báo/điều kiện thoát không ngăn bước đóng cuối ngày; nó được ưu tiên trước các
bảo vệ và điều kiện tại Close cuối, sau khi đã xét lệnh chờ khớp trong nến.
Thiếu nến để đóng vẫn báo lỗi; dữ liệu dừng giữa phiên có thể còn vị thế mở.
Hạn `exit.flat_by` sớm hơn vẫn là ràng buộc riêng do chiến lược khai báo.

- Thay đổi tại `application/price_strategy.py`, `api/price_schemas.py`,
  `application/run_backtest.py`, `application/strategy_parameters.py` và nhãn web.
- `tests/test_price_end_of_day.py`: 11 kiểm thử mới, gồm LONG/SHORT, lượng còn lại sau TP,
  LO chờ đóng/mở ở nến cuối, không đóng hai lần, không mở mới tại Close cuối,
  dữ liệu thiếu, chuỗi đầy đủ/cắt, chạy lại bản ghim v1 và mẫu mặc định qua API/lưu/đọc lại.
- Toàn bộ Python **243/243 đạt**, 19,800 giây; web **28/28 đạt**.
- Snapshot của mẫu mặc định từng lỗi tái hiện được lỗi với cấu hình v1.
  Cùng nguồn và request, cấu hình v2 chạy qua, có 123 lần đóng cuối ngày đã hoàn tất;
  phần cuối dữ liệu còn ở giữa phiên nên vị thế hiện tại vẫn được ghi mở.
  Không sửa bytes của snapshot/lịch sử cũ, không lấy dữ liệu khác thay thế.
- Trình duyệt với phiên tổng hợp đầy đủ: giữ nguyên mẫu mặc định, vào 100,19,
  đóng 100,47 lúc 14:30, lượng 1, lãi 0,28 điểm × lượng, vị thế còn mở 0;
  bảng hiển thị **Hết ngày**, không có lỗi/cảnh báo console.
- Đã xác nhận dịch vụ local đang chạy tự nạp `price-only-v2` và mặc định mới.
- Chạy nguyên mẫu trên web của dịch vụ đang dùng với nguồn VNDIRECT đã thành công:
  run `9d742778-e764-4dcc-8321-274e0d5ed10b`, kỳ báo cáo 27/04–27/10/2026,
  dữ liệu thực có từ 28/04 nên vẫn ghi `PARTIAL_REPORT_COVERAGE`.
  124 vị thế đóng, 0 còn mở; toàn bộ 124 lần đóng lúc 14:30, lý do Hết ngày.
  GET bản đã lưu xác nhận mặc định v2; console không lỗi/cảnh báo.
  Đây là kiểm tra chạy được với nguồn đang cấu hình, chưa thay nghiệm thu đầy đủ
  quy ước timestamp/volume và các tiêu chí thị trường thật ở T23.

Các số liệu 232/27 phía dưới là mốc kết thúc C–D trước lần cập nhật D08 này.
Những bản ghim `price-only-v1` tiếp tục đọc và chạy lại theo chính sách ban đầu.

## Thay đổi đã thực hiện

- `api/price_schemas.py`, `application/price_strategy.py`: SL/TP theo % hoặc giá tuyệt đối,
  TP nhiều mức, lượng đóng theo biểu thức và trailing từ entry hoặc sau TP1.
  SL/TP chỉ xét và khớp tại Close; trailing kiểm tra mức cũ trước khi cập nhật mức cho nến sau.
  Entry IMMEDIATE bắt đầu bảo vệ từ nến sau; entry LO xét bảo vệ tại Close sau fill.
  Trailing gửi lệnh đóng theo IMMEDIATE/LO đã cấu hình, không tạo lại LO đang chờ.
- `application/run_backtest.py`, `api/backtest_routes.py`: POST và validate chỉ nhận cấu hình mới.
  Máy chủ luôn lấy dữ liệu, giữ kỳ báo cáo riêng với lịch sử cần thiết, loại nến chưa khả dụng.
  Không nhận nến/file, accounting hoặc cờ tự lấy. Lỗi nguồn không chuyển sang dữ liệu khác.
  Khoảng thiếu nguồn không biến dữ liệu cũ thành mẫu hợp lệ để thoát vị thế.
- `infrastructure/file_repository.py`: schema 3 và snapshot 2 ghim cấu hình có hiệu lực,
  phiên bản mặc định, dữ liệu và chính sách; kiểm tra toàn vẹn trước lưu và khi đọc.
  Chạy lại nội bộ dùng bản ghim, không tải nguồn hoặc áp dụng mặc định mới.
  Bộ đọc schema 1/2 cũ giữ nghĩa và đơn vị gốc.
- Lịch sử phân trang hỗn hợp có bộ lọc đơn vị và chỉ số theo điểm; sắp xếp theo
  tổng lãi/lỗ, phần đã chốt, giảm từ đỉnh hoặc số vị thế đóng hết. Không so điểm với VND/vốn.
- `application/strategy_parameters.py`, `api/app.py`: `GET /api/strategy-parameters`
  xuất schema, mặc định, alias, toán tử, nguồn, lịch sử tối thiểu và ví dụ.
  Giới hạn biểu thức dùng cùng hằng số với bộ kiểm tra.
- `web/backtest-input.mjs`, `backtest-app.mjs`, `backtest-data.mjs`, `backtest-chart.mjs`,
  `index.html`, `language.mjs`, `backtest-input.css`: form và JSON chỉ chứa cấu hình;
  ngày tùy chọn theo cặp; chọn IMMEDIATE/LO; bảo vệ ghi đơn vị %.
  Giữ chính xác chuỗi thập phân và cấu hình nâng cao khi sửa form.
  Kết quả theo điểm, lịch sử cũ, không giao dịch và lỗi được trình bày riêng;
  danh mục chỉ tải khi mở, lịch sử chỉ tải khi tìm.

## Bằng chứng kiểm thử

- Toàn bộ Python: **232/232 đạt**, 26,372 giây; web: **27/27 đạt**.
  Python chạy ngoài sandbox vì TestClient Windows cần socket nội bộ.
- `test_price_protection.py`: 13 kiểm thử bảo vệ, gồm LONG/SHORT, vượt nhiều TP cùng Close,
  trailing không hồi tố, TP1 thực sự khớp mới bật trailing, entry LO và sai mức sau gap.
- `test_price_data.py`: 7 kiểm thử lấy tự động với đồng hồ/nguồn cố định, cắt thời điểm
  khả dụng, không thử lại bằng nguồn khác, chạy lại bản ghim và khoảng thiếu dữ liệu.
- `test_price_history.py`: lưu/đọc, mã băm sai, lỗi ghi, không giao dịch,
  lịch sử hỗn hợp, bộ lọc/sắp xếp/con trỏ và chart từ cùng snapshot.
- `test_strategy_parameters.py`: mọi alias, đầu ra BB/MACD và toán tử công bố đều
  qua kiểm tra và thực thi; ví dụ cấu hình và mặc định khớp schema.
- Giữ kiểm thử số học, thời điểm và chuỗi đầy đủ/cắt tại t của B.
  Kiểm thử đường cũ dùng router chỉ có trong `tests/legacy_inline_app.py`;
  ứng dụng chính không gắn router này. Notebook cũ mới được kiểm tra nội bộ,
  chưa được chuyển sang API mới.
- Hai tệp nguồn và ba cặp run/input ở mốc A được đọc lại, mã băm không đổi.
  `git diff --check` không phát hiện lỗi khoảng trắng.

Lệnh chạy:

```powershell
.venv/Scripts/python.exe -m unittest discover -s tests -p "test_*.py"
node --test tests/web/*.test.mjs
git diff --check
```

## Trình duyệt thực

Chạy ứng dụng thật với bộ lấy nguồn tổng hợp cố định, ghi rõ `SYNTHETIC_UI_QA`;
không gửi nến qua API và không dùng dữ liệu này làm nghiệm thu thị trường.

- Nhập JSON nâng cao → đồng bộ form → validate → chạy → mở lại lịch sử và chart.
  LONG 3 tại 100; TP1 đóng 1 tại 106, TP2 đóng 2 tại 113: lãi đã chốt **32 điểm × lượng**.
  Bảng, marker, đường P&L và bản mở lại cùng kết quả.
- LO giá 100 không được khớp trên nến tạo dù Low đã chạm; sau ba nến không khớp
  thì hết hạn. Không giao dịch hiển thị số 0 và lý do hết hạn.
- Mở kết quả schema 2 bằng VND và schema 3 theo điểm; bộ lọc đơn vị không trộn số học.
- Tra danh mục và tìm trailing; bàn phím dùng được. Màn hình 390 × 844 không tràn ngang;
  không ghi nhận lỗi hoặc cảnh báo console. Ảnh/log QA giữ local trong `.agents/`.

## Giới hạn còn lại

E chưa triển khai LLM. F còn chuyển notebook/ví dụ, dọn mã cũ và cập nhật toàn bộ
tài liệu lịch sử. POST payload cũ nay trả 422; dữ liệu cũ chỉ được đọc theo schema gốc.
Chưa chạy nguồn mạng thật hoặc nghiệm thu VN30F1M tại T23. Không đổi quy tắc/ngưỡng
CANSLIM; bộ ngưỡng % cho mẫu chuyển đổi vẫn cần được chốt riêng ở T19.
Không commit, triển khai dịch vụ hoặc thay đổi dữ liệu thị trường/lịch sử đã lưu.
