# Khớp lệnh theo phiên HNX trên nến 5 phút

API hiện tại theo [hợp đồng khớp ngay hoặc LO, một vị thế và điểm](price-only-contract.md),
đã triển khai B–D. POST/validate chỉ nhận cấu hình, máy chủ luôn lấy dữ liệu; kết quả mới là schema 3.
[Kiểm chứng C–D](../testing/price-only-cd.md) ghi phạm vi đã kiểm tra. Lịch sử cũ vẫn đọc theo đơn vị gốc.

**Các mục bên dưới là tài liệu đường cũ để đối chiếu lịch sử**, không phải cấu trúc POST
đang được chấp nhận. Việc dọn đầy đủ tài liệu và mã cũ thuộc phần F.

`hnx_sessions_v1` mô phỏng ATO mở, LO liên tục và ATC đóng trên OHLC. `execution.auction_match_quantity` giới hạn lượng khớp từng lệnh đấu giá.

MTL/MOK/MAK và LO khớp nhiều lần với ngân sách đối ứng cố định được mô tả
riêng ở [mục 7](#7-đặc-tả-mtlmokmak--a01); phải bật cấu hình mới để sử dụng.

Mục 6 ghi yêu cầu ATO/ATC chốt ngày 14/10/2026 và trạng thái kiểm thử từng phần.

## 1. Bật chế độ

- Khai báo lệnh tại `strategy.entry.order` hoặc `strategy.entry.actions.<nhãn>.order`; nhóm đóng dùng `exit.bar_close` tương tự.
- Ví dụ: LO `{"type":"LO","limit_price":{"ref":"trade_data.close"}}`, ATO `{"type":"ATO"}`, ATC `{"type":"ATC"}`.
- Chọn `execution.matching_model: "hnx_sessions_v1"`.
- Cấu hình cũ vẫn được đọc; cũ/mới mâu thuẫn bị từ chối. Xem [hướng dẫn cách khớp hiện tại](strategy-payload-guide.md#5-cách-khớp-lệnh).

- `sizing.pyramiding: true`: xử lý nhiều nhánh LO/ATO theo `entry.priority`.
- Hạn mức gồm lượng đang giữ và mở đang chờ. Mỗi lần mở có giá vốn và bảo vệ riêng.
- `remaining` đóng phần đang xét; bảo vệ hủy lệnh đóng chờ cùng `position_id`.
- `next_open` và lệnh mở `SIMULATED` dùng chế độ một vị thế.

Thứ tự mỗi nến khi có nhiều phần vị thế:

1. Khớp lệnh chờ tại Open, rồi xử lý bảo vệ tại Open.
2. Ghi LO chạm giá tại Close, rồi xử lý bảo vệ trong nến.
3. Cập nhật trailing sau Close.

- Cùng thời điểm: theo thứ tự gửi lệnh và phần vị thế.
- Lệnh đóng tại Open ưu tiên trước bảo vệ cùng Open. TP đạt tại Open được giữ dù nến chạm stop sau đó.
- Một vị thế giữ thứ tự bảo vệ cũ. Các giả định được ghi trong metadata vì OHLC chỉ cho biết các mức giá của nến.

Giữ `accounting.model: "contract"`, `trade_data.resolution: "5"`,
`trade_data.timezone: "Asia/Ho_Chi_Minh"`. Nhập dữ liệu thì dùng
`auto_fetch_data: false`; khớp liên tục cũng hỗ trợ `auto_fetch_data: true`.
Khai báo:

```json
{
  "execution": {
    "matching_model": "hnx_sessions_v1",
    "entry_fill_policy": "limit",
    "auction_match_quantity": 2,
    "slippage_rate": 0
  }
}
```

`auction_match_quantity` là số nguyên không âm, dùng khi có ATO/ATC:

- Bỏ trường: giả định khớp đủ.
- Đặt `2`: tối đa 2 hợp đồng mỗi lệnh đấu giá.
- Đặt `0`: thử trường hợp hết hiệu lực mà chưa khớp.
- Giá trị được ghim cùng đầu vào và metadata.

- Bỏ `matching_model`: giữ bộ khớp cũ. Chế độ HNX áp dụng cho contract.
- Nhập tay: cung cấp nguồn và mã hợp đồng theo ngày.
- Tự lấy: tải VN30F1M/VNINDEX 5 phút, tạo `contract_dates` với giả định chuyển mã sau ngày đáo hạn. Giả định và nguồn được lưu cùng lượt chạy.
- Lịch chuyển mã cần đối chiếu riêng với nhà cung cấp; lịch phiên và độ phủ bảng hợp đồng vẫn được kiểm tra.
- Mô hình tiền, trượt giá, ngưỡng và giờ thoát lấy từ cấu hình chiến lược.

- Web hỗ trợ tự lấy khi chọn HNX.
- `/validate` trả payload đầy đủ với `auto_fetch_data: false` để chạy đúng dữ liệu đã kiểm tra.
- ATO/ATC cần bản ghi nhãn 09:00/14:45 tương ứng; thiếu bản ghi làm lượt chạy lỗi.

ATO theo cấu hình cũ dùng `execution.entry_fill_policy: "ato"`:

1. Xét điều kiện lúc 08:45 bằng dữ liệu đã hoàn tất.
2. Chốt lượng theo Close liên tục gần nhất; cần lịch sử trước ngày vào lệnh.
3. Kiểm tra ký quỹ tại Open 09:00 rồi khớp.

- LO mở theo cấu hình cũ dùng `strategy.entry.limit_price`, ví dụ `{"ref":"trade_data.close"}` hoặc `{"sub":[{"ref":"trade_data.close"},0.5]}`.
- Chốt giá và lượng tại thời điểm tín hiệu. Giá giới hạn phải dương, đúng bước 0,1 điểm.
- `next_open` vẫn tính lượng tại Open thực thi.

LO đóng dùng `strategy.exit.bar_close.fill_policy: "limit"` cùng `limit_price`;
khối lượng là `remaining`, được chốt khi gửi lệnh. Nếu stop/target làm thay đổi vị thế
trước khi LO đóng khớp, LO còn chờ bị hủy với lý do `POSITION_CHANGED`.

## 2. Phiên, thời hạn và giá khớp

| Giờ địa phương | Phiên                                   |
| ------------------- | ---------------------------------------- |
| 08:45–09:00        | ATO mở vị thế; engine gửi lúc 08:45, khớp lúc 09:00 |
| 09:00–11:30        | Liên tục buổi sáng                   |
| 11:30–13:00        | Nghỉ trưa                              |
| 13:00–14:30        | Liên tục buổi chiều                  |
| 14:30–14:45        | ATC; chỉ đóng vị thế, khớp lúc 14:45 |

LO mua khớp tại Open nếu Open ≤ giá giới hạn; nếu không, Low chạm giới hạn thì
khớp tại giới hạn. LO bán áp dụng đối xứng bằng Open/High. Đóng LONG là bán,
đóng SHORT là mua. Không dùng volume cuối nến để quyết định khớp tại Open.

- `strategy.entry.pending.max_execution_bars` là số nguyên ≥ 1, mặc định 1, quy định số nến chờ LO.
- `cross_lunch`, `cross_cutoff`, `cross_session` chỉ nhận `false`.
- LO hết số nến chờ chuyển `expired`; hủy khi đến nghỉ trưa, ATC hoặc hạn mở.
- Hủy tại ranh giới là chính sách gửi lệnh đã khai báo, xử lý trước khi chuyển phiên.

- LO mở tại Open dùng thứ tự stop/target hiện có.
- LO chạm trong nến: ghi khớp tại Close, `bar_time` là Open của nến chứa khớp.
- Stop có thể đóng ngay nến mở; target xét từ nến kế tiếp.
- Giả định bảo thủ có thể ghi stop dù mức stop xuất hiện trước lúc mở trong thực tế. Giả định được lưu cùng kết quả.

- LO tính lượng theo rủi ro/ký quỹ tại giá giới hạn; ATO dùng Close liên tục đã khả dụng trước 08:45.
- Khi khớp, kiểm tra ký quỹ sau phí tại giá thực hiện. Thiếu tiền thì từ chối toàn bộ lượng định khớp.
- ATC đóng một phần và `allow_overnight: false`: trả `END_OF_DAY_POSITION_REQUIRES_EXIT`.
- Bỏ cờ này: kết quả giữ phần vị thế còn lại.

## 3. Dữ liệu bổ sung bắt buộc

- `trade_data.contract_dates`: tăng dần, một mã mỗi ngày, phủ lịch sử khởi tạo và kỳ báo cáo.
- Nhập tay: dùng ánh xạ từ nguồn hoặc giả định đã được đồng ý.
- Tự lấy: tạo theo bảng đáo hạn ở mục 1, trong phạm vi dữ liệu đến cuối kỳ. Đây là giả định chuyển mã của mô hình.

- ATO lấy `open` bản ghi nhãn 09:00; ATC lấy `close` bản ghi nhãn 14:45 trong `trade_data.bars`.
- Giá phải dương, đúng bước 0,1 điểm.
- Nhập tay phải có `contract_dates` và `provenance`. Thiếu bản ghi cần khớp, sai ngày hoặc mã làm lượt chạy lỗi.

- Trường `trade_data.auctions` cũ vẫn được đọc để chạy lại input ATC đã lưu trước thay đổi này.
- Lượt chạy mới ưu tiên bản ghi OHLCV 14:45 khi cả hai cùng tồn tại.
- Bản ghi cũ vẫn phải có `match_time` 14:45, `available_at`, `status`, `price` và `source` hợp lệ như hợp đồng trước đây.

- Lịch từ `runtime-policy-v1.json` được ghim cùng đầu vào; hai nguồn dùng lịch riêng.
- Bản ghi ATO/ATC được tách khỏi chuỗi chỉ báo và quyết định.
- Dữ liệu khớp bắt buộc bị thiếu làm lượt chạy lỗi. Giá thanh toán hằng ngày và đáo hạn thuộc phạm vi kiểm chứng riêng.

## 4. Đóng ATC và kết quả

Khai báo `strategy.exit.bar_close.fill_policy: "atc"`, `quantity: "remaining"`.
Điều kiện đóng chỉ phát lệnh tại Close nến cuối liên tục lúc 14:30. Ví dụ:

```json
{
  "conditions":{"CLOSE_ATC":{"gte":[{"ref":"clock.local_time"},"14:30"]}},
  "any":["CLOSE_ATC"],
  "priority":["CLOSE_ATC"],
  "quantity":"remaining",
  "fill_policy":"atc"
}
```

- Điều kiện gửi lệnh dùng dữ liệu khả dụng trước ATC.
- Nếu có `flat_by`, giờ phải từ 14:45 trở đi.
- Dùng ATC trong một cấu hình riêng; mẫu CANSLIM giữ giờ thoát đã chốt.

- Thiếu bản ghi: `MISSING_ATO_MATCH_BAR` hoặc `MISSING_ATC_MATCH_BAR`.
- Lượng khớp 0: lệnh hết hiệu lực. Còn vị thế cuối ngày với `allow_overnight: false`: `END_OF_DAY_POSITION_REQUIRES_EXIT`.
- Lệnh ATO/ATC dùng thời hạn phiên cố định. Giá đấu giá được tách khỏi chỉ báo.
- Thời điểm khớp: nhãn 09:00/14:45. `available_at` của fill ATO là 09:00; ATC theo thời điểm khả dụng của bản ghi.

- Kết quả dùng `schema_version: 2`; metadata thêm `matching_model`, `matching_rules_version`, nguồn và giả định.
- Lệnh ghi loại, lượng đặt/khớp/hết hiệu lực/còn chờ, giá giới hạn, thời điểm gửi/kết thúc và `events`.
- Trạng thái cuối: `filled`, `rejected`, `canceled`, `expired`. Sự kiện gồm `submitted`, có thể có `partially_filled`, rồi trạng thái cuối.
- Lệnh khớp một phần có thể kết thúc `expired` và vẫn liên kết fill. Chỉ lượng đã khớp phát sinh phí.
- Fill thêm `phase`, `order_type`, `time_precision`; ATO/ATC thêm nguồn và `available_at`. ID tín hiệu/lệnh/fill được lưu và kiểm tra.

- Kho file lưu toàn bộ dữ liệu nến, nguồn, lịch và cấu hình trong snapshot có dấu kiểm.
- Web tải các trường này cùng dữ liệu giao dịch, hiển thị loại lệnh, khối lượng đặt/khớp/hết hiệu lực/còn chờ và thời điểm kết thúc.
- Biểu đồ dùng Open 09:00 hoặc Close 14:45 để kiểm tra vị trí mũi tên; bản ghi ATC cũ vẫn dùng điểm trắng và đường giá riêng, không tạo nến OHLC giả.

## 5. Kiểm chứng

Kiểm thử tổng hợp:

- `tests/test_session_matching.py`: phiên, ATO/ATC khớp đủ/một phần/0; LO mở/đóng, thời hạn và hủy lệnh.
- Cùng file kiểm tra stop/target, chốt lượng, ký quỹ, dữ liệu thiếu/sai mã, dữ liệu tương lai, API và lưu/đọc.
- `tests/web/backtest-input.test.mjs`, `backtest-chart.test.mjs`: giữ bản ghi ATO/ATC khi tải JSON và đặt mũi tên biểu đồ.

Giá đấu giá thực tế và lịch chuyển mã của nhà cung cấp cần nghiệm thu riêng trên dữ liệu thị trường.

Trạng thái triển khai và nghiệm thu:

- [X] Chế độ bật riêng, giữ payload cũ và mẫu CANSLIM hiện tại.
- [X] Phiên, LO, khối lượng chốt trước, thời hạn/hủy và xử lý stop/target bảo thủ.
- [X] ATO từ Open 09:00 và ATC từ Close 14:45; vẫn đọc bản ghi ATC riêng cũ.
- [X] Cơ chế khớp một phần bằng giới hạn cố định, phần dư hết hiệu lực sau đấu giá.
- [X] API, lưu/tải lại dữ liệu có dấu kiểm, bảng lệnh và biểu đồ.
- [X] Kiểm thử tổng hợp, hồi quy và bộ chuyển dữ liệu biểu đồ ATO/ATC.
- [ ] Cung cấp giá ATC thật, xác nhận timestamp và lịch chuyển hợp đồng.
- [ ] Nghiệm thu trên bộ dữ liệu thị trường đã xác nhận.

## 6. Checklist mở rộng ATO/ATC, khớp một phần và thanh khoản

Ngày chốt yêu cầu: 14/10/2026. Dấu `[X]` chỉ phần đã có mã nguồn và kiểm thử
tổng hợp; dấu `[ ]` tiếp tục là công việc chưa hoàn thành hoặc chưa nghiệm thu.

### 6.1. Yêu cầu đã chốt

- ATO lấy Open bản ghi nhãn 09:00; ATC lấy Close bản ghi nhãn 14:45.
  Đây là quy ước giá mô phỏng của project, không yêu cầu bảng giá đấu giá riêng.
- Lệnh ATO phải được gửi trong phiên 08:45–09:00 trước thời điểm khớp 09:00;
  ATC gửi trong phiên 14:30–14:45 trước thời điểm khớp 14:45.
- Sau khi lệnh ATO/ATC được ghi nhận hợp lệ, không cho bên gửi sửa hoặc hủy lệnh.
- Tại lần khớp định kỳ, lệnh có thể khớp đủ, khớp một phần hoặc không khớp.
  Kết thúc đợt đấu giá, tự loại toàn bộ lượng chưa khớp khỏi danh sách chờ.
- “Xóa lệnh/phần dư” là chấm dứt hiệu lực phần chưa khớp, không xóa lịch sử lệnh,
  sự kiện hoặc phần đã khớp. Hết hiệu lực tự động khác với bên gửi yêu cầu hủy.
- Làm theo thứ tự: ATO/ATC giả định khớp đủ → cơ chế khớp một phần → mô hình
  thanh khoản. Mô hình thanh khoản quyết định lượng được khớp; loại lệnh quyết
  định cách xử lý phần dư. Quy tắc hết hiệu lực vẫn áp dụng ở mọi giai đoạn.

### 6.2. Đối chiếu triển khai hiện tại

| Yêu cầu | Hiện trạng đối chiếu mã nguồn |
| --- | --- |
| ATO | Gửi lúc 08:45 từ dữ liệu đã hoàn tất, chốt lượng theo Close liên tục gần nhất và khớp tại Open 09:00. |
| ATC | Gửi lúc 14:30, khớp tại Close nhãn 14:45; bản ghi ATC riêng cũ là đường tương thích. |
| Không cho sửa/hủy sau khi đặt | Signal/lệnh là dữ liệu bất biến; không có endpoint sửa/hủy. Engine chỉ tự kết thúc phần dư theo vòng đời đã khai báo. |
| Khớp đủ hoặc không khớp | Giới hạn bỏ trống cho khớp đủ; giá trị `0` tạo trường hợp không khớp và toàn bộ lượng hết hiệu lực. |
| Khớp một phần do giới hạn mô phỏng | `auction_match_quantity` giới hạn lượng khớp; đây là kiểm thử cơ chế, chưa phải mô hình thanh khoản thị trường. |
| Tự loại phần dư sau đấu giá | Phần dư kết thúc `expired` tại 09:00/14:45, không chuyển thành LO hoặc sang ngày sau. |

Căn cứ mã hiện tại: `FixedSignal`/`OrderResult` trong
`src/backtesting_api/domain/trading.py`; `submit`, `finish` và nhánh ATC trong
`src/backtesting_api/domain/session_matching.py`; bộ chuyển kết quả trong
`src/backtesting_api/application/inline_results.py`; các endpoint trong
`src/backtesting_api/api/backtest_routes.py`.

### 6.3. Giai đoạn 1 — ATO/ATC giả định khớp đủ

- [X] Bổ sung ATO vào cấu trúc lệnh, kiểm tra đầu vào và luồng chạy; giữ định
  nghĩa loại lệnh tập trung, dùng chung cơ chế ghi lệnh/lần khớp.
- [X] Thêm thời điểm xét/gửi ATO bằng dữ liệu đã khả dụng trước khi gửi;
  không dùng Open 09:00 hoặc Close 09:05 để quyết định lệnh ATO khớp lúc 09:00.
- [X] Lấy giá theo nhãn 09:00/14:45 đã chốt; tách sự kiện đấu giá khỏi quy tắc
  nến liên tục đóng sau 5 phút, không dời khớp ATC sang 14:50.
- [X] Giữ riêng thời điểm gửi, khớp và khả dụng; không đưa giá đấu giá vào
  chỉ báo hoặc quyết định trước khi giá đó khả dụng.
- [X] Thiếu bản ghi bắt buộc, sai mã hợp đồng hoặc sai giá/bước giá thì báo lỗi;
  không lấy giá gần nhất hoặc nến ngày khác thay thế.
- [X] Khóa giá trị lệnh sau khi ghi nhận hợp lệ; mọi đường sửa/hủy từ bên gửi
  phải bị từ chối. Không thêm API sửa/hủy mới chỉ để thực hiện quy tắc này.
- [X] Tách việc tự hết hiệu lực sau đấu giá khỏi yêu cầu hủy; lệnh không khớp
  phải kết thúc, không tự gửi lại hoặc chuyển thành LO.
- [X] Ghi nguồn giá OHLCV, quy ước lấy giá, giả định khớp đủ và phiên bản quy tắc
  vào đầu vào/kết quả; giữ khả năng đọc kết quả ATC từ bản ghi riêng đã lưu.
- [X] Nối API, tự lấy dữ liệu, kho file, bảng lệnh và biểu đồ với quy ước mới;
  giữ hành vi cấu hình cũ và không tự đổi điều kiện/giờ giao dịch CANSLIM v1.

### 6.4. Giai đoạn 2 — Cơ chế khớp một phần

- [X] Lưu riêng lượng đặt ban đầu, lượng đã khớp, lượng hết hiệu lực và lượng
  còn chờ; lượng đã khớp + lượng hết hiệu lực + lượng còn chờ = lượng đặt ban đầu.
  Không sửa lượng đặt thành lượng khớp.
- [ ] Cho một lệnh nối tới nhiều bản ghi khớp tách rời khi nguồn dữ liệu phân bổ
  yêu cầu. `fill_indices` đã giữ được nhiều liên kết, nhưng mã xử lý hiện gộp lượng
  khớp của một đợt thành một lần khớp vì chưa có nguồn phân bổ nhiều phần.
- [X] Ghi trạng thái và lý do kết thúc độc lập với lượng đã khớp, kể cả lệnh khớp
  một phần rồi hết hiệu lực.
- [X] Tại cùng đợt ATO/ATC, lượng được phân bổ dùng cùng giá đấu giá;
  phần dư tự hết hiệu lực ngay khi đợt đấu giá kết thúc, không chờ đợt khác.
- [X] Chỉ cập nhật vị thế, tiền, phí, thuế và ký quỹ theo lượng thực khớp;
  lượng không khớp không phát sinh giao dịch hoặc phí khớp lệnh.
- [X] Không tự tạo lần khớp tiếp hoặc lệnh mới tăng vị thế; phần mở thực tế dùng
  lượng đã khớp để tính giá vốn, stop/target và lượng chốt lời. Không tự mở quyền
  tăng vị thế. Chốt cách tính giá vốn, stop/target và lượng TP khi mở chưa đủ.
- [X] Nếu ATC đóng chưa đủ, giữ đúng vị thế còn lại; áp dụng quy tắc cuối ngày
  đã khai báo, không tự đóng hết để làm lượt chạy thành công.
- [X] Cập nhật chuyển kết quả, lưu/tải lại, ID liên kết, bảng lệnh và biểu đồ để
  phần đã khớp không bị mất khi trạng thái cuối của lệnh là hết hiệu lực.

### 6.5. Giai đoạn 3 — Mô hình thanh khoản

- [X] Kiểm tra cơ chế bằng lượng khớp giả định cố định trước khi dùng volume
  thị trường; dữ liệu tổng hợp chỉ dùng kiểm thử, không làm dữ liệu nghiệm thu.
- [ ] Chốt mô hình và tham số ước lượng lượng đối ứng; xác nhận đơn vị volume
  và phân biệt volume từng nến với volume lũy kế trước khi sử dụng.
- [ ] Không dùng volume cuối nến để quyết định khớp tại Open của chính nến đó;
  không coi volume toàn phiên là lượng chắc chắn đối ứng với lệnh của mình.
- [ ] Không phân bổ vượt lượng còn chờ hoặc dùng lặp cùng lượng thanh khoản;
  lưu giả định và tham số để chạy lại được cùng kết quả.

### 6.6. Kiểm thử và nghiệm thu cần thực hiện

- [X] Với cả ATO và ATC: từ chối sửa/hủy sau khi ghi nhận; engine chỉ gửi đúng
  phiên và từ chối gửi tại/sau thời điểm khớp.
- [X] Đặt 5, khớp 5: vị thế thay đổi 5, không còn lượng chờ.
- [X] Đặt 5, khớp 2: vị thế thay đổi 2, lượng 3 còn lại hết hiệu lực sau đấu giá;
  lịch sử vẫn giữ lượng đặt 5, lần khớp 2 và lượng hết hiệu lực 3.
- [X] Đặt 5, khớp 0: không có fill hoặc phí khớp lệnh, toàn bộ 5 hết hiệu lực.
- [X] Lệnh/phần dư hết hiệu lực không được khớp lại ở nến tiếp theo hoặc ngày sau;
  phần đã khớp vẫn tồn tại và được quản lý đúng.
- [X] Thiếu giá đấu giá phải báo thiếu dữ liệu, không đổi thành “không khớp”.
- [X] Kiểm tra tiền/phí/ký quỹ, các phía mở/đóng được hỗ trợ và ATC đóng chưa đủ;
  trường hợp chưa chốt hành vi phải được bổ sung đặc tả trước khi viết logic.
- [X] Giá tương lai không đổi quyết định cũ; so kết quả đến cùng mốc đã hoàn tất
  khi chạy dữ liệu đầy đủ và dữ liệu cắt; chạy lại cùng đầu vào cho cùng kết quả.
- [X] Chạy kiểm thử phiên, hợp đồng, API/kho file và giao diện liên quan; nghiệm
  thu trên OHLCV được cung cấp sau khi kiểm thử tổng hợp đạt yêu cầu.
- [X] Cập nhật hợp đồng dữ liệu, đặc tả API, hướng dẫn JSON, tài liệu khớp theo
  phiên và danh mục kiểm thử khi từng giai đoạn được triển khai.

## 7. Đặc tả MTL/MOK/MAK — A01

A01 chốt đặc tả; A02–A07 triển khai ngày 20/10/2026 cho lượng đối ứng cố định và biên giá có nguồn.

### 7.1. Quy tắc sàn và phạm vi hiệu lực

- [Quyết định 21/QĐ-HĐTV ngày 18/04/2025 của VNX](https://stream.vnx.vn/VNX/Legal/2025042314515227121.QD.HDTV.pdf) thay Quyết định 20/QĐ-HĐTV ngày 20/05/2022 khi hệ thống mới vận hành.
- [Danh mục quy chế VNX](https://www.vnx.vn/vi/van-ban-phap-ly/6) ghi hiệu lực 05/05/2025. Lần tra ngày 20/10/2026 tìm thấy hai văn bản trên.
- Phạm vi A01 đã đối chiếu: 05/05/2025–20/10/2026. Kỳ ngoài phạm vi cần đối chiếu quy chế trước khi dùng loại lệnh mới.

| Căn cứ trong Quy chế kèm Quyết định | Quy tắc sàn được sử dụng |
| --- | --- |
| Điều 21 khoản 2; Điều 22 khoản 2 điểm a–c | Lệnh thị trường mua/bán theo giá đối ứng đang có, chỉ nhập trong phiên liên tục; không có đối ứng thì hủy ngay. |
| Điều 22 khoản 2 điểm d | MOK khớp toàn bộ hoặc hủy toàn bộ; MAK khớp phần có thể khớp và hủy dư; MTL chuyển dư sang LO sau khi có khớp. |
| Điều 22 khoản 2 điểm d, mục (i)–(iii) của MTL | LO mua dư cao hơn giá khớp cuối một bước, bán dư thấp hơn một bước; nếu đã ở trần/sàn thì giữ trần/sàn. LO chuyển đổi theo quy định sửa/hủy LO. |
| Điều 22 khoản 1 điểm b; Điều 24 | LO có thể tồn tại đến hết ngày hoặc bị hủy; việc sửa/hủy chỉ tác động phần chưa khớp, không cho sửa/hủy trong phiên định kỳ. |
| Điều 15–16 | Biên độ theo mẫu hợp đồng; trần/sàn dựa vào giá tham chiếu, có trường hợp điều chỉnh. Không suy trần/sàn từ High/Low của nến. |

- Số trang in 7–10 của Quy chế tương ứng trang PDF 9–12; định nghĩa MTL/MOK/MAK ở trang in 8, trang PDF 10.
- [Thông tin sản phẩm VN30 của VSDC](https://vsdc.vn/vi/thong-tin-san-pham) ghi bước giá 0,1 điểm và đơn vị 1 hợp đồng.
- Project giữ bước giá này; không lấy tỷ lệ biên độ công bố chung thay bảng trần/sàn từng ngày/hợp đồng.

Quy tắc sàn không quy định khớp tại Open nến 5 phút. Giá Open, độ trễ tới
nến kế tiếp, thời điểm ghi nhận và hủy sớm bên dưới đều là giả định project.

### 7.2. D01 — Hành động và mô hình hợp lệ

Cả ba loại đều dùng được trong bốn hành động sau, ở chế độ một vị thế hoặc
`sizing.pyramiding: true`; một lần khớp tiếp theo thuộc cùng lệnh và
`position_id`, không phải tín hiệu mở mới. A03 chốt quản trị giá vốn/bảo vệ.

| Hành động | Hướng vị thế | Chiều giao dịch | Loại mở/đóng theo điều kiện |
| --- | --- | --- | --- |
| Mở LONG | LONG | BUY | MTL, MOK, MAK |
| Mở SHORT | SHORT | SELL | MTL, MOK, MAK |
| Đóng LONG | LONG | SELL | MTL, MOK, MAK |
| Đóng SHORT | SHORT | BUY | MTL, MOK, MAK |

- Yêu cầu: contract, `hnx_sessions_v1`, nến 5 phút, `Asia/Ho_Chi_Minh`, `slippage_rate: 0` và đúng mã hợp đồng.
- `next_open` và normalized từ chối MTL/MOK/MAK. Ba loại dùng đúng tên, theo bốn hành động ở bảng trên.
- Nhiều phần chỉ bổ sung cùng hướng theo `priority` và hạn mức. Lệnh đóng giảm đúng phần được chỉ định, tối đa lượng còn lại.

### 7.3. D02 — Thời điểm, giá và lượng chốt trước

1. Sau Close `t`, đánh giá dữ liệu có `available_at <= decision_time`.
2. Trong phiên liên tục, chốt lượng mở và giữ chỗ theo Close vừa hoàn tất, sau khi áp hạn mức.
3. Thử khớp tại Open nến liên tục kế tiếp, cùng buổi, ngày và hợp đồng.
4. Cùng nhãn giờ: Close → quyết định/gửi → Open kế, giả định độ trễ 0.
5. Giá mô phỏng BUY/SELL là Open, chênh lệch mua/bán bằng 0. Các giá cuối nến chỉ khả dụng khi nến hoàn tất.
6. Kiểm tra giá, phiên, mã, lượng và tài khoản trước fill, phí hoặc trừ đối ứng. Lượng đối ứng cố định theo A02.
7. Thiếu ký quỹ: từ chối toàn bộ lượng định khớp, kết thúc dư, giữ fill trước đó. Lượng đã nhận đặt giữ nguyên.

Chi tiết tiền tại [mục 6 kế toán](canslim-v1-execution-accounting.md#6-hợp-đồng-kế-toán-mtlmokmak).

- Khi triển khai, ghim phiên bản quy tắc mới và các giả định trên vào cấu hình đã chuẩn bị/metadata: Close dùng tính lượng, thứ tự Close → Open, giá Open, LO dư từ nến sau, thời hạn và nguồn biên giá.
- Không ghi đè phiên bản hoặc hash của lượt cũ; chạy lại dùng đúng dữ liệu/quy tắc đã ghim.

- Close 11:30/14:30 nằm ngoài khoảng gửi lệnh liên tục.
- Lệnh chưa khớp kết thúc khi vượt hạn mở, hết buổi, đổi ngày/mã hoặc hết kỳ báo cáo.
- Thiếu nến cùng buổi là lỗi dữ liệu thực thi; lượng đối ứng 0 là trường hợp riêng.
- `flat_by` và `allow_overnight: false` vẫn được kiểm tra.

### 7.4. D03 — MTL chuyển dư thành LO

Chỉ chuyển khi `0 < lượng đã khớp < lượng đã nhận`. Gọi `P` là giá khớp cuối
của chính lệnh MTL, `U`/`D` là trần/sàn của ngày và hợp đồng đó:

```text
BUY:  giá LO dư = min(P + 0,1; U)
SELL: giá LO dư = max(P - 0,1; D)
```

- MTL khớp 0: hủy toàn bộ. Khớp đủ: kết thúc lệnh.
- Khớp một phần: chuyển dư theo giá P, trần U, sàn D đã cung cấp. Các giá phải hữu hạn, dương, đúng bước 0,1 và `D <= P <= U`.
- Thiếu hoặc sai biên giá: lỗi dữ liệu trước khi ghi fill. Xem [API mục 3.4.4](backtest-api-specification.md#344-lệnh-mtlmokmak).

- Giữ yêu cầu gốc MTL và lượng nhận đặt; ghi sự kiện chuyển loại với giá, lượng và thời điểm.
- LO dư chỉ xét từ **nến liên tục kế tiếp sau nến chuyển đổi**, nhằm giữ đúng thứ tự thông tin.
- Các nến sau dùng giá LO ở mục 2 và ngân sách A02. Giá chưa đạt điều kiện thì giữ ngân sách.

- LO dư dùng `order.pending` của MTL; mặc định `max_execution_bars=1`.
- Đếm từ nến đầu được thử LO dư; mỗi nến tính một lần, kể cả lượng đối ứng 0.
- Ba cờ `cross_*` là `false`; hủy dư tại nghỉ trưa, hạn mở, ATC, đổi ngày/mã hoặc hết kỳ.
- Chính sách hủy sớm của dự án ngắn hơn thời hạn tối đa hết ngày của sàn.
- MAK/MOK kết thúc sau lần thử đầu và từ chối `pending` riêng.

### 7.5. Ma trận lượng và trường hợp biên

Giả sử lệnh đã được nhận **5 hợp đồng**, đủ tiền và dữ liệu hợp lệ. Lượng
khả dụng là 0/2/5 hợp đồng cố định, không phải volume của nến:

| Loại | Khả dụng 0 | Khả dụng 2 | Khả dụng 5 hoặc lớn hơn |
| --- | --- | --- | --- |
| MOK | Hủy 5 | Hủy 5, giữ ngân sách | Khớp 5 |
| MAK | Hủy 5 | Khớp 2, hủy 3 | Khớp 5 |
| MTL | Hủy 5, không sinh LO | Khớp 2, chuyển LO 3 | Khớp 5, không sinh LO |

- Open=1300, sàn=1200, trần=1400: MTL BUY khớp 2 ở 1300, dư LO mua 3 ở 1300,1; SELL dư LO bán 3 ở 1299,9.
- BUY tại P=1400 giữ LO=1400; SELL tại P=1200 giữ LO=1200. BUY P=1399,9 và SELL P=1200,1 cũng cho LO tại biên.
- Ví dụ áp dụng cả lệnh mở và đóng theo mục 7.2.
- Hạn mức nhận 3 từ lượng mong muốn 5: MOK kiểm tra đủ 3. Đã nhận 5 mà chỉ có đối ứng 2: hủy cả lệnh.

| Trường hợp | Hành vi bắt buộc khi triển khai |
| --- | --- |
| Lượng yêu cầu/sizing bằng 0 | Từ chối đặt, không có fill/phí hoặc giữ chỗ; không nhầm với lượng đối ứng 0. |
| Lượng đối ứng âm, phân số, boolean hoặc thiếu | Lỗi đầu vào cấp lượng; không đổi thành 0 hoặc khớp đủ. |
| Open thiếu, sai giá trị/bước giá hoặc ngoài biên | Lỗi dữ liệu, kể cả lượng đối ứng 0. |
| Thiếu bảng biên giá, sai ngày/mã hoặc biên chưa khả dụng | Lỗi dữ liệu; không lấy Close/High/Low suy ra hoặc dùng ngày/mã khác. |
| Gửi/thử trong ATO, nghỉ trưa, ATC hoặc ngoài phiên | Không khớp; gửi sai phiên bị từ chối, lệnh chờ được kết thúc tại ranh giới đã khai báo. |
| Bộ khớp trả lượng âm/phân số, vượt lượng còn chờ/ngân sách, sai chiều/mã/thời điểm hoặc sai giá | Lỗi hợp đồng nội bộ, dừng lượt chạy trước khi hạch toán; không chặn số hoặc công bố kết quả một phần là thành công. |
| Thiếu ký quỹ sau phí tại giá khớp | Từ chối toàn bộ phần định khớp, kết thúc dư và giữ ngân sách. |

### 7.6. Cấu hình và bằng chứng cơ chế

- `execution.continuous_match_quantity`: số nguyên không âm, dùng chung LO/MTL/MOK/MAK trong một nến và mã hợp đồng.
- Ngân sách dùng chung mua/bán và Open/Close; nến mới cấp lại lượng cố định.
- Thứ tự: Open trước Close, cùng sự kiện theo thứ tự gửi.
- Giá chưa đạt, MOK thiếu lượng hoặc tài khoản từ chối: giữ ngân sách.
- Đây là cấu hình D05 của mục 2; lượng đối ứng được cung cấp cố định.

- SIMULATED và các lệnh bảo vệ giữ cách khớp cũ, không chịu ngân sách cố định; ATO/ATC vẫn dùng `auction_match_quantity` riêng mỗi lệnh.
- Bỏ cấu hình mới giữ LO khớp đủ như trước, MTL/MOK/MAK bị từ chối vì chưa có lượng đối ứng.
- Kết quả ghi `hnx-sessions-v4-market-orders`, lượng cố định, biên giá có nguồn và các giả định.
- D04 được mô tả tại mục 6 kế toán.

[Hồ sơ kiểm thử cơ chế](../testing/market-orders-partial-matching.md) đối chiếu các bảng trên. [Ví dụ MTL mở, MAK đóng](../examples/orders/market-fixed.json) dùng sáu nến và biên giá tổng hợp có nhãn nguồn.

## Nguồn quy tắc

- [Giờ phiên và loại lệnh phái sinh — ACBS](https://acbs.com.vn/blog/gio-giao-dich-phai-sinh).
- [Quyết định 21/QĐ-HĐTV ngày 18/04/2025 — bản gốc VNX](https://stream.vnx.vn/VNX/Legal/2025042314515227121.QD.HDTV.pdf), đối chiếu Điều 15–16, 21–22, 24 ngày 20/10/2026.
- [Lịch và loại lệnh phái sinh — Shinhan](https://shinhansec.com.vn/vi/ho-tro-khach-hang/chung-khoan-phai-sinh.html).
- [Hướng dẫn giao dịch phái sinh — SHS](https://www.shs.com.vn/Sites/QuoteVN/SiteRoot/documents/2025/HDnhadautugiaodichchungkhoanphaisinh.pdf).

Các quy ước khớp OHLC, thời hạn LO và xử lý stop/target trong tài liệu này là
quyết định mô phỏng của project, không được trình bày thành quy tắc khớp của HNX.
