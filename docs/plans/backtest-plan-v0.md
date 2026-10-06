# Kế hoạch backtest VN30F1M

## 1. Mục tiêu và phạm vi

Sản phẩm nhận chiến lược/dữ liệu JSON, chạy backtest có thể tái lập, lưu kết
quả và trình bày qua API, notebook, chart. Symbol hiện hành VN30F1M; 5 phút
là khung giao dịch chính, 1D hỗ trợ theo JSON. Không tối ưu ngưỡng hoặc tự
thêm chiến lược, dữ liệu hoặc cách tính tiền ngoài quyết định đã chốt.

[Đặc tả yêu cầu](../requirements/software-requirements-specification.md) sở hữu
phạm vi sản phẩm; [quy tắc v1](../strategies/canslim-v1-rules.md) và
[công thức nền normalized](../strategies/canslim-rules.md) sở hữu chiến lược.

## 2. Nhóm công việc

| Nhóm | Kết quả và ranh giới |
| --- | --- |
| Dữ liệu và nghiệp vụ | Kiểm tra OHLCV/thời gian/map, không dùng dữ liệu tương lai; quy tắc và tiền có fixture đối chiếu |
| Engine và JSON | Chỉ báo/biểu thức, tín hiệu, thực thi và tài khoản tách lớp; tổ hợp chưa hỗ trợ bị từ chối |
| API, lưu trữ và trình bày | Một kho file, API/web/notebook cùng result; chart và marker theo fill thật; đọc sau restart |
| Agent và mở rộng | Thiết kế dự kiến, chỉ triển khai khi có yêu cầu và giao diện/giới hạn đã chốt |

Thành phần đã có tại [kế hoạch kỹ thuật](technical-plan.md) và
[cấu trúc source](../design/project-structure.md). Trạng thái đợt dọn luồng
và đổi package theo [checklist](legacy-cleanup-checklist.md), không theo lịch
hoặc ước lượng của một kế hoạch cũ.

## 3. Thứ tự và nghiệm thu

Chốt phạm vi/dữ liệu → cập nhật tài liệu sở hữu → sửa source → chạy kiểm tra
liên quan → tích hợp API/kho file → đánh dấu kết quả đã xác minh.
Không dùng báo cáo khảo sát hoặc thiết kế dự kiến để đánh dấu implementation.

- Cùng JSON/chính sách cho cùng nghiệp vụ, thời điểm và hash sau khi tách UUID.
- Signal sau Close không khớp trước Open hợp lệ; dữ liệu tương lai không đổi quá khứ.
- Sai schema/OHLC/tham chiếu/map bị từ chối; thiếu warm-up không được coi là đạt.
- Run lưu đầy đủ; failed/running không xuất hiện như thành công.
- Result/input/chart mở lại sau restart và thuộc cùng run.
- API, notebook và tài nguyên Docker dùng package `backtesting_api`.
- Nghiệm thu dữ liệu thật sáu tháng của v1 vẫn là kiểm tra riêng, không suy ra
  từ fixture tổng hợp hoặc các lượt chạy lịch sử rút kỳ.

## 4. Công việc còn cần chốt khi mở rộng

Nguồn và độ phủ dữ liệu thật từng hợp đồng, các kiểm tra giao diện trong trình
duyệt, backup/retention sản xuất, xác thực và trạng thái agent được xử lý khi
có task tương ứng. Không tự thay policy/rule để vượt kiểm tra dữ liệu thiếu.

Tài liệu thực hiện: [runbook API/notebook](vn30f1m-backtest-runbook.md),
[kế hoạch chart](candlestick-ui-plan.md), [kế hoạch agent](agent-research-plan.md).
