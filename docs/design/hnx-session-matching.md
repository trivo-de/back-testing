# Khớp lệnh theo phiên HNX trên nến 5 phút

Chế độ `hnx_sessions_v1` hỗ trợ ATO mở vị thế, LO trong phiên liên tục và ATC
đóng vị thế. Đây là mô phỏng OHLC; `execution.auction_match_quantity` có thể giới
hạn lượng khớp mỗi lệnh ATO/ATC để kiểm tra khớp một phần. Cấu hình này không tái
dựng sổ lệnh, hàng đợi hoặc thanh khoản thật. Không đổi mẫu CANSLIM v1 hiện hành.

Checklist mở rộng ATO/ATC theo quy ước OHLCV đã chốt ngày 14/10/2026 nằm ở
mục 6. Trạng thái trong checklist phân biệt cơ chế đã kiểm thử tổng hợp với mô
hình thanh khoản và nghiệm thu dữ liệu thật chưa thực hiện.

## 1. Bật chế độ

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

`auction_match_quantity` là số nguyên không âm và không bắt buộc. Bỏ trường này
để giả định khớp đủ; đặt `2` nghĩa là mỗi lệnh đấu giá khớp tối đa 2 hợp đồng;
đặt `0` để kiểm tra trường hợp không khớp. Chỉ dùng trường này khi có lệnh ATO
hoặc ATC. Giá trị được ghim trong đầu vào và metadata kết quả.

Không khai báo `matching_model` thì giữ đường chạy cũ; `normalized` không dùng
chế độ này. Dữ liệu nhập tay cần nguồn và mã hợp đồng theo ngày. Khi tự lấy,
service tải VN30F1M/VNINDEX 5 phút như luồng hiện có, tạo `contract_dates` từ bảng
đáo hạn đã cung cấp theo giả định giữ mã đến hết ngày đáo hạn, chuyển từ ngày sau đó.
Giả định này đã được người dùng đồng ý và được lưu cùng nguồn dữ liệu; không xác
minh lịch chuyển mã của nhà cung cấp. Các kiểm tra lịch phiên và độ phủ bảng hợp
đồng vẫn áp dụng. Không tự đổi mô hình tiền, trượt giá, ngưỡng hoặc giờ thoát CANSLIM.

Trên web có thể bật lấy dữ liệu tự động khi chọn khớp theo phiên HNX. `/validate`
trả lại payload đầy đủ với `auto_fetch_data: false` để chạy lại đúng dữ liệu đã
kiểm tra. ATO/ATC chỉ chạy khi dữ liệu trả về có bản ghi nhãn 09:00/14:45 cần
thiết; thiếu bản ghi thì lượt chạy báo lỗi, không lấy giá gần nhất thay thế.

ATO mở vị thế dùng `execution.entry_fill_policy: "ato"`. Engine xét điều kiện lúc
08:45 bằng dữ liệu đã hoàn tất trước thời điểm đó, chốt lượng đặt theo Close liên
tục gần nhất và kiểm tra lại ký quỹ tại Open 09:00. Vì vậy dữ liệu phải có lịch sử
trước ngày cần vào ATO; Open 09:00 không được dùng để quyết định hoặc tính lượng.

LO mở khai báo `strategy.entry.limit_price` bằng biểu thức số hiện có, ví dụ
`{"ref":"trade_data.close"}` hoặc `{"sub":[{"ref":"trade_data.close"},0.5]}`.
Giá và số lượng được chốt tại thời điểm tín hiệu, không tính lại theo nến tương lai.
Giá giới hạn phải dương và đúng bước 0,1 điểm; sai thì lệnh bị từ chối.
`next_open` vẫn dùng được và giữ cách tính khối lượng tại Open.

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

`strategy.entry.pending.max_execution_bars` mặc định 1, cho phép số nguyên ≥ 1
ở chế độ mới; đây là thời hạn chờ cho các LO. Các cờ `cross_lunch`, `cross_cutoff`,
`cross_session` vẫn chỉ nhận `false`. LO chưa khớp bị hủy trước nghỉ trưa, trước ATC
hoặc khi qua giờ giới hạn mở vị thế. Hết số nến chờ thì `expired`.
Hủy tại ranh giới phiên là chính sách gửi lệnh đã khai báo trước, được xử lý
trước khi engine chuyển sang phiên tiếp theo; không phải lệnh hủy gửi trong ATC.

LO mở tại Open dùng thứ tự stop/target hiện có. LO mở giữa nến được ghi thời điểm
khớp tại Close của nến đó và giữ `bar_time` là Open chứa khớp. Stop có thể đóng
ngay trong nến này; mục tiêu chốt lời chỉ xét từ nến kế tiếp. Thứ tự giá trong nến
không được biết: stop có thể bị ghi nhận theo giả định bảo thủ dù thực tế giá chạm
stop trước lúc mở vị thế. Tất cả giả định được lưu trong kết quả.

Khối lượng LO mở tính bằng công thức rủi ro/ký quỹ hiện có, lấy giá giới hạn làm
giá dự kiến. ATO dùng Close liên tục gần nhất đã khả dụng trước 08:45. Khi khớp,
kiểm tra lại ký quỹ sau phí ở giá thực hiện; thiếu thì từ chối toàn bộ, không tự
giảm số hợp đồng. Không mô phỏng đảo chiều. Nếu ATC chỉ đóng được một phần,
`allow_overnight: false` làm lượt chạy lỗi `END_OF_DAY_POSITION_REQUIRES_EXIT`;
không khai báo cờ này thì kết quả giữ vị thế còn lại để đối chiếu.

## 3. Dữ liệu bổ sung bắt buộc

`trade_data.contract_dates` là danh sách tăng dần, mỗi ngày một mã hợp đồng,
bao phủ cả lịch sử khởi tạo chỉ báo và kỳ báo cáo. Với dữ liệu nhập tay, khai báo
ánh xạ theo nguồn hoặc giả định đã được đồng ý. Với tự lấy để khớp liên tục, service
tạo danh sách theo giả định đáo hạn đã nêu ở mục 1, chỉ trong phạm vi dữ liệu được
dùng đến cuối kỳ báo cáo. Không coi ánh xạ này là lịch chuyển mã đã xác minh với
nhà cung cấp.

`trade_data.bars` giữ bản ghi nhãn 09:00 cho ATO và nhãn 14:45 cho ATC. ATO lấy
`open` của bản ghi 09:00; ATC lấy `close` của bản ghi 14:45. Giá phải dương và
đúng bước 0,1 điểm. `contract_dates` và `provenance` vẫn là dữ liệu bắt buộc khi
nhập tay. Thiếu bản ghi đang cần, sai ngày hoặc sai mã hợp đồng làm lượt chạy lỗi.

Trường `trade_data.auctions` cũ vẫn được đọc để chạy lại input ATC đã lưu trước
thay đổi này. Lượt chạy mới ưu tiên bản ghi OHLCV 14:45 khi cả hai cùng tồn tại.
Bản ghi cũ vẫn phải có `match_time` 14:45, `available_at`, `status`, `price` và
`source` hợp lệ như hợp đồng trước đây.

Lịch giao dịch lấy từ `runtime-policy-v1.json` và được lưu cùng đầu vào. `trade_data`
và `market_data` vẫn được kiểm tra theo lịch riêng. Engine tách bản ghi ATO/ATC ra
khỏi chuỗi nến dùng cho chỉ báo và quyết định. Không lấy giá gần nhất, Open kế tiếp
hoặc nến ngày khác thay dữ liệu thiếu. Đợt này chưa kiểm tra trần/sàn, giá thanh
toán hằng ngày hoặc ngày đáo hạn.

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

Không dùng giá ATC trong điều kiện gửi lệnh. Nếu có `flat_by`, giờ này không được
sớm hơn 14:45. Mẫu CANSLIM có giờ thoát cũ được giữ nguyên; muốn dùng ATC phải
khai báo thành một cấu hình chiến lược riêng.

Thiếu bản ghi khi cần khớp báo `MISSING_ATO_MATCH_BAR` hoặc
`MISSING_ATC_MATCH_BAR`. Lượng khớp bằng 0 làm lệnh hết hiệu lực; còn vị thế cuối
ngày với `allow_overnight: false` thì báo `END_OF_DAY_POSITION_REQUIRES_EXIT`,
không tự đóng. Không có API sửa/hủy lệnh ATO/ATC. Giá đấu giá không tham gia chuỗi
chỉ báo. Thời điểm khớp là nhãn 09:00/14:45; `available_at` của fill ATO là 09:00,
còn ATC dùng thời điểm khả dụng của bản ghi 14:45.

Kết quả vẫn dùng `schema_version: 2`, thêm `metadata.matching_model`,
`matching_rules_version`, nguồn dữ liệu và giả định. Mỗi lệnh có `order_type`,
`quantity`, `filled_quantity`, `expired_quantity`, `remaining_quantity`,
`limit_price`, `submitted_time`, `completed_time`, `events`.
Trạng thái cuối gồm `filled`, `rejected`, `canceled`, `expired`; lịch sự kiện ghi
`submitted`, có thể có `partially_filled`, rồi trạng thái kết thúc. Lệnh khớp một
phần kết thúc là `expired` nhưng vẫn liên kết tới fill đã tạo; lượng chưa khớp
không tạo fill hoặc phí. Fill bổ sung `phase`, `order_type`, `time_precision`;
ATO/ATC có thêm nguồn và
`available_at`. ID nối tín hiệu/lệnh/lần khớp tiếp tục được lưu và kiểm tra.

Kho file lưu toàn bộ dữ liệu nến, nguồn, lịch và cấu hình trong snapshot
có dấu kiểm. Web tải các trường này cùng dữ liệu giao dịch, hiển thị loại lệnh,
khối lượng đặt/khớp/hết hiệu lực/còn chờ và thời điểm kết thúc. Biểu đồ dùng
Open 09:00 hoặc Close 14:45 để kiểm tra vị trí mũi tên; bản ghi ATC cũ vẫn dùng
điểm trắng và đường giá riêng, không tạo nến OHLC giả.

## 5. Kiểm chứng

`tests/test_session_matching.py` kiểm tra phiên, ATO/ATC khớp đủ/một phần/không
khớp, LO hai hướng và LO đóng,
thời hạn/hủy lệnh, stop/target bảo thủ, khối lượng chốt trước, kiểm tra ký quỹ,
ATC thiếu/không khớp/sai hợp đồng, tính độc lập với giá tương lai,
API, snapshot, tải lại kết quả và dữ liệu biểu đồ.
`tests/web/backtest-input.test.mjs` và `backtest-chart.test.mjs` kiểm tra dữ liệu
ATO/ATC không bị mất khi tải JSON và mũi tên không cần nến giả.

Các kiểm thử trên dùng dữ liệu tổng hợp. Chưa nghiệm thu giá ATO/ATC thật hoặc độ đúng
của lịch chuyển hợp đồng từ nhà cung cấp; phải cung cấp/xác nhận trước khi kết luận
kết quả ATC trên dữ liệu thị trường là đáng tin cậy.

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

## Nguồn quy tắc

- [Giờ phiên và loại lệnh phái sinh — ACBS](https://acbs.com.vn/blog/gio-giao-dich-phai-sinh).
- [Quyết định 21/QĐ-HĐTV ngày 18/04/2025 của VNX](https://vts.com.vn/upload/files/VBPL/2025042314515227121_QD_HDTV.pdf).
- [Lịch và loại lệnh phái sinh — Shinhan](https://shinhansec.com.vn/vi/ho-tro-khach-hang/chung-khoan-phai-sinh.html).
- [Hướng dẫn giao dịch phái sinh — SHS](https://www.shs.com.vn/Sites/QuoteVN/SiteRoot/documents/2025/HDnhadautugiaodichchungkhoanphaisinh.pdf).

Các quy ước khớp OHLC, thời hạn LO và xử lý stop/target trong tài liệu này là
quyết định mô phỏng của project, không được trình bày thành quy tắc khớp của HNX.
