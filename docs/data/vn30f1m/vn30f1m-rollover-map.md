# VN30F1M — Bảng đáo hạn tham khảo năm 2026

- Các ngày dưới đây là bảng tham khảo người dùng cung cấp, được lưu trong `runtime-policy.json`.
- Khi tự lấy dữ liệu hợp đồng, service chuyển các dòng `rollover` thành `trade_data.contract_map`.
- Mã `VN30FYYMM` là nhãn tháng của mô hình; việc gắn nhãn không xác minh dữ liệu từng hợp đồng với vendor.

Quy ước lịch:

- Định kỳ: Thứ Năm tuần thứ ba của tháng đáo hạn.
- Thay đổi: Dịch sớm hơn nếu trùng ngày nghỉ lễ.
- Chuyển đổi: Mã F1M đổi sang tháng mới sau ngày này.

| Tháng | Ngày đáo hạn | Unix timestamp (UTC+7) |
| ------ | ---------------: | ---------------------: |
| 1      |       15/01/2026 |         `1768410000` |
| 2      |       13/02/2026 |         `1770915600` |
| 3      |       19/03/2026 |         `1773853200` |
| 4      |       16/04/2026 |         `1776272400` |
| 5      |       21/05/2026 |         `1779296400` |
| 6      |       18/06/2026 |         `1781715600` |
| 7      |       16/07/2026 |         `1784134800` |
| 8      |       20/08/2026 |         `1787158800` |
| 9      |       17/09/2026 |         `1789578000` |
| 10     |       15/10/2026 |         `1791997200` |
| 11     |       19/11/2026 |         `1795021200` |
| 12     |       17/12/2026 |         `1797440400` |

## Cách dùng

Unix là giây tại 00:00:00 `Asia/Ho_Chi_Minh` của ngày đáo hạn, không phải
thời điểm khớp. Bảng hiện kết thúc 17/12/2026; kỳ và lịch sử phải được map phủ.

- Luồng JSON chỉ dùng bảng để gắn mã hợp đồng và kiểm tra độ phủ.
- Không tự đóng vị thế tại Open ngày đáo hạn từ trường `rollover_action` trong chính sách.
- Điều kiện đóng vị thế phải được khai báo trong JSON; mẫu CANSLIM v1 đóng cuối ngày theo quy tắc riêng.
- Chi tiết tại [hợp đồng dữ liệu](data-contract.md).
