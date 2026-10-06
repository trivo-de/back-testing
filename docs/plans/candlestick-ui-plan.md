# Kế hoạch kiểm chứng chart và giao diện

## 1. Phạm vi hiện tại

Giao diện đã có form JSON/file, kiểm tra/chạy, lịch sử, chart nến/khối lượng,
marker fill, equity, chỉ báo máy chủ và các bảng đối chiếu. Package tài nguyên
là `backtesting_api/web`; FastAPI phục vụ cùng origin. Thiết kế/behavior tại
[đặc tả giao diện](../design/web-ui-specification.md).

## 2. Điểm nối và source

| Phần việc | Source hiện tại |
| --- | --- |
| Trang và form JSON | `web/index.html`, `web/backtest-app.mjs` |
| Kiểm tra dữ liệu/quan hệ chart | `web/backtest-data.mjs` |
| Nến, marker, volume, chỉ báo và equity | `web/backtest-chart.mjs` |
| Style và light/dark | `web/preview.css`, `web/preview-theme.mjs`, `web/theme.css`, `web/theme.mjs` |
| Vendor và giấy phép | `web/vendor/` |
| Route/static MIME | `api/app.py`, `api/backtest_routes.py` |
| Dữ liệu chart và đọc sau restart | `infrastructure/file_repository.py` |

Các đường dẫn source nằm dưới `src/backtesting_api/`.
API chart dùng run_id; phiên bản 2 ghim input_hash/policy_hash, lịch sử phiên
bản 1 ghim dataset/content hash. Marker dùng fill thực và giá/time đã lưu.
Chart không chạy lại chiến lược hoặc gọi dữ liệu ngoài để xem kết quả.

## 3. Cách kiểm chứng

Test JavaScript kiểm tra ánh xạ dữ liệu, marker/quan hệ bảng, trục volume/chỉ
báo và đồng bộ theme. Test Python kiểm tra HTTP, chart, kho file và notebook.
Docker xác minh đóng gói tài nguyên, MIME và đọc sau restart. Các thao tác
zoom/resize/mobile/focus trong trình duyệt là kiểm tra riêng; bảng dưới là
các trường hợp cần kiểm tra, không phải báo cáo tất cả đã đạt.

Cách chạy theo [README](../../README.md) và [runbook](vn30f1m-backtest-runbook.md).
Nghiệm thu dữ liệu thật phải dùng snapshot/kỳ đã xác nhận; không dùng fixture
đầu ra làm dữ liệu thị trường hoặc suy ra đủ lịch sử từ tên file.

## 4. Các trường hợp kiểm tra


| ID / chức năng   | Input và thao tác                                                      | Expected result                                                                                      | Cấp kiểm tra       |
| ------------------ | ------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------- | -------------------- |
| TC-01 / UI-01      | Ngày bắt đầu sau kết thúc, vốn <=0 hoặc field thiếu             | JSON sai cú pháp báo tại form; sai schema/ngày/vốn được backend trả HTTP 422                           | Browser + API        |
| TC-02 / UI-01      | Double-click Chạy khi POST chưa xong                                   | Chỉ một POST; submit khóa; mở lại sau kết thúc/lỗi                                           | Browser              |
| TC-03 / UI-02      | Tạo run hoặc mở run cũ                                               | Cùng run/version/hash; OHLCV đúng dataset và khoảng ngày inclusive                             | API + Browser        |
| TC-04 / UI-03      | Bar O=100,H=105,L=98,C=103, ngày cố định                             | Thân/râu/crosshair đúng số, không đổi ngày theo timezone                                    | JS + Browser         |
| TC-05 / UI-04      | BUY 2026-01-05 giá 101, SELL 2026-01-07 giá 110, có bars tương ứng | Đúng hai marker với fill IDs, ngày/giá/side; tooltip khớp bảng                                | JS + Browser         |
| TC-06 / UI-04      | Signal thứ Sáu 02/01/2026, fill thứ Hai 05/01                         | Marker tại 05/01, không ở ngày signal/cuối tuần                                                | JS + Browser         |
| TC-07 / UI-04      | Fill price=106, bar high=105 do slippage giả lập                       | Marker ở 106, thấy được; không ép về high                                                    | JS + Browser         |
| TC-08 / UI-04      | Hai order IDs có reason khác nhau; đổi thứ tự arrays               | Join đúng IDs, không join reason bằng chỉ số/ngày                                             | JS                   |
| TC-09 / UI-08      | fills rỗng, orders pending/rejected, equity_history hợp lệ            | Không marker; vẫn nến/volume/equity và giải thích chưa có fill                               | JS + Browser         |
| TC-10 / UI-07      | Chỉ BUY đã khớp, open_position cuối kỳ                             | Một BUY, không tạo SELL; unrealized tách realized                                                | JS + Browser         |
| TC-11 / UI-08      | Thiếu bar của fill, trùng/đảo ngày, sai OHLC, null/NaN/Infinity    | Reject payload, lỗi consistency; không sort/fill/dời marker                                       | JS + API             |
| TC-12 / UI-08      | Lệch lần lượt run_id, input_hash/policy_hash hoặc dataset_id/version/content_hash của lịch sử                       | Không render dữ liệu trộn; báo lỗi                                                             | JS + Browser         |
| TC-13 / UI-02      | Chọn A rồi B; response A đến sau B                                   | Chỉ B được hiển thị; tooltip/listeners của A được dọn                                     | Browser              |
| TC-14 / UI-08      | POST thành công, chart GET lỗi; thử lại; history GET lỗi riêng    | Chỉ GET lại run/chart, không POST mới; history lỗi không hủy result đã tải                 | Browser              |
| TC-15 / UI-05      | Volume 0 và 1.000 ở hai ngày của bars                                | Giá trị đúng 0/1000, không mất ngày, chung time scale với nến                               | JS + Browser         |
| TC-16 / UI-06      | Equity 1000,1100,900 ở ba phiên; summary cuối=900                     | Line đúng ba điểm, cuối khớp summary; không tự tính equity                                  | JS + Browser         |
| TC-17 / UI-07      | Trade có giá vào/ra, quantity, fees, net_pnl; summary return=0.1      | Cột đúng payload, return format 10%; không tự tính trade return                                | Browser              |
| TC-18 / UI-03,09   | Zoom/scroll/fit; resize 1280px rồi 390px; mở run nhiều lần           | Marker đúng tọa độ, volume không che nến, không tràn trang/nhân canvas/listeners           | Browser              |
| TC-19 / UI-09      | Bàn phím, click marker trên mobile, không dựa vào màu             | Form/bảng có focus/label; detail đọc được; aria-live báo state                               | Browser              |
| TC-20 / UI-08      | Reason/API message chứa HTML có event handler                          | Hiển thị như text, không thực thi HTML/script                                                   | Browser              |
| TC-21 / UI-02,03   | GET /, CSS, JS, vendor sau build/install image; chặn CDN                | Assets đúng MIME, chart tải được, attribution hiện trên trang                                | API + Docker/Browser |
| TC-22 / API        | UUID sai, run không có, run failed, bars mất, JSON/hash hoặc schema kho file sai | Đối chiếu HTTP 422/404/409/500 theo endpoint và loại lỗi trong đặc tả API; không lộ path/stack trace                                   | API                  |
| TC-23 / UI-02      | Restart backend/containers giữ volume, mở cùng run                    | Chart/fills/summary/equity/notebook nhất quán; không chạy lại strategy để xem                 | Kho file + Browser     |
| TC-24 / regression | Cùng input/config; chạy tests cũ và so business result               | Accounting/strategy/timing/causality không đổi; fixture UI không giả làm dữ liệu nghiệm thu | Python + integration |

Test status/actual ở PROGRESS hoặc evidence được liên kết từ đó. Expected trong
plan không phải test đã pass; kiểm tra ignore không phải preprocessing acceptance.

## 5. Dữ liệu và bằng chứng

Kết quả tổng hợp trước/sau tích hợp, test và Docker theo
[checklist](legacy-cleanup-checklist.md). Giữ raw/history đã có; không thay
UUID/hash hoặc mốc dữ liệu để làm marker/summary khớp. Lịch sử phiên bản 1
được đọc bằng kho file/Parquet, không được dùng làm cấu hình chạy JSON mới.
