# Project documentation

Tài liệu được phân theo loại nội dung; các tài liệu gắn với một dataset nằm
trong `data/<dataset>/`.

## Requirements

- [Software Requirements Specification](requirements/software-requirements-specification.md)

## Design

- [Đặc tả API backtest — tham số v0/v1](design/backtest-api-specification.md)
- [System Design](design/system-design.md)
- [CANSLIM v1 execution/accounting — đặc tả một phần](design/canslim-v1-execution-accounting.md)
- [Database Schema](design/database-schema.md)
- [Project Structure](design/project-structure.md)
- [Web UI Specification](design/web-ui-specification.md)

## Strategy

- [CANSLIM Rules](strategies/canslim-rules.md)
- [CANSLIM v1 — rule đã chốt và mục còn trống](strategies/canslim-v1-rules.md)

## Data contracts

- [HPG data contract](data/hpg/data-contract.md)
- [VN30F1M data contract](data/vn30f1m/data-contract.md)
- [VN30 futures data contract v1](data/vn30f1m/data-contract-v1.md)

## Testing

- [HPG accounting test cases](testing/hpg/accounting-test-cases.md)
- [CANSLIM v1 test cases — khung S10 chưa điền](testing/vn30f1m/canslim-v1-test-cases.md)

## Plans and status

- [Chạy backtest VN30F1M 5 phút qua API/notebook](plans/vn30f1m-backtest-runbook.md)

- [VN30F1M 5 phút: đầu việc và field xác nhận](../.agents/checklists/vn30f1m-backtest-checklist.md)

- [Backtest Plan v0](plans/backtest-plan-v0.md)
- [Technical Plan](plans/technical-plan.md)
- [Candlestick UI Plan](plans/candlestick-ui-plan.md)
- [Progress](plans/progress.md)
- [Agent Research Plan](plans/agent-research-plan.md)
