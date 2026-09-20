# VN30F1M — Static Rollover Map (03/2026–09/2026)

Đáo hạn = thứ Năm tuần thứ 3 của tháng hợp đồng. Đã kiểm chéo lịch nghỉ lễ
Việt Nam 2026 (Giỗ Tổ 26/4 Chủ nhật, nghỉ bù 27/4; 30/4 Thứ Năm; 1/5 Thứ Sáu) —
không ngày nào trùng các thứ Năm tuần 3 dưới đây, nên không cần dời lịch.

| Tháng hợp đồng | Mã tham khảo* | Ngày đáo hạn | Thứ | Unix (00:00 UTC) |
|---|---|---|---|---|
| 3/2026 | VN30F2603 | 19/03/2026 | Thứ Năm | 1773878400 |
| 4/2026 | VN30F2604 | 16/04/2026 | Thứ Năm | 1776297600 |
| 5/2026 | VN30F2605 | 21/05/2026 | Thứ Năm | 1779321600 |
| 6/2026 | VN30F2606 | 18/06/2026 | Thứ Năm | 1781740800 |
| 7/2026 | VN30F2607 | 16/07/2026 | Thứ Năm | 1784160000 |
| 8/2026 | VN30F2608 | 20/08/2026 | Thứ Năm | 1787184000 |
| 9/2026 | VN30F2609 | 17/09/2026 | Thứ Năm | 1789603200 |

## Cách dùng

**Xác nhận user 18/09/2026:** cho phép dùng lịch/mã tham khảo trong bảng làm
assumption mô phỏng, dù chưa verify rollover thật của dchart. Chốt **giữ vị thế
và pending order qua đáo hạn/rollover**, không forced SELL hoặc tự đưa về flat.
Entry/exit tiếp tục theo CANSLIM và Open bar hợp lệ kế tiếp. Giá raw giữ nguyên,
không chỉnh basis, thêm multiplier/margin/settlement hoặc mô phỏng roll trade.

Runtime policy dùng nhãn tháng hiện hành đến hết ngày đáo hạn inclusive và nhãn
tháng kế tiếp từ ngày sau đó; đây là mapping tham khảo tĩnh để kiểm tra coverage,
không phải bằng chứng actual contract identity. Quyết định giữ vị thế trên chuỗi
giá nguồn là giới hạn rõ của normalized simulation.

## Chưa xác nhận — cần làm trước khi tin tưởng map này

- **Mã hợp đồng (`VN30FYYMM`)** là naming truyền thống, dùng để tham khảo/tra
  cứu chéo. Sau khi HOSE/HNX chuyển hệ thống giao dịch sang KRX (2025), có
  nguồn nhắc một dạng mã khác — chưa xác nhận đây có còn là naming chính thức
  hiện hành hay không. Không hard-code mã này vào pipeline nếu chưa đối chiếu
  lại với nguồn giao dịch thật.
- **Chưa verify rollover thật trên data:** đây là lịch lý thuyết (quy tắc thứ
  Năm tuần 3), chưa đối chiếu xem symbol `VN30F1M` trên dchart-api có thực sự
  chuyển sang hợp đồng tháng sau đúng phiên kế tiếp sau mỗi ngày đáo hạn hay
  không. Cách kiểm: so Close của VN30F1M với VN30 spot cùng ngày quanh mỗi mốc
  đáo hạn — nếu có bước nhảy basis bất thường đúng ngày chuyển tháng, xác nhận
  được cơ chế rollover của nguồn data.
