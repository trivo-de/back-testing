# Tài liệu project

Tài liệu mô tả source hiện tại trong `src/backtesting_api`. API nhận dữ liệu và
chiến lược JSON, lưu kết quả trong kho file; giao diện và notebook đọc cùng API.
Lịch sử công việc và kế hoạch triển khai cũ không thuộc bộ tài liệu này.

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

`runtime-policy-v1.json` cung cấp lịch phiên cho đầu vào có bảng hợp đồng.
`runtime-policy.json` cung cấp bảng đáo hạn khi tự lấy dữ liệu hợp đồng.
Đây là cấu hình được ứng dụng đọc, không phải tài liệu kế hoạch.

## Kiểm thử

- [Kiểm thử hợp đồng và CANSLIM v1](testing/vn30f1m/canslim-v1-test-cases.md)
- [Ví dụ số học normalized](testing/normalized-accounting-test-cases.md)
- [Kiểm thử cấu hình lệnh và nhiều phần vị thế](testing/order-strategy-matching-separation.md)

Tài liệu kiểm thử dẫn tới các test hiện có. Kiểm thử tổng hợp không thay
nghiệm thu dữ liệu thật toàn kỳ hoặc kiểm tra trực tiếp trong trình duyệt.
