# Đặc tả yêu cầu — Backtesting API

## 1. Mục tiêu và phạm vi

Hệ thống chạy chiến lược được cung cấp bằng JSON, từ dữ liệu → chỉ báo →
điều kiện chiến lược → tín hiệu → khớp lệnh → tài khoản → kết quả. Độ đúng
được đánh giá theo dữ liệu, quy tắc, thời điểm và số học, không theo lợi nhuận.

Symbol hiện hành là VN30F1M, dữ liệu chính 5 phút; 1D là khả năng hỗ trợ theo
cấu hình JSON. Chiến lược và cách tính tiền thuộc nội dung đầu vào được kiểm
tra, không được suy ra từ tên symbol hoặc tên CANSLIM. Quy tắc v1 đã chốt tại
[CANSLIM v1](../strategies/canslim-v1-rules.md); công thức nền normalized tại
[CANSLIM nền](../strategies/canslim-rules.md). Không thay quy tắc khi dọn source.

API nhận JSON trực tiếp; giao diện web và notebook dùng cùng API. Đầu vào,
chính sách và kết quả được lưu tại kho file. Hệ thống đọc lại kết quả lịch sử
phiên bản 1 và kết quả JSON phiên bản 2 theo định dạng đã lưu.

## 2. Yêu cầu chức năng

| ID | Yêu cầu |
| --- | --- |
| FR-001 | Nhận dữ liệu, chiến lược, execution, accounting, vốn và kỳ báo cáo bằng JSON theo đặc tả API. |
| FR-002 | Từ chối schema, kiểu, OHLC, thời gian, thứ tự nến và tham chiếu sai; không tự sửa dữ liệu. |
| FR-003 | Chỉ báo chỉ dùng dữ liệu đã khả dụng; thiếu lịch sử phải ghi trạng thái chưa đánh giá được. |
| FR-004 | Đánh giá cây điều kiện và tạo tín hiệu/reason; tín hiệu không tự trở thành giao dịch. |
| FR-005 | Tín hiệu sau Close chỉ được khớp tại Open hợp lệ kế tiếp theo cấu hình; stop/target trong nến theo quy tắc đã chốt. |
| FR-006 | Tính quantity tại lúc thực thi theo sizing và accounting trong JSON; lệnh không đủ điều kiện phải bị từ chối. |
| FR-007 | Ghi riêng tín hiệu, order, trạng thái bị từ chối/chưa khớp và fill thực tế. |
| FR-008 | Ghi cash, vị thế, phí, lãi/lỗ đã chốt/chưa chốt, equity và ký quỹ khi áp dụng. |
| FR-009 | Xử lý cuối kỳ theo execution/exit đã khai báo; không tạo giá hoặc giao dịch giả để đóng vị thế. |
| FR-010 | Kết quả có metadata, signals, orders, fills, trades, open_position, equity_history, summary và evaluations. |
| FR-011 | Cùng đầu vào và chính sách cho cùng kết quả nghiệp vụ; UUID không thuộc phép so số học. |
| FR-012 | Kiểm tra JSON bằng cùng quy tắc dữ liệu và khả năng thực thi trước khi chạy. |
| FR-013 | Giao diện chỉ trình bày kết quả máy chủ, không tính lại quy tắc hoặc tiền. |
| FR-014 | Summary, bảng, equity và chart phải thuộc cùng run_id và nguồn dữ liệu. |
| FR-015 | Nến, khối lượng và marker dùng dữ liệu chart của run; marker theo fill, không theo signal. |
| FR-016 | Chỉ công bố lượt chạy thành công khi kết quả đầy đủ đã được lưu. |
| FR-017 | Liệt kê và mở lại run theo run_id sau khi khởi động lại ứng dụng. |
| FR-018 | Ghim đầu vào/chính sách bằng hash và kiểm tra tính toàn vẹn khi đọc lại. |

## Các trường hợp ngoại lệ và tiêu chí chấp nhận


Bảng này gom các tình huống người dùng hoặc hệ thống có thể gặp ở cấp yêu cầu.
Mã `SRS-EX-*` được dùng để nối sang test case; rule chi tiết thuộc tài liệu
strategy, còn status HTTP thuộc đặc tả API.

| Case ID | Điều kiện | Hành vi hệ thống bắt buộc | Tiêu chí kiểm tra |
| --- | --- | --- | --- |
| `SRS-EX-01` | Input sai schema, thiếu metadata/cột bắt buộc, ngày trùng hoặc giảm dần, OHLC không hợp lệ | Từ chối trước khi chạy; trả lỗi có cấu trúc; không tạo kết quả thành công | Validator test xác nhận lỗi và không có fill/result thành công |
| `SRS-EX-02` | Thiếu dữ liệu cần cho indicator hoặc chưa đủ warm-up tại thời điểm `t` | Đánh dấu không đánh giá được; không coi là đạt, không tự lùi kỳ, không tự điền dữ liệu | Fixture thiếu history không sinh signal và ghi reason |
| `SRS-EX-03` | Signal ở Close `t` không có Open thực thi kế tiếp hoặc là signal cuối kỳ | Giữ pending/unfilled hoặc ghi trạng thái cuối kỳ; không tạo fill giả | State-machine test xác nhận không có fill ngoài dữ liệu |
| `SRS-EX-04` | Quantity dưới 1, không đủ cash hoặc lệnh bị từ chối | Giữ signal, ghi rejected order/reason, không thay đổi vị thế | Accounting/execution test đối chiếu signal, order và position |
| `SRS-EX-05` | Core invariant, persistence hoặc ghi kết quả thất bại | Run ở trạng thái failed với lỗi có cấu trúc; không công bố partial result là thành công | Atomicity test xác nhận không đọc được run như succeeded |
| `SRS-EX-06` | Service restart hoặc result/input không còn hợp lệ khi đọc lại | Run thành công hợp lệ phải đọc lại được; tệp sai hash/schema phải bị từ chối | Reload/integrity test đối chiếu cùng kết quả nghiệp vụ hoặc lỗi rõ ràng |
| `SRS-EX-07` | Có dữ liệu sau thời điểm quyết định hoặc chạy lại cùng input/config | Không dùng dữ liệu tương lai; kết quả đến `t` phải giữ nguyên và chạy lại phải cho cùng kết quả | Causality và determinism test so sánh event đến cutoff |
| `SRS-EX-08` | UI/API nhận run no-trade, rejected, loading hoặc error | Phân biệt đúng trạng thái; không hiển thị lỗi/partial result như kết quả giao dịch thành công | Acceptance UI/API kiểm tra mapping theo cùng `run_id` |

## 3. Yêu cầu chất lượng

- Không sử dụng dữ liệu tương lai; thay dữ liệu sau thời điểm t không làm đổi
  kết quả trước t. Dữ liệu đầy đủ và dữ liệu cắt tại t phải khớp phần chung.
- Giữ riêng các lớp dữ liệu, chỉ báo, chiến lược, tín hiệu, thực thi, tài khoản
  và kết quả. Domain không phụ thuộc HTTP hoặc kho lưu trữ.
- Tính tiền bằng Decimal; số thập phân được giữ qua lưu/đọc JSON.
- Lưu engine_version, input_hash, policy_hash, accounting và thông tin nguồn.
- Lượt chạy failed/running không xuất hiện trong danh sách thành công.
- Chạy một tiến trình ghi kho file; chưa yêu cầu xử lý ghi phân tán.

## 4. Nghiệm thu tích hợp

- Kiểm tra timing, sizing, accounting, dữ liệu thiếu, tham chiếu và cây điều kiện.
- Chạy cùng fixture/JSON cho cùng summary, signals, orders, fills, trades,
  equity, evaluations và hash, sau khi tách UUID.
- Kiểm tra, chạy, liệt kê, đọc kết quả/input/chart qua API; đọc lại sau restart.
- Đọc được lịch sử phiên bản 1 còn giữ mà không chạy lại chiến lược.
- Tài nguyên web được đóng gói, các module .mjs có MIME phù hợp trình duyệt.
- Kiểm thử tổng hợp không thay nghiệm thu dữ liệu thật toàn kỳ.

## 5. Ngoài phạm vi hiện tại

Live trading, dữ liệu thời gian thực, nhiều vị thế đồng thời, mô hình thanh khoản,
khớp một phần lệnh, xác thực nhiều người dùng và agent/MCP chưa thuộc hệ thống
hiện tại. Đóng một phần vị thế theo rule là khả năng riêng với khớp một phần lệnh.
Không tối ưu ngưỡng hoặc bổ sung chiến lược trong đợt dọn source.

## 6. Tài liệu sở hữu

- [Đặc tả API](../design/backtest-api-specification.md): trường, endpoint và lỗi HTTP.
- [Thiết kế hệ thống](../design/system-design.md): lớp xử lý, trạng thái và kho file.
- [Hợp đồng dữ liệu](../data/vn30f1m/data-contract-v1.md): thời gian, lịch và map hợp đồng.
- [Đặc tả giao diện](../design/web-ui-specification.md): trình bày dữ liệu của một run.
- [Checklist tích hợp](../plans/legacy-cleanup-checklist.md): công việc và bằng chứng nghiệm thu.
