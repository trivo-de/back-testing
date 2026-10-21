# Tài liệu project

Tài liệu cho `src/backtesting_api`: nhận chiến lược JSON, mô phỏng giao dịch và lưu kết quả. Web và notebook dùng cùng API.

## Bắt đầu sử dụng

- [Cài đặt, chạy API, notebook và Docker](guides/run-backtest.md)
- [Đặc tả API](design/backtest-api-specification.md)
- [Hướng dẫn JSON chiến lược](design/strategy-payload-guide.md)

## Yêu cầu và thiết kế

- [Đặc tả yêu cầu](requirements/software-requirements-specification.md)
- [Thiết kế hệ thống và đường đi lời gọi](design/system-design.md)
- [Cấu trúc repository](design/project-structure.md)
- [Thực thi và tính tiền hợp đồng](design/canslim-v1-execution-accounting.md)
- [Khớp ATO/LO/ATC theo phiên HNX](design/hnx-session-matching.md)
- [Tính tiền normalized](design/normalized-accounting.md)
- [Đặc tả giao diện](design/web-ui-specification.md)
- [Màu sắc và bố cục giao diện](design/DESIGN.md)

## Chiến lược và dữ liệu

- [Mẫu chiến lược CANSLIM v1](strategies/canslim-v1-rules.md)
- [Hợp đồng dữ liệu JSON](data/vn30f1m/data-contract.md)
- [Dữ liệu cho mẫu CANSLIM v1](data/vn30f1m/data-contract-v1.md)
- [Bảng đáo hạn tham khảo](data/vn30f1m/vn30f1m-rollover-map.md)

- `runtime-policy-v1.json`: lịch phiên cho đầu vào có bảng hợp đồng.
- `runtime-policy.json`: bảng đáo hạn khi tự lấy dữ liệu hợp đồng.

## Kiểm thử

- [Kiểm thử hợp đồng và CANSLIM v1](testing/vn30f1m/canslim-v1-test-cases.md)
- [Ví dụ số học normalized](testing/normalized-accounting-test-cases.md)
- [Kiểm thử cấu hình lệnh và nhiều phần vị thế](testing/order-strategy-matching-separation.md)
- [Kiểm thử MTL/MOK/MAK với lượng đối ứng cố định](testing/market-orders-partial-matching.md)

Tài liệu kiểm thử ghi phạm vi và bằng chứng của từng nhóm chức năng.
