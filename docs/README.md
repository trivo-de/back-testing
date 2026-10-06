# Tài liệu project

Tài liệu theo loại nội dung; hợp đồng dữ liệu phân theo dataset. Tài liệu yêu
cầu/quy tắc sở hữu behavior; kế hoạch và checklist ghi công việc/bằng chứng.

## Yêu cầu và thiết kế

- [Đặc tả yêu cầu](requirements/software-requirements-specification.md)
- [Thiết kế hệ thống](design/system-design.md)
- [Đặc tả API JSON](design/backtest-api-specification.md)
- [Hướng dẫn payload chiến lược](design/strategy-payload-guide.md)
- [Thực thi và tính tiền hợp đồng v1](design/canslim-v1-execution-accounting.md)
- [Cấu trúc project](design/project-structure.md)
- [Đặc tả giao diện](design/web-ui-specification.md)
- [Style giao diện](design/DESIGN.md)

## Quy tắc và dữ liệu

- [CANSLIM v1](strategies/canslim-v1-rules.md)
- [Công thức nền CANSLIM normalized](strategies/canslim-rules.md)
- [Hợp đồng dữ liệu VN30F1M](data/vn30f1m/data-contract.md)
- [Hợp đồng dữ liệu v1](data/vn30f1m/data-contract-v1.md)
- [Map chuyển hợp đồng tham khảo](data/vn30f1m/vn30f1m-rollover-map.md)
- [Hợp đồng dữ liệu HPG lịch sử](data/hpg/data-contract.md)

## Kiểm thử và thực hiện

- [Ví dụ số học normalized](testing/hpg/accounting-test-cases.md)
- [Các trường hợp kiểm tra CANSLIM v1](testing/vn30f1m/canslim-v1-test-cases.md)
- [Chạy API và notebook](plans/vn30f1m-backtest-runbook.md)
- [Kế hoạch backtest](plans/backtest-plan-v0.md)
- [Kế hoạch kỹ thuật](plans/technical-plan.md)
- [Kiểm chứng chart và giao diện](plans/candlestick-ui-plan.md)
- [Checklist dọn luồng và đổi package](plans/legacy-cleanup-checklist.md)
- [Kế hoạch agent](plans/agent-research-plan.md)
