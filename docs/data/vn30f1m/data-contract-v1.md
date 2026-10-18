# Dữ liệu cho mẫu CANSLIM v1

Nếu bật `hnx_sessions_v1`, bổ sung mã hợp đồng thực tế theo ngày, nguồn dữ liệu
và bản ghi ATC riêng theo [hợp đồng khớp theo phiên](../../design/hnx-session-matching.md).
Nến nhãn `14:45` không được tự chuyển thành giá ATC. Mẫu CANSLIM mặc định không
tự bật chế độ này hoặc thay đổi chuỗi chỉ báo.

Tài liệu này bổ sung [hợp đồng dữ liệu JSON](data-contract.md) cho
[mẫu CANSLIM v1](../../strategies/canslim-v1-rules.md), không tạo bộ kiểm tra
hoặc nguồn dữ liệu riêng.

## 1. Hai chuỗi dữ liệu

- `trade_data`: OHLCV VN30F1M 5 phút, dùng khớp lệnh, stop/target/trailing và P/L.
- `market_data`: OHLCV VNINDEX 5 phút, dùng SMA20, EMA5, BB, MACD và MFI14.
  Volume của MFI lấy từ VNINDEX, không thay bằng volume hợp đồng.
- Cần tối thiểu 150 nến VNINDEX đã khả dụng tại lần xét entry, tính cả nến
  hiện tại. Có thể cung cấp lịch sử trước report; không dùng nến tương lai.
- Bộ chỉ báo của mô hình contract dùng các nến mở trong khoảng liên tục
  09:00–11:30 và 13:00–14:30; record ngoài khoảng này vẫn có thể được giữ
  trong dữ liệu nguồn, không đưa vào chuỗi tính chỉ báo 5 phút của mô hình này.

## 2. Phiên và mã hợp đồng

`runtime-policy-v1.json` quy định ngày và nhãn giờ của hai nguồn.
Khi gửi contract_map, kiểm tra cả hai nguồn 5 phút theo chính sách này.
Nhãn ATO/ATC của trade_data là tùy chọn. Market_data dùng lưới riêng, trong đó
14:30 và 14:45 vẫn là nhãn bắt buộc của nguồn; không áp giờ ATO hợp đồng
cho VNINDEX. Nến thiếu được báo và chuỗi chỉ báo liên quan phải
khởi tạo lại; thiếu nến thực thi bắt buộc không được thay bằng giá giả.

`trade_data.contract_map` gồm `contract_code`, `expiry_date`,
`expiry_unix`. Unix biểu diễn ngày đáo hạn theo múi giờ nguồn, không phải
thời điểm khớp. Bảng cần phủ cả lịch sử và kỳ báo cáo, các tháng liên tiếp.
[Bảng tham khảo](vn30f1m-rollover-map.md) là nguồn map khi tự lấy dữ liệu.

Đổi hợp đồng không khởi tạo lại chuỗi VNINDEX. Source hiện gắn mã theo bảng,
chưa đối chiếu vendor_symbol hoặc kiểm tra giá với dữ liệu từng hợp đồng.
Không suy mã hợp đồng từ giá.

## 3. Giá, tiền và khả dụng

- Giá giữ đơn vị điểm, không nhân hệ số hợp đồng vào OHLC/chỉ báo.
- Mẫu dùng hệ số 100.000, tick mô phỏng 0,1 điểm, slippage 0.
- Mẫu truyền margin_rate 0,17 cùng phí/thuế trong JSON. Đây là cấu hình mô phỏng,
  không xác nhận tỷ lệ thực tế của mọi ngày lịch sử.
- Close/available_at mặc định bằng Open + 5 phút; chuỗi giao dịch công bố
  trễ hơn Close bị từ chối `PRIMARY_AVAILABILITY_DELAY_UNSUPPORTED`.
- Chuỗi tham chiếu chỉ được đọc sau available_at. Không lặp một nến VNINDEX
  thành nhiều mẫu khi ghép với nến giao dịch.
- Chưa kiểm tra biên độ giá hoặc quyết toán qua đêm bằng DSP/FSP.

Công thức và thứ tự xử lý tại [tính tiền hợp đồng](../../design/canslim-v1-execution-accounting.md).

## 4. Ranh giới kiểm chứng

Các test tổng hợp đã có tại [danh mục kiểm thử](../../testing/vn30f1m/canslim-v1-test-cases.md),
gồm khả dụng, khoảng thiếu, chuyển mã, khởi tạo chỉ báo và lỗi thiếu nến thoát.

Nghiệm thu dữ liệu thật sáu tháng chưa được xác nhận. Việc nhập được JSON,
có bảng tham khảo hoặc nhận STRUCTURE_VALID không tự chứng minh đủ lịch sử,
đúng mã hợp đồng thực tế hoặc đủ nến để hoàn tất mọi lệnh.
