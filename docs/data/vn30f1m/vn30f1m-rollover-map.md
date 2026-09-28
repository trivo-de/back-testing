# VN30F1M — Static Rollover Map (03/2026–09/2026)

Quy tắc lịch đáo hạn:

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

Theo rule mục 4 (Rollover — buộc đóng vị thế trước đáo hạn): nếu đang giữ vị
thế và phiên hiện tại rơi đúng ngày đáo hạn của hợp đồng đang nắm giữ, đóng
toàn bộ vị thế tại Open phiên đáo hạn (cùng cơ chế khớp + slippage đã có),
bất kể STOP_LOSS/TAKE_PROFIT đã đạt hay chưa. v0 không roll sang hợp đồng
tháng kế tiếp — luôn về flat qua mỗi lần đáo hạn.
