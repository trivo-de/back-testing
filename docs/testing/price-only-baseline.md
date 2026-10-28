# Mốc kiểm thử và dữ liệu đối chiếu phần A

Ngày 23/10/2026; source trước khi làm A: `f21ed42`.
[Hợp đồng đích](../design/price-only-contract.md) đã được duyệt toàn bộ ngày 27/10/2026;
runtime mới chưa triển khai. Không dùng kết quả kiểm tra tài liệu thay nghiệm thu engine.

## 1. Hiện trạng trước thay đổi

- `.venv/Scripts/python.exe -m unittest discover -s tests -p "test_*.py" -v`: **166/166 đạt**, 22,545 giây.
- `node --test tests/web/*.test.mjs`: **27/27 đạt**.
- `git diff --check`: đạt; chỉ có cảnh báo chuyển LF sang CRLF theo cấu hình Git.
- Không phát hiện lỗi trong các bộ kiểm thử đã chạy. Không kiểm thử trình duyệt,
  notebook, mạng nguồn thật hoặc nhà cung cấp LLM trong bước baseline.
- Log Python và JSON kiểm tra nguồn/hash: `.agents/todo-a/`, bị Git bỏ qua.
  File dưới đây là kết luận cần giữ, không đưa log hoặc dữ liệu thô vào Git.

## 2. Fixture tính tay

`tests/fixtures/price-only-cases.json` gồm LONG đóng một phần/còn mở,
SHORT đóng hết, LONG lỗ, SHORT còn mở cuối kỳ; sáu trường hợp BUY/SELL
Open tốt hơn limit/chạm limit/không khớp; dòng P&L 0 → 18 → 12, drawdown 6.
`tests/test_price_only_fixtures.py` kiểm tra số học, thời gian nguồn và đối chiếu
giá với hàm LO đang có. Bổ sung 4 ví dụ mở/đóng LONG/SHORT khớp ngay tại Close,
không dùng Open nến sau, không có pending. Các kiểm tra này kiểm tra ví dụ hợp đồng,
không phải kiểm thử runtime khớp ngay hoặc nghiệm thu quy tắc bảo vệ.

Sau khi thêm fixture A: toàn bộ **170/170 kiểm thử Python đạt** (23,879 giây),
gồm 4 kiểm tra mới về số học/thời gian, ví dụ tài liệu và giá LO đang có.
93 liên kết file local trong 8 tài liệu liên quan đều tồn tại; UTF-8 và khoảng trắng đạt.
Kiểm tra cuối xác nhận lại bytes/hash của cả hai nguồn và ba cặp run/input không đổi.

Bản cập nhật hai cách khớp giữ nguyên baseline 166/27 và kết quả full-suite
170/170 trước đó. Sau chỉnh sửa hai cách khớp: **5/5 kiểm tra fixture đạt**,
bao gồm kiểm tra mới về ví dụ khớp ngay; không chạy lại toàn bộ Python/web vì
chưa thay runtime. `git diff --check` và kiểm tra liên kết/tính hợp lệ JSON đạt.

Sau khi chốt D03 theo %: **6/6 kiểm tra fixture đạt**, bổ sung ví dụ mức SL/TP/
trailing LONG/SHORT tại giá 1300 và phân biệt 6% với 0,6%. Chỉ kiểm tra số học
hợp đồng, chưa nghiệm thu runtime; không tự đổi ngưỡng CANSLIM từ điểm sang %.

Sau khi chốt SL/TP chỉ xét Close: **7/7 kiểm tra fixture đạt**; 10 trường hợp
LONG/SHORT phân biệt High/Low chạm nhưng Close chưa đạt, Close vượt ngưỡng và
đúng bằng ngưỡng. Fill theo Close, không ép về giá stop/target. Đây là kiểm tra
ví dụ hợp đồng, chưa nghiệm thu runtime; tại mốc kiểm tra này chi tiết trailing
còn chờ duyệt (đã duyệt bổ sung ngày 27/10/2026).

## 3. Bộ nguồn thật chọn để đối chiếu về sau

Nguồn VNDIRECT, resolution 5, múi giờ Asia/Ho_Chi_Minh, bundle
`data/intraday-bundles/bundle-52ca9fbe68ce00878bf9cc10d65a088e47eb80b84086f4ec26deb67a1f4e4f9b.json`.
Đã đọc bytes, kiểm tra SHA-256 trùng manifest và chạy `validate_bars` (OHLCV,
thứ tự timestamp). Không tải mạng, không thêm nến hoặc sửa file nguồn.

| Nguồn | Số nến | Nhãn đầu / nhãn cuối UTC+7 | SHA-256 raw |
| --- | --- | --- | --- |
| VN30F1M | 6076 | 2026-03-18T09:00:00+07:00 / 2026-09-15T14:45:00+07:00 | `0a64c66974969070dbcdf811be40e3c6400d541f5b2834430c3fac188c4e9557` |
| VNINDEX | 6227 | 2026-03-18T09:15:00+07:00 / 2026-09-15T15:05:00+07:00 | `c5810cdcf96b42936c9d403092ee3361fcd694d108c269f1adb1af5098a5def6` |

Phạm vi đối chiếu ban đầu: 01/04–15/09/2026; nến trước 01/04 chỉ khởi tạo
chỉ báo khi đủ mẫu. Mốc yêu cầu URL 01/03 không phải mốc có dữ liệu: nguồn
thực bắt đầu 18/03. Hai nguồn khác nhãn cuối; không cắt/ghép giả để làm bằng nhau.
Bundle ghi `mode=raw_capture_not_backtest_ready`, timestamp semantics và đơn vị
volume đều `unconfirmed`, thời điểm trích xuất null. Đây là bộ ứng viên có nguồn
và hash rõ, **chưa được nghiệm thu thị trường**. Trước T23 phải xác nhận timestamp,
nhãn đấu giá, đơn vị volume và chuyển mã; mọi giả định được duyệt phải ghim vào
snapshot. Phần A không tuyên bố nguồn đáp ứng đầy đủ lịch phiên hoặc không thiếu nến.

## 4. Mẫu lịch sử phải giữ nguyên

Đọc ba bản thành công bằng `FileRunRepository.get_run/get_input`; kiểm tra
hash kết quả/đầu vào đang có và SHA-256 tệp trước/sau đọc đều không đổi.
Chỉ là mẫu, không quét toàn bộ 82 tệp trạng thái trong kho.

| Run ID (schema 2) | SHA-256 tệp runs/{id}.json | input_hash = SHA-256 tệp input |
| --- | --- | --- |
| `01a6d5a4-1dff-48c5-a2d4-4817fc7359e4` | `a3f6528fc9755b6dc38a2ccecfb460c753779dc6538f4284c5558175eaa11364` | `22fc2fffeb9d6dc242aa6f1a874775a04adfd31c6f06fe6a67073f9951469299` |
| `02061147-5885-45b6-a3cb-c4691f80dbd2` | `6ccfa9a301a5b026e79a07e3b9eb8d4352807a1cda1cc9a59517f953aa53e1c5` | `b4f1b8d2ae56e1aaae6c8f41587bc857f2af965e860186c636f4ff3e78761e6f` |
| `0530eb1f-f93d-483c-ae83-744cfca9e147` | `b9ed49aefbbb553fcf3685eeae4c2edeed2f7787eacbafcb0cf507b5fc44f18f` | `33d40786d1c497350cf4d6e61840f11dbcb8b46894be709666ad74b1dcdfef54` |

Mã băm trên là bytes tệp, khác `result_hash` của JSON chuẩn hóa; không tráo hai
khái niệm. Bản baseline chi tiết trong `.agents/todo-a/baseline.json` giữ cả hai.
Các tệp dữ liệu và lịch sử tiếp tục local-only, không chuyển vào Git.

## 5. Kiểm tra đồng bộ ngày 27/10/2026

- HEAD vẫn là `f21ed42`; lần đồng bộ này chỉ sửa tài liệu và trạng thái công việc,
  không sửa mã thực thi hoặc điều kiện chiến lược.
- `tasks/hop-dong-A-cho-duyet.md` và hợp đồng đích trong `docs/design/` cùng nội dung,
  chỉ khác đường dẫn liên kết. Hai bản `price-only-cases.json` trong `tasks/`
  và `tests/fixtures/` giống nhau từng byte.
- `.venv/Scripts/python.exe -m unittest discover -s tests -p "test_price_only_fixtures.py" -v`:
  **7/7 đạt**. `node --test tests/web/*.test.mjs`: **27/27 đạt**.
- Toàn bộ Python: **173/173 đạt**, 15,894 giây, chạy bằng lệnh ở mục 1 ngoài sandbox.
  Lượt đầu trong sandbox bị kẹt ở socket nội bộ khi Windows tạo vòng lặp sự kiện
  cho `TestClient`; chạy lại ngoài sandbox đạt mà không sửa mã. Các số 166/170
  ở trên vẫn là bằng chứng ngày 23/10, không thay bằng số mới.
- Đối chiếu SHA-256 của 2 nguồn và 3 cặp kết quả/đầu vào lịch sử: trùng mốc A.
  Không tải mạng hoặc sửa dữ liệu để kiểm tra.
- Kiểm tra 76 liên kết file trong các tài liệu Markdown của `tasks/` và hai tài liệu
  hợp đồng/mốc kiểm thử ở `docs/`: đều tồn tại. `git diff --check`: đạt.
- Bạn xác nhận đã duyệt các phần còn lại của A ngày 27/10/2026: D02, D08, D09
  và toàn bộ chi tiết D07. D08 theo bản kế hoạch bạn sửa: không giữ vị thế qua ngày,
  LO tối đa 3 nến và chỉ trong ngày đặt. T01–T03 và điểm kiểm tra A hoàn tất.
  Chưa nghiệm thu trình duyệt, notebook hoặc dữ liệu thị trường cho bộ chạy mới.
