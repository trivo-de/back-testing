# Data contract — CANSLIM v1 / VN30 futures

Cập nhật: 28/09/2026. U05 đã có bộ ánh xạ JSON, lịch phiên/map và báo khoảng
thiếu dữ liệu. U08 đã chạy v1 trên dữ liệu tổng hợp; chưa nghiệm thu dataset thật.
Các mục trống chưa được phép suy ra default. Không thay
[contract v0 hiện hành](data-contract.md) hoặc raw/version đã lưu.
Rule sử dụng dữ liệu tại [CANSLIM v1](../../strategies/canslim-v1-rules.md).

## 1. Dữ liệu yêu cầu

- Primary: OHLCV 5 phút của hợp đồng F1M thực tế tại ngày giao dịch.
- Map theo ngày từ nhãn VN30F1M sang mã hợp đồng thực.
- VNINDEX 5 phút có OHLCV để tính SMA/EMA/BB/MACD/MFI, tối thiểu 150 nến đã đóng tính cả t.
- Calendar/session, instrument metadata và margin/fee/tax policy có version.
- market_data VNINDEX bắt buộc cho v1; không dùng SMA200 của v0. Khối lượng MFI lấy từ dữ liệu VNINDEX đã cung cấp, không thay bằng khối lượng hợp đồng.

## 2. Identity, provenance và availability

- Pin dataset ID/version/hash, vendor, symbol nguồn, mã hợp đồng và timezone.
- Chỉ dùng nến đã khả dụng tại thời điểm quyết định.
- Thiếu warm-up → UNEVALUABLE; thiếu bar thực thi forced exit → INVALID.
- Khi đổi hợp đồng, giữ chuỗi chỉ báo VNINDEX; không nối giá hợp đồng cũ vào
  hợp đồng mới.

### Input cụ thể chưa chốt

- Vendor và đường dẫn/manifest intraday từng hợp đồng: không hard-code trong strategy; manifest bắt buộc có `vendor`, `source_symbol`, `contract_code`, `path`, `hash` cho từng mã thực.
- Timestamp Open/Close và available_at cho từng nguồn v1: `Asia/Ho_Chi_Minh`; bar 5 phút mang thời điểm bắt đầu, Close và `available_at = start + 5 phút`.
- Session/calendar version cho v1: lịch HNX theo năm; ATO 08:45–09:00, liên tục 09:00–11:30 và 13:00–14:30, ATC 14:30–14:45; lưu version/hash lịch nghỉ.
- Xử lý missing expected bars ngoài forced exit: không fill; đánh dấu `DATA_GAP`, ngừng đánh giá indicator phụ thuộc và chỉ resume sau khi đủ lại warm-up hợp lệ.
- Quy tắc đủ 150 mẫu tại biên kỳ: đủ 150 nến VNINDEX 5 phút hợp lệ đã đóng, tính cả nến t; được lấy lịch sử trước kỳ báo cáo. Ghép theo available_at, không theo số dòng hay lặp nến thị trường để đủ mẫu.

## 3. Lịch giao dịch

Giờ giao dịch dùng lịch Việt Nam cấu hình sẵn, múi giờ Asia/Ho_Chi_Minh;
không yêu cầu nhập lại mỗi request. Hợp đồng: ATO 08:45–09:00; liên tục
09:00–11:30 và 13:00–14:30; ATC 14:30–14:45; nghỉ cuối tuần/ngày nghỉ của sở.
[Hướng dẫn HSC](https://www.hsc.com.vn/vi/3-quy-dinh-giao-dich-hop-dong-tuong-lai-1).
VNINDEX dùng lịch và thời gian khả dụng của nguồn thị trường cơ sở, không
áp giờ ATO phái sinh cho VNINDEX. Không tạo nến giả để ghép hai nguồn.
Khung giờ entry v1 giữ nguyên; thiếu nến VNINDEX hợp lệ thì chưa xét entry.

## 4. Map đáo hạn và chuyển hợp đồng

Map đầu vào tại `trade_data.contract_map` trong [payload](../../../data/payload.json):
mỗi dòng có contract_code (mã thực), expiry_date (YYYY-MM-DD), expiry_unix
(Unix giây của ngày đáo hạn theo UTC+7). Dùng nguyên lịch năm 2026 người dùng
đã điền. expiry_unix biểu diễn ngày, không phải giá hoặc thời điểm khớp lệnh.
Kiểm tra ngày khớp timestamp, mã/ngày không trùng và thứ tự tăng dần.
Theo quy tắc chuyển kỳ bên dưới, ngày giao dịch sau đáo hạn trước đến hết
ngày đáo hạn hiện tại thuộc hợp đồng hiện tại; đầu/cuối khoảng chạy phải có
map bao phủ. Không đổi nguồn hoặc suy lịch từ OHLCV.

- Mã hợp đồng và ngày/giờ chuyển kỳ: internal dùng `VN30FYYMM`; hợp đồng tháng hiện tại giữ đến hết ngày giao dịch cuối cùng, chuyển sang tháng kế tiếp từ Open phiên giao dịch kế tiếp.
- Quy tắc đối chiếu với vendor: đối chiếu `trading_date + contract_code + vendor_symbol + expiry_date`; mismatch hoặc alias không rõ → fail validation.
- Policy xử lý thiếu map: `INVALID`; không suy ra F1M từ tên file, giá hoặc volume.
- Chuyển hợp đồng không làm mất warm-up VNINDEX; dữ liệu khớp lệnh vẫn phải đúng mã hợp đồng mới.

## 5. Instrument và policy metadata

Các giá trị sau là tham số mô phỏng đã nhận từ quyết định user, không phải
kết luận đã kiểm chứng quy định thị trường cho toàn kỳ lịch sử:

- Multiplier: 100.000; tiền tệ mô hình: VND.
- Tick mô phỏng: 0,1 điểm; quantity là số hợp đồng nguyên.
- Slippage: 0.

Margin/thuế/phí theo [accounting v1](../../design/canslim-v1-execution-accounting.md).

- Nguồn/version/ngày hiệu lực instrument metadata: mẫu hợp đồng HNX + danh mục/tỷ lệ ký quỹ VSDC; lưu ngày hiệu lực, thời điểm tải và hash.
- Price limit và cách xử lý nếu mô phỏng: ±7% giá tham chiếu; raw vượt biên → `INVALID`. Không clamp stop/target; mức ngoài biên chỉ không thể khớp trong ngày đó.
- Bộ dữ liệu đủ điều kiện chạy v1: đủ map mã thực, 150 nến VNINDEX khởi tạo, calendar, metadata và tỷ lệ ký quỹ cố định 17%; không có gap trong bar quyết định/thực thi.

## 6. Evidence

U05 dùng `runtime-policy-v1.json`: giữ lịch ngày/ngày nghỉ từ cấu hình đã có,
không lấy rule rollover v0. Phiên liên tục là các nhãn bắt buộc; nhãn ATO/ATC
được liệt kê riêng trong optional_times. Không tạo nến để lấp khoảng trống.
Map tháng phải liên tiếp; dòng đầu phủ từ đầu tháng đáo hạn, các dòng sau
phủ sau ngày đáo hạn trước đến hết ngày đáo hạn hiện tại. Muốn lấy lịch sử
trước tháng đầu phải cung cấp thêm map. Nguồn giao dịch có map dùng múi giờ
Asia/Ho_Chi_Minh theo hợp đồng này.

Close và available_at được giữ riêng. Engine nhận đầy đủ OHLCV của thị trường
nhưng chỉ công bố nến khi available_at <= thời điểm xét; không lặp mẫu.
Khoảng thiếu nến được báo trong data_gaps và đánh dấu data_gap_before tại nến
quan sát tiếp theo. Việc đợi đủ lại 150 mẫu thuộc U08.
Chuỗi giao dịch công bố trễ sau Close hiện bị từ chối chạy với
PRIMARY_AVAILABILITY_DELAY_UNSUPPORTED; không tự sửa available_at về Close.
Nến trước report chỉ cung cấp lịch sử, nến sau end_date không đi vào engine.
Không rút ngắn kỳ báo cáo sáu tháng.

- Validation schema/hash/session/coverage: lưu báo cáo kiểm tra schema, hash file, số bar kỳ vọng/thực tế, gap và coverage theo từng hợp đồng.
- Kiểm tra chuyển hợp đồng: giữ lịch sử chỉ báo VNINDEX, chọn đúng dữ liệu hợp đồng để khớp; không dùng nến tương lai.
- Nghiệm thu dữ liệu thật: toàn kỳ yêu cầu chạy lại cho cùng kết quả, không thiếu lịch chuyển hợp đồng/chính sách và không thiếu nến bắt buộc để khớp lệnh.
