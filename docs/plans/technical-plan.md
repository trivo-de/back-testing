# Kế hoạch kỹ thuật — Backtesting API

## 1. Phạm vi

Giữ luồng JSON → dữ liệu → chỉ báo → điều kiện → tín hiệu → thực thi → tài
khoản → kết quả/kho file. Package `backtesting_api`, điểm khởi chạy
`backtesting_api.main:app`. API, giao diện và notebook dùng cùng application.

Phạm vi sản phẩm tại [SRS](../requirements/software-requirements-specification.md).
Quy tắc CANSLIM v1, normalized, ngưỡng, timing và accounting thuộc tài liệu sở
hữu; kế hoạch này không bổ sung hoặc thay đổi quy tắc.

## 2. Thành phần hiện có

- FastAPI và Pydantic: nhận/kiểm tra yêu cầu JSON, phục vụ API và tài nguyên web.
- BacktestService: kiểm tra, gọi run_inline_strategy và đọc/ghi một repository.
- inline_data: chuẩn hóa đầu vào hợp lệ, ghép theo available_at, báo gap/map/kỳ.
- indicators/expressions/inline_strategy: tính chỉ báo, cây điều kiện và trạng thái.
- engine/execution/portfolio/contract_accounting: thời gian, khớp lệnh và tiền.
- inline_results: kết quả JSON cùng metadata/evaluations.
- FileRunRepository: JSON đầu vào/kết quả; Parquet dành cho lịch sử đã có.

Danh sách dependency và phiên bản lấy từ [pyproject.toml](../../pyproject.toml).
Không thêm dependency hoặc framework cho việc dọn source.
Cây source tại [cấu trúc project](../design/project-structure.md).

## 3. Ranh giới dữ liệu

VN30F1M 5 phút là dữ liệu giao dịch chính, VNINDEX tham chiếu theo chiến lược
được cung cấp. Không aggregate daily tự động, không trộn nguồn, không tự fill
missing data hoặc thay symbol để đủ lịch sử. Hợp đồng dữ liệu:
[VN30F1M](../data/vn30f1m/data-contract.md),
[v1](../data/vn30f1m/data-contract-v1.md).

Các nến trước kỳ báo cáo có thể cấp lịch sử chỉ báo; không phát sinh trade
ngoài kỳ. Gap và chuyển hợp đồng phải tuân theo bộ ánh xạ/chính sách đã dùng.
Dữ liệu thị trường chỉ khả dụng sau available_at; không lặp mẫu để đủ cửa sổ.
Mốc sáu tháng của v1 và nghiệm thu dữ liệu thật vẫn theo đặc tả đã chốt.

## 4. Thực thi và tính tiền

Engine điều phối sự kiện; execution tính quantity tại Open theo sizing,
slippage và accounting đã khai báo. Normalized phục vụ mô hình mô phỏng nền;
contract dùng sổ tiền hợp đồng, long/short và đóng một phần vị thế theo JSON.
Không đồng nhất đóng một phần vị thế với khớp một phần lệnh.

Timing, stop/target/trailing, giới hạn ngày và cuối kỳ theo
[đặc tả API](../design/backtest-api-specification.md) và
[accounting v1](../design/canslim-v1-execution-accounting.md).
Không thay threshold để cải thiện kết quả trong đợt dọn.

## 5. API, giao diện và notebook

Endpoint kiểm tra dùng cùng quy tắc dữ liệu/khả năng thực thi với endpoint chạy.
JSON chứa đầy đủ dữ liệu và chiến lược; không cần đăng ký dataset hoặc chiến
lược. Các chức năng đọc theo run_id không chạy lại chiến lược.
Giao diện lấy marker từ fill thực, chỉ báo từ evaluations và tiền từ result.
Notebook gửi JSON rồi GET lại cùng run_id để đối chiếu.

Cách chạy/cấu hình tại [runbook](vn30f1m-backtest-runbook.md).

## 6. Kho file

`BACKTEST_STORE_PATH` mặc định `data/backtest-store`. Đầu vào và chính sách
được ghim trong `inputs/<input_hash>.json`; run và result trong
`runs/<run_id>.json`. Công bố từng tệp bằng thay thế nguyên tử. Một tiến trình
chịu trách nhiệm ghi; nhiều workers cùng ghi chưa thuộc phạm vi hiện tại.

Phiên bản 2 kiểm tra input_hash, policy_hash, result_hash và run_id khi đọc.
Danh sách chỉ gồm succeeded; failed/running được giữ trong tệp run.
Lịch sử phiên bản 1 tiếp tục đọc dataset/Parquet đã ghim để dựng chart;
pyarrow phục vụ nhánh đọc đó. Không sửa hash, UUID hoặc dữ liệu lịch sử để
làm kiểm thử khớp. Docker gắn kho file để giữ kết quả qua restart.

Dữ liệu nguồn và kết quả local tiếp tục được Git bỏ qua. Cách backup, retention
và giới hạn dung lượng sản xuất cần được chốt khi có yêu cầu triển khai tương ứng.

## 7. Kiểm chứng và trạng thái tích hợp

Theo [checklist dọn và đổi tên](legacy-cleanup-checklist.md):
kiểm tra import/tài nguyên đóng gói, test Python/JavaScript, notebook, API và
Docker; đọc lại kết quả sau restart và đối chiếu bằng chứng tổng hợp trước/sau.
Causality dùng dữ liệu đầy đủ, dữ liệu cắt tại t và dữ liệu tương lai bị thay đổi.
Tách UUID khỏi phép so, giữ thời điểm signal/fill/equity và input/policy hash.

Bằng chứng tổng hợp không thay nghiệm thu dữ liệu thật đầy đủ theo kỳ đã chốt.
Giao diện trong trình duyệt, dữ liệu thật và mô hình thanh khoản có phạm vi
kiểm chứng riêng; không coi test nghiệp vụ là bằng chứng cho tất cả các mục đó.

## 8. Công việc mở rộng

Agent/MCP theo [kế hoạch agent](agent-research-plan.md), chưa có runtime.
Queue, xử lý phân tán, nhiều vị thế và kho phiên agent chưa được triển khai.
Khi mở rộng phải chốt tài liệu sở hữu trước source và giữ các kiểm tra hồi quy.
