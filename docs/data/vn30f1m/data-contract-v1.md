# Data contract — CANSLIM v1 / VN30 futures

Cập nhật: 25/09/2026. Đặc tả một phần, chưa nghiệm thu dataset v1.
Các mục trống chưa được phép suy ra default. Không thay
[contract v0 hiện hành](data-contract.md) hoặc raw/version đã lưu.
Rule sử dụng dữ liệu tại [CANSLIM v1](../../strategies/canslim-v1-rules.md).

## 1. Dữ liệu yêu cầu

- Primary: OHLCV 5 phút của hợp đồng F1M thực tế tại ngày giao dịch.
- Daily pivot: OHLC phiên giao dịch trước của cùng hợp đồng.
- Map theo ngày từ nhãn VN30F1M sang mã hợp đồng thực.
- VNINDEX 5 phút có OHLCV để tính SMA/EMA/BB/MACD/MFI, tối thiểu 150 nến đã đóng tính cả t.
- Calendar/session, instrument metadata và margin/fee/tax policy có version.
- market_data VNINDEX bắt buộc cho v1; không dùng SMA200 của v0. Khối lượng MFI lấy từ dữ liệu VNINDEX đã cung cấp, không thay bằng khối lượng hợp đồng.

## 2. Identity, provenance và availability

- Pin dataset ID/version/hash, vendor, symbol nguồn, mã hợp đồng và timezone.
- Chỉ dùng bar/daily data đã available tại decision; không dùng daily của phiên
  đang chạy để tạo pivot phiên đó.
- Thiếu warm-up → UNEVALUABLE; thiếu bar thực thi forced exit → INVALID.
- Khi đổi hợp đồng, giữ chuỗi chỉ báo VNINDEX; không nối giá hợp đồng cũ vào
  hợp đồng mới. Pivot vẫn lấy daily đúng mã hợp đồng đang giao dịch.

### Input cụ thể chưa chốt

- Vendor và đường dẫn/manifest intraday từng hợp đồng: không hard-code trong strategy; manifest bắt buộc có `vendor`, `source_symbol`, `contract_code`, `path`, `hash` cho từng mã thực.
- Vendor và đường dẫn/manifest daily: dùng daily trực tiếp của cùng vendor nếu có; manifest bắt buộc nối theo `contract_code + trading_date` và lưu `path/hash`.
- Timestamp Open/Close và available_at cho từng nguồn v1: `Asia/Ho_Chi_Minh`; bar 5 phút mang thời điểm bắt đầu, Close và `available_at = start + 5 phút`; daily chỉ available sau khi phiên kết thúc.
- Session/calendar version cho v1: lịch HNX theo năm; ATO 08:45–09:00, liên tục 09:00–11:30 và 13:00–14:30, ATC 14:30–14:45; lưu version/hash lịch nghỉ.
- Xử lý missing expected bars ngoài forced exit: không fill; đánh dấu `DATA_GAP`, ngừng đánh giá indicator phụ thuộc và chỉ resume sau khi đủ lại warm-up hợp lệ.
- Quy tắc đủ 150 mẫu tại biên kỳ: đủ 150 nến VNINDEX 5 phút hợp lệ đã đóng, tính cả nến t; được lấy lịch sử trước kỳ báo cáo. Ghép theo available_at, không theo số dòng hay lặp nến thị trường để đủ mẫu.

## 3. Daily pivot

Giờ giao dịch dùng lịch Việt Nam cấu hình sẵn, múi giờ Asia/Ho_Chi_Minh;
không yêu cầu nhập lại mỗi request. Hợp đồng: ATO 08:45–09:00; liên tục
09:00–11:30 và 13:00–14:30; ATC 14:30–14:45; nghỉ cuối tuần/ngày nghỉ của sở.
[Hướng dẫn HSC](https://www.hsc.com.vn/vi/3-quy-dinh-giao-dich-hop-dong-tuong-lai-1).
VNINDEX dùng lịch và thời gian khả dụng của nguồn thị trường cơ sở, không
áp giờ ATO phái sinh cho VNINDEX. Không tạo nến giả để ghép hai nguồn.
Khung giờ entry v1 giữ nguyên; thiếu nến VNINDEX hợp lệ thì chưa xét entry.

Ưu tiên daily OHLC chính thức/cùng vendor với 5m. User cho phép aggregate 5m
thành daily sau khi quy định đầy đủ semantics trong contract này.
Chưa có các quyết định dưới đây thì chưa aggregate.

- Chọn daily trực tiếp hay aggregate: chọn daily trực tiếp; v1 không tự aggregate 5 phút khi chạy production.
- Timezone/session boundary: `Asia/Ho_Chi_Minh`; một daily record thuộc đúng một ngày giao dịch HNX, không gộp qua nghỉ trưa hay sang ngày kế tiếp.
- Record ATO/ATC bao gồm/loại trừ: daily giữ ATO/ATC theo dữ liệu chính thức/vendor; record đấu giá không được giả thành nến 5 phút liên tục.
- Công thức Open/High/Low/Close/Volume: lấy nguyên OHLCV daily từ nguồn; không tính lại. Nếu sau này aggregate thì Open=khớp đầu, High=max, Low=min, Close=khớp cuối, Volume=sum toàn phiên.
- Phiên thiếu/incomplete: không tạo pivot từ phiên thiếu; phiên kế tiếp `UNEVALUABLE` cho rule cần pivot.
- Thời điểm daily available: sau 14:45 và sau thời điểm vendor công bố record; strategy chỉ dùng record này từ phiên giao dịch kế tiếp.
- Version/provenance nối daily với intraday: cùng `dataset_version`, `vendor`, `contract_code`, `trading_date`; khác nguồn thì phải lưu mapping và hash riêng.
- Pivot khi phiên trước là ngày trước khi hợp đồng trở thành F1M: được dùng nếu là cùng mã hợp đồng thực và record đã available; không yêu cầu ngày đó hợp đồng đã mang nhãn F1M.

## 4. Map đáo hạn và chuyển hợp đồng

Map tham khảo hiện có: [vn30f1m-rollover-map.md](vn30f1m-rollover-map.md),
bản máy đọc trong [runtime-policy.json](runtime-policy.json).
Đây là nguồn tham khảo v0, chưa xác nhận là actual-contract mapping cho v1.
V1 không giữ vị thế qua đêm; map vẫn cần để chọn đúng contract và history.

- Nguồn map thực tế: lịch đáo hạn HNX + danh mục hợp đồng VSDC; đóng thành map versioned theo ngày giao dịch.
- Mã hợp đồng và ngày/giờ chuyển kỳ: internal dùng `VN30FYYMM`; hợp đồng tháng hiện tại giữ đến hết ngày giao dịch cuối cùng, chuyển sang tháng kế tiếp từ Open phiên giao dịch kế tiếp.
- Quy tắc đối chiếu với vendor: đối chiếu `trading_date + contract_code + vendor_symbol + expiry_date`; mismatch hoặc alias không rõ → fail validation.
- Policy xử lý thiếu map: `INVALID`; không suy ra F1M từ tên file, giá hoặc volume.
- Chuyển hợp đồng không làm mất warm-up VNINDEX; vẫn cần daily phiên trước đúng mã để tạo pivot cho hợp đồng mới.

## 5. Instrument và policy metadata

Các giá trị sau là tham số mô phỏng đã nhận từ quyết định user, không phải
kết luận đã kiểm chứng quy định thị trường cho toàn kỳ lịch sử:

- Multiplier: 100.000; tiền tệ mô hình: VND.
- Tick mô phỏng: 0,1 điểm; quantity là số hợp đồng nguyên.
- Slippage: 0.

Margin/thuế/phí theo [accounting v1](../../design/canslim-v1-execution-accounting.md).

- Nguồn/version/ngày hiệu lực instrument metadata: mẫu hợp đồng HNX + danh mục/tỷ lệ ký quỹ VSDC; lưu ngày hiệu lực, thời điểm tải và hash.
- Price limit và cách xử lý nếu mô phỏng: ±7% giá tham chiếu; raw vượt biên → `INVALID`. Không clamp stop/target; mức ngoài biên chỉ không thể khớp trong ngày đó.
- Bộ dữ liệu đủ điều kiện chạy v1: đủ map mã thực, 150 bar warm-up, daily phiên trước, calendar, metadata và tỷ lệ ký quỹ cố định 17%; không có gap trong bar quyết định/thực thi.

## 6. Evidence

- Validation schema/hash/session/coverage: lưu báo cáo kiểm tra schema, hash file, số bar kỳ vọng/thực tế, gap và coverage theo từng hợp đồng.
- Daily availability và rollover/warm-up: test riêng boundary đáo hạn; daily không look-ahead và VNINDEX có đủ 150 nến và pivot lấy đúng hợp đồng mới.
- Nghiệm thu dữ liệu thật: toàn kỳ yêu cầu chạy lại cho cùng kết quả, không thiếu lịch chuyển hợp đồng/chính sách và không thiếu nến bắt buộc để khớp lệnh.
