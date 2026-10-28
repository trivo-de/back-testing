# Hợp đồng đích: khớp ngay hoặc LO, một vị thế và lãi/lỗ theo điểm

Ngày lập: 23/10/2026. A đã duyệt; B–D (T04–T16) đã triển khai và kiểm chứng ngày 27/10/2026.
Tài liệu này sở hữu hợp đồng API hiện tại: POST/validate chỉ nhận cấu hình mới;
lịch sử cũ đọc theo schema và đơn vị gốc. E–F chưa hoàn tất; không sửa payload/kết quả đã lưu.
Cập nhật D08 ngày 27/10/2026 theo yêu cầu của bạn: tự đóng hết vị thế khi hết ngày.
Lần chạy mới ghim `session_end_action=close_at_close`, `default_profile_version=price-only-v2`;
bản ghim v1 vẫn chạy lại theo quy tắc cũ.

## 1. Quyết định D01–D10

Bạn đã xác nhận ngày 23/10/2026: **hai cách khớp — khớp ngay tại Close hoặc LO**;
**một vị thế**; **SL/TP/trailing dùng %**; **LLM để sau**. Quyết định hai cách khớp thay lựa chọn chỉ LO trước đó.
Ngày 27/10/2026, bạn xác nhận đã duyệt các phần còn lại của A, gồm D02, D07–D09
và request/response đích. D08 đã chốt: không giữ vị thế
qua ngày; LO tối đa 3 nến thực có và chỉ trong ngày đặt. T01–T03 và điểm kiểm tra A hoàn tất.

| Mã | Kết luận cụ thể | Trạng thái |
| --- | --- | --- |
| D01 | Chọn rõ từng lệnh: khớp ngay tại Close nến ra tín hiệu, hoặc LO chờ giá limit từ nến sau; áp dụng cả mở và đóng | Đã duyệt hai cách khớp |
| D02 | Decimal: chênh lệch giá × hướng × lượng; không vốn, phí/thuế, trượt giá, ký quỹ, hệ số hợp đồng hoặc tỷ suất trên vốn | Đã duyệt ngày 27/10/2026 |
| D03 | SL/TP/trailing dùng phần trăm; 6 nghĩa là 6%, không phải 0,06%. SL/TP từ giá khớp vào thực tế; trailing theo cực trị thuận lợi của cơ chế kích hoạt | Đã duyệt đơn vị %; chi tiết bảo vệ ở D07 |
| D04 | `quantity` nguyên dương, bỏ thì dùng mặc định máy chủ 1; tối đa một vị thế và một lệnh chủ động đang chờ; không cộng thêm vào vị thế đang mở | Đã duyệt |
| D05 | LO được xét tối đa 3 nến thực có sau nến tạo lệnh, chỉ trong ngày đặt; hết nến thứ 3 chưa khớp hoặc hết ngày trước thì hủy. Khớp ngay không có thời hạn chờ | Đã duyệt |
| D06 | Giữ khớp ngay và LO cho mở/đóng theo điều kiện. ATO/ATC/MTL/MOK/MAK, pyramiding và cấu hình cũ không nằm trong bề mặt mới; không tự đổi lệnh cũ sang một trong hai cách | Đã duyệt hai cách khớp |
| D07 | SL/TP chỉ xét và thoát tại Close. Trailing dùng chuỗi Close theo quy ước đồng bộ bên dưới; giữ TP nhiều mức/đóng từng phần | Đã duyệt toàn bộ quy ước bên dưới ngày 27/10/2026 |
| D08 | Qua trưa được giữ vị thế; cuối phiên liên tục tự đóng hết lượng còn giữ tại Close thực của nến cuối phiên, hủy lệnh chờ. LO tối đa 3 nến trong ngày. Dữ liệu dừng giữa phiên vẫn ghi vị thế mở; không đóng bằng giá ngày sau hoặc mã hợp đồng khác | Đã duyệt ngày 27/10/2026 |
| D09 | Đọc lịch sử cũ theo đơn vị gốc, giữ nguyên bytes/hash; không chạy payload cũ âm thầm theo nghĩa mới | Đã duyệt ngày 27/10/2026 |
| D10 | Để sau: phần A không chọn nhà cung cấp/model/ngân sách, không gọi LLM; cấu hình và phê duyệt sử dụng dịch vụ thuộc giai đoạn E | Đã duyệt hoãn |

## 2. Quy tắc thời gian và khớp

Các quy tắc dưới đây đã được duyệt trong phần A ngày 27/10/2026.
Đường mới đã thực hiện B–D; phạm vi kiểm chứng và E–F còn lại ghi ở mục 7.

1. Tại Close nến t, chỉ đọc dữ liệu có `available_at <= decision_time`.
   LONG mở BUY, đóng SELL; SHORT mở SELL, đóng BUY. Mỗi lệnh phải chỉ rõ cách
   khớp, không chọn ngầm theo hướng vị thế hoặc tên chiến lược.
2. **Khớp ngay (`IMMEDIATE`)**: điều kiện đúng → tín hiệu → tạo lệnh → fill đủ
   lượng tại chính Close t. Các sự kiện cùng timestamp Close t nhưng giữ thứ tự
   quyết định → gửi → khớp, `fill_phase=decision_close`. Không chờ Open nến kế,
   không có limit/thời hạn chờ. Đây là giả định mô phỏng cùng Close, độ trễ 0,
   không thanh khoản/trượt giá; không phải khẳng định khớp thực tế hoặc loại lệnh sàn.
   Đây là thay đổi được bạn duyệt so với quy tắc chỉ khớp nến sau của runtime cũ.
3. **LO**: chốt giá limit và lượng tại lúc tạo từ thông tin đã biết; chỉ xét từ
   nến thực có kế tiếp. BUY khớp Open nếu Open <= limit, nếu không thì khớp limit
   khi Low <= limit. SELL đối xứng: Open >= limit hoặc High >= limit. Không chạm
   thì giữ lệnh để xét tiếp, tối đa 3 nến thực có sau nến tạo lệnh và chỉ trong
   ngày đặt theo D05; không tự chuyển LO sang khớp ngay.
   **Thời hạn LO đã chốt:** nến tạo tín hiệu không tính vào 3 nến. Xét đầy đủ
   nến thứ 1, 2, 3; vẫn được khớp trong nến thứ 3. Sau Close nến thứ 3 chưa khớp:
   EXPIRED/MAX_EXECUTION_BARS, không xét nến thứ 4. Hết ngày đặt trước khi đủ
   3 nến: EXPIRED/END_OF_DAY; tuyệt đối không khớp bằng nến ngày sau.
   Ngày theo Asia/Ho_Chi_Minh; thời điểm hết phiên theo lịch nguồn nội bộ có độ phủ,
   không tự đặt giờ đóng cửa. Khi không có lịch, hủy ở ranh giới ngày địa phương
   trước khi xét bất kỳ nến ngày sau, đồng thời ghi giới hạn chưa xác nhận cuối phiên.
   Nghỉ trưa không tính là nến và không đặt lại bộ đếm; được chờ qua trưa cùng ngày
   nếu chiến lược không có cutoff/cửa sổ cấm. Khoảng thiếu không được tạo nến để đếm.
   Cuối báo cáo, đổi mã, thay đổi vị thế hoặc cutoff được hủy sớm hơn theo chính
   sách tương ứng. Không thay lệnh đang chờ để làm mới giới hạn 3 nến.
4. LO khớp tại Open ghi thời điểm Open; LO suy ra chạm trong nến ghi tại Close,
   `fill_phase=intrabar_assumed`. Khớp ngay ghi đúng Close sinh tín hiệu, không
   gán ngược fill về Open hoặc dùng High/Low để chọn một giá thuận lợi hơn.
   Cả hai cách giả định khớp đủ lượng hợp lệ; đóng từng phần là ý định giảm vị thế.
5. SL/TP tính ngưỡng từ giá khớp vào thực tế và phần trăm đã khai báo.
   **Chỉ kiểm tra tại Close nến đã hoàn tất**: LONG Close <= stop hoặc >= TP;
   SHORT Close >= stop hoặc <= TP. High/Low chạm ngưỡng nhưng Close chưa đạt
   thì không thoát; Open gap qua ngưỡng cũng không làm khớp trước Close.
6. Khi SL/TP được kích hoạt, tạo sự kiện thoát tự động và ghi fill **tại Close
   đang xét**, fill_phase=decision_close. Không khớp tại mức stop/target hoặc
   Open đã qua; phần trăm lỗ/lãi thực tế có thể vượt tham số. Đây là thoát bảo vệ
   tự động theo mô phỏng cùng Close; lệnh đóng theo điều kiện vẫn giữ IMMEDIATE/LO
   đã khai báo, không chuyển ngầm các lệnh LO đang chờ thành khớp ngay.
   Close vượt nhiều mức TP: xử lý TP1 rồi TP2 trên lượng còn lại,
   tất cả phần đóng ở cùng Close, không gán về từng giá target.
7. Thời điểm và thứ tự đã chốt: LO chờ có thể khớp tại Open hoặc trong nến như
   mục 3–4; sau đó tại Close xét SL/TP trên vị thế đã có trước quyết định mở mới,
   rồi điều kiện thoát và entry. Entry IMMEDIATE tại Close chỉ xét bảo vệ từ
   nến sau, không mở/đóng cùng Close bằng cùng bộ bảo vệ mới. Với LO entry Open
   hoặc intrabar, xét SL/TP tại Close nến entry sau fill theo thứ tự sự kiện;
   không dùng High/Low để xét bảo vệ.
   Bảo vệ làm thay đổi quantity thì hủy LO đóng còn chờ với POSITION_CHANGED.
8. **Quy ước trailing đồng bộ theo Close**: dùng đơn vị %, mốc ban đầu là giá
   khớp khi trailing bắt đầu có hiệu lực. LONG giữ Close cao nhất đã biết kể từ
   kích hoạt (gồm mốc seed); mức trailing = mốc × (1 − pct/100). SHORT dùng
   Close thấp nhất và mức = mốc × (1 + pct/100). Không dùng High/Low trước entry.
   Mỗi Close kiểm tra mức đã có hiệu lực trước khi cập nhật; nếu chưa kích hoạt
   thoát thì siết theo Close mới, có hiệu lực nến sau, không bao giờ nới mức.
   risk.trailing bắt đầu từ entry; trailing_after_tp1 chỉ bắt đầu sau phần TP1,
   seed giá khớp TP1 thực tế, không dùng giá target hoặc cực trị đã qua.
   Close chạm/vượt mức thì phát lệnh đóng; lệnh dùng order của hành động đóng
   đúng hướng nếu có, nếu không dùng order cấp request. IMMEDIATE khớp tại Close
   kích hoạt; LO chốt limit rồi chờ tối đa 3 nến/trong ngày. Kích hoạt không đồng
   nghĩa đã khớp; đang có LO đóng chờ thì không tạo lệnh lặp để làm mới thời hạn.
   Đây là quy ước backtest đã duyệt, không phải
   khẳng định HSC bắt buộc mọi trailing dùng Close. Ví dụ trong [bài HSC](https://one.hsc.com.vn/sp/blogs/trailing-stop-la-gi-huong-dan-su-dung)
   dùng giá đóng cửa điều chỉnh và tách giá kích hoạt khỏi giá đặt lệnh.
9. Đang giữ vị thế chỉ xét thoát đúng hướng. Khi phẳng, LONG/SHORT cùng đúng:
   SIGNAL_CONFLICT, không mở. Nến có fill đóng không mở lại tại Close;
   nến sau mới được đánh giá entry, không tự đảo chiều.
10. Qua trưa được giữ vị thế; cuối phiên liên tục, engine tự đóng hết lượng còn giữ
    tại Close thực của nến cuối phiên theo lịch nội bộ có độ phủ (thiếu: CALENDAR_REQUIRED).
    Lịch hiện tại dùng nến mở 14:25, đóng 14:30; không sử dụng giá ATC hoặc Open ngày sau.
    Sau khi xét khớp các lệnh đã chờ trong nến cuối, hủy phần còn chờ với END_OF_DAY,
    đóng lượng còn giữ và ghi signal/order/fill/trade với lý do END_OF_DAY.
    Bước này ưu tiên trước SL/TP/trailing/điều kiện thoát tại Close cuối; không mở mới
    tại Close đó. Không làm mới LO hoặc chờ LO đóng sang ngày sau.
    Thiếu nến để đóng: MISSING_POSITION_EXECUTION_BAR; không lấy nến trước làm giá thay.
    `exit.flat_by` sớm hơn vẫn là hạn bắt buộc riêng: chưa đóng tại mốc đó thì
    REQUIRED_EXIT_NOT_FILLED. Cấu hình v1 đã ghim giữ cách xử lý cũ khi chạy lại.
    Khi lịch có độ phủ phát hiện
    thiếu nến: entry LO chờ bị hủy EXECUTION_DATA_GAP; chỉ báo nguồn đó bị ngắt;
    đang giữ vị thế thì MISSING_POSITION_EXECUTION_BAR. Không lịch thì không
    tuyên bố đã phát hiện đủ nến thiếu của thị trường.
11. Chuyển mã hợp đồng: hủy LO chờ, ngắt chỉ báo trade; market độc lập giữ lịch sử
    nếu không thiếu. Còn vị thế thì OPEN_POSITION_AT_CONTRACT_CHANGE; không đóng
    bằng giá mã khác hoặc tự điều chỉnh giá. Thiếu metadata thì ghi giới hạn nguồn.
12. Close cuối kỳ vẫn được xét khớp ngay nếu điều kiện hợp lệ; entry mới có thể còn
    mở với P&L chưa chốt 0 tại chính Close đó nếu chưa đến cuối phiên. Nếu đã đến
    cuối phiên, áp dụng đóng cuối ngày ở mục 10 và không mở mới. LO mới tạo ở
    Close cuối báo cáo giữa phiên hết hạn END_OF_REPORT vì không còn nến xét.
    Vị thế còn giữ được mark bằng Close cuối, không coi việc dữ liệu dừng giữa phiên
    là bằng chứng hết ngày để đóng vị thế. Thiếu dữ liệu thoát khi giữ
    vị thế là lỗi; thiếu chỉ báo mở khi phẳng là UNEVALUABLE.

Ví dụ cùng một tín hiệu LONG tại Close t=100:

- Khớp ngay: entry 100 tại Close t; bỏ qua High/Low nến t để xét bảo vệ mới.
- LO limit 100: không khớp trong nến t. Nến t+1 Open 98 → entry 98; Open 102,
  Low 99 → entry 100 ghi intrabar; Low 101 → chưa khớp.
- LO tạo sau Close 09:05: xét các nến mở 09:05, 09:10, 09:15; nếu chưa
  khớp thì hủy sau Close 09:20. Nếu ngày kết thúc trước mốc đó thì hủy sớm.
- LONG vào 100, SL 6%=94: Low 93 nhưng Close 97 → chưa thoát; Close 90 →
  thoát 90 (lỗ 10%), không gán giá 94. TP 12%=112: High 115 nhưng Close 110
  → chưa thoát; Close 115 → thoát 115 (lãi 15%), không gán giá 112.

## 3. Request đích và mặc định

`POST /api/backtests` và `POST /api/backtests/validate` nhận cùng JSON.
Ví dụ LONG tối thiểu và ví dụ có TP nhiều mức/trailing bên dưới đã được đường API
mới chấp nhận từ B–D. Các số minh họa không thay ngưỡng CANSLIM.

Payload chỉ giữ lựa chọn khác mặc định. Máy chủ áp dụng profile mặc định đang dùng
ở phiên bản chạy đó; `/validate` và kết quả phải lưu `effective_config`,
`default_profile_version` và `policy_hash` đã giải nghĩa. Vì `SIMULATED/next_open`
cũ không nằm trong API mới, mặc định mới của `order` là `IMMEDIATE` (khớp Close
cùng nến); chỉ cần gửi `order` khi chọn LO. `quantity` bỏ thì là 1. Các trường
accounting/vốn/ký quỹ/sizing cũ không còn được gửi lại hoặc ngầm đưa vào payload.

Không kỳ báo cáo, LONG tối thiểu:

```json
{
  "symbol": "VN30F1M",
  "entry": {
    "long": {
      "left": "price",
      "op": "above",
      "right": "sma20"
    }
  },
  "risk": {
    "sl": 6,
    "tp": 12
  }
}
```

Có kỳ báo cáo, LONG/SHORT, all/any và nguồn thị trường tường minh:

```json
{
  "symbol": "VN30F1M",
  "from": "2026-04-01",
  "to": "2026-09-15",
  "quantity": 3,
  "entry": {
    "long": {
      "all": [
        {
          "left": "market.price",
          "op": "above",
          "right": "market.sma20"
        },
        {
          "ref": "market.mfi14",
          "min": 55,
          "max": 80
        }
      ]
    },
    "short": {
      "all": [
        {
          "left": "market.price",
          "op": "below",
          "right": "market.sma20"
        },
        {
          "ref": "market.mfi14",
          "max": 45
        }
      ]
    }
  },
  "exit": {
    "long": {
      "any": [
        {
          "left": "price",
          "op": "below",
          "right": "sma20"
        },
        {
          "left": "market.price",
          "op": "cross_down",
          "right": "market.sma20"
        }
      ]
    },
    "short": {
      "left": "price",
      "op": "above",
      "right": "sma20"
    }
  },
  "risk": {
    "sl": 6,
    "targets": [
      {
        "quantity": 1,
        "pct": 6
      },
      {
        "quantity": "remaining",
        "pct": 12
      }
    ],
    "trailing_after_tp1": 6
  },
  "order": {
    "type": "LO",
    "limit_price": {
      "ref": "trade_data.close"
    }
  }
}
```

| Trường | Bắt buộc / mặc định | Đơn vị, kiểm tra và lỗi |
| --- | --- | --- |
| `symbol` | Bắt buộc, hiện chỉ VN30F1M | Mã không hỗ trợ: `SYMBOL_UNSUPPORTED` |
| `from/to` | Cùng bỏ hoặc cùng có | Ngày ISO gồm hai đầu, Asia/Ho_Chi_Minh; thiếu một đầu, sai ngày, đảo kỳ hoặc tương lai: `INVALID_REPORT_RANGE`; cùng ngày hợp lệ |
| `entry.long/short` | Ít nhất một hướng | Một điều kiện boolean; không khai báo hướng nào thì không mở hướng đó |
| `exit.long/short` | Tùy chọn | Hướng có entry cần exit cùng hướng hoặc ít nhất một bảo vệ; thiếu: `EXIT_REQUIRED` |
| `order` | Bỏ: IMMEDIATE; khai báo khi chọn LO | type IMMEDIATE hoặc LO; LO bắt buộc limit_price, IMMEDIATE từ chối limit_price/pending; mặc định và tên trường đã duyệt |
| `quantity` | Mặc định 1 | Số nguyên dương, không bool/phân số/chuỗi; `INVALID_QUANTITY` |
| `risk.sl/tp/trailing` | Bỏ nghĩa là tắt từng cơ chế | Phần trăm hữu hạn >0, 6=6%, 0.6=0,6%; số JSON hoặc chuỗi thập phân chính xác; bool, NaN, Infinity sai; `INVALID_RISK` |
| `risk.stop_price` | Nâng cao, loại trừ `sl` | Số/biểu thức giá tuyệt đối tính và ghim ở quyết định; phải nằm phía rủi ro so giá khớp, nếu sai lỗi `INVALID_PROTECTION_LEVEL` trước khi ghi fill |
| `risk.targets` | Nâng cao, loại trừ `tp` | Danh sách có thứ tự tăng không giảm theo khoảng cách có lợi, `pct` hoặc `price` (chỉ một), `quantity` nguyên dương/biểu thức nguyên/`remaining`; `remaining` chỉ ở cuối; tổng không vượt lượng ban đầu |
| `risk.trailing_after_tp1` | Tắt; loại trừ `trailing` | Phần trăm >0, cần `targets`; giữ cách bật sau TP1, không tự bật từ entry |
| `indicators` | Tùy chọn | Khai báo tùy chỉnh theo loại/nguồn/chu kỳ đang có, tên không được đè alias; `UNKNOWN_REF`/`INDICATOR_PARAMETERS_MISMATCH` |
| `warmup_bars` | Tối thiểu máy chủ tính | Nguyên không âm; là ngưỡng bổ sung, không được làm giảm mức cần cho chỉ báo |
| `entry.signal_windows` | Bỏ: không hạn chế giờ | Danh sách cặp HH:MM, UTC+7, hai đầu gồm, tăng dần/không chồng; khớp ngay xét Close quyết định; LO xét signal và Open thực thi cùng ngày/cửa sổ, ngoài cửa sổ hủy entry chờ |
| `daily_limits.stop_new_entry` | Bỏ: không giới hạn bổ sung | Biểu thức boolean trên day.entry_fill_count/day.net_pnl; net_pnl là lãi/lỗ đã chốt trong ngày theo điểm × lượng, không gồm mark chưa chốt; ngày mới đặt lại 0 |
| `exit.flat_by` | Bỏ: không bắt buộc phẳng theo giờ | HH:MM UTC+7; tại mốc vẫn có vị thế thì lỗi REQUIRED_EXIT_NOT_FILLED; không tự sinh fill |
| Chính sách không giữ qua ngày | Cố định phía máy chủ; không cần gửi `exit.allow_overnight` | Ghim allow_overnight=false trong effective_config; không nhận true. Cần lịch nội bộ có độ phủ (thiếu: CALENDAR_REQUIRED); ghim session_end_action=close_at_close, tự đóng tại Close thực cuối phiên, thiếu nến để đóng thì MISSING_POSITION_EXECUTION_BAR |

Quy đổi bảo vệ theo phần trăm (Decimal, không làm tròn tiền): với giá khớp
vào P và r = tham số / 100:

- LONG: stop = P × (1 − r_sl), target = P × (1 + r_tp).
- SHORT: stop = P × (1 + r_sl), target = P × (1 − r_tp).
- Trailing theo quy ước Close ở D07: LONG dùng mốc Close cao nhất kể từ kích
  hoạt × (1 − r_trailing); SHORT dùng mốc Close thấp nhất × (1 + r_trailing).
  Mốc seed là giá khớp khi kích hoạt, mức mới hiệu lực nến sau, không tính từ vốn.
- Không nhận bool/NaN/Infinity hoặc phần trăm <=0. Mức giá tính ra phải hữu hạn,
  dương và đúng phía bảo vệ; sai thì INVALID_PROTECTION_LEVEL, không ép về 0.
- SL/TP/targets.pct lấy giá khớp vào thực tế, kể cả LO được giá Open tốt hơn limit;
  không dùng limit hoặc giá tín hiệu làm gốc. Giá tuyệt đối ở stop_price/targets.price
  vẫn là đường nâng cao riêng, không diễn giải như phần trăm.
- Ví dụ P=1300, sl=6, tp=12: LONG stop 1222 / TP 1456; SHORT stop 1378 / TP 1144.
  Trailing 6% với đỉnh LONG 1400 đặt mức 1316; đáy SHORT 1200 đặt mức 1272,
  chỉ áp dụng nếu mức đó siết có lợi theo D07. Các số này chỉ minh họa.
- D03 chỉ đổi đơn vị bảo vệ; P&L theo chênh lệch giá × lượng ở D02 vẫn là mục
  riêng, không tự đổi toàn bộ kết quả hoặc ngưỡng lỗ ngày thành % vốn.

Đường nâng cao cho mỗi `entry.long/short`: điều kiện trực tiếp như ví dụ, hoặc
`{"condition": <điều kiện>, "order": {"type": "IMMEDIATE"}}` /
`{"condition": <điều kiện>, "order": {"type": "LO", "limit_price": <biểu thức giá>}}`.
Mỗi `exit.long/short` cũng nhận dạng này, thêm quantity nguyên dương/remaining
(mặc định remaining); không đóng vượt lượng đang giữ. order tại hành động ghi đè
order cấp request; bỏ order tại hành động thì dùng order cấp request.
LO limit là số/biểu thức dương hữu hạn, tính một lần ở quyết định. Máy chủ
ghim max_execution_bars=3 và time_in_force=DAY trong effective_config/snapshot,
không cần người dùng gửi trường thời hạn; đây là chính sách cố định D05 đã duyệt.
Không nhận cấu hình bộ khớp phiên hoặc tự đổi loại cũ.
position.held_bars đếm nến entry là 1; điều kiện >=18 tạo lệnh đóng theo cách khớp
đã chọn: khớp ngay tại Close nến 18 hoặc LO chờ nến sau.

Điều kiện ngắn dùng `above` (>), `below` (<), `gte`, `lte`, `cross_up`, `cross_down`.
Giao cắt lên: trái trước <= phải trước và trái nay > phải nay; xuống đối xứng.
Đây là hai mẫu liên tiếp của nguồn được tham chiếu đã khả dụng, không lấy lại cùng
một nến market cho hai phía giao cắt. Thiếu mẫu, mẫu qua gap/chuyển mã: chưa đánh giá được.
Khoảng `min/max` gồm cận, ít nhất một cận, min <= max. all/any không được rỗng.
Giữ biểu thức `ref/shift`, add/sub/mul/div/min/max/floor và so sánh hiện có;
shift nguyên không âm, không shift trạng thái. Không thêm `if`, eval hoặc mã chuỗi.
Giữ tham chiếu OHLCV của trade_data/market_data trong biểu thức (khác với gửi
nguồn ở cấp request), position.entry_price/initial_quantity/held_bars,
day.net_pnl/entry_fill_count, clock.local_time. Tham chiếu position chỉ dùng
sau khi có vị thế; entry không được đọc position hoặc dữ liệu tại Open tương lai.
Giới hạn hiện có: sâu tối đa 32, tối đa 4096 nút mỗi cây điều kiện sau giải alias.

Alias ban đầu: `price`/`market.price` là trade/market Close;
`sma20` (SMA20 Close), `ema5` (EMA5 Close), `bb20_2.middle/upper/lower`,
`macd12_26_9.line/signal/histogram`, `mfi14` (HLCV). Tiền tố `market.` đổi
nguồn sang VNINDEX; không có tiền tố là VN30F1M. HIGHEST/LOWEST và chu kỳ khác
khai báo trong `indicators`; không suy chu kỳ từ chuỗi tùy ý. Histogram=Line−Signal.

Mọi field lạ bị từ chối. `accounting`, `initial_cash`, phí/trượt giá, `execution`,
`strategy` cũ, `report`, `auto_fetch_data`, `trade_data`, `market_data`, `bars`,
`raw`, OHLCV, `file`, đường dẫn, `contract_map`, `price_limits`, đấu giá:
HTTP 422 `LEGACY_OR_DATA_FIELD_NOT_ALLOWED` kèm vị trí trường, không bỏ qua rồi chạy.
Tổ hợp thuộc chức năng ngừng hỗ trợ: `FEATURE_REMOVED`; toán tử chưa có:
`UNSUPPORTED_OPERATOR`; tham chiếu không tồn tại: `UNKNOWN_REF`.

## 4. Nguồn tự động và /validate

- VN30F1M/VNINDEX 5 phút từ VNDIRECT qua bộ lấy hiện có; dữ liệu tham chiếu
  chỉ dùng khi đã khả dụng. Không thêm nguồn hoặc API nhập nến/file công khai.
- Không kỳ: sáu tháng lịch gần nhất đến lúc lấy như `fetch()`; không tự mở rộng
  để đủ mẫu. Có kỳ: `fetch_by_range()` lùi lịch sử đủ cho chỉ báo/shift/giao cắt,
  giữ đúng kỳ giao dịch; chỉ giữ nến `Open + 300 <= min(hết ngày to, hiện tại)`.
- MFI cần period+1; MACD Signal/Histogram cần slow+signal−1; biểu thức shift và
  giao cắt cộng lịch sử tương ứng. Ngưỡng bổ sung dùng max, CANSLIM vẫn là 150.
  Trước kỳ chỉ khởi tạo, không tạo tín hiệu/lệnh/fill; sau kỳ không chạy.
- Giữ kiểm tra OHLCV hữu hạn, thứ tự/không chồng timestamp, volume khi cần;
  primary `available_at == Close`, market được trễ. Dùng lịch/bảng mã nội bộ
  đã có khi có độ phủ, độc lập accounting. Giữ bản ghi nguồn; bản ghi đấu giá
  đã được nhận diện tách khỏi chuỗi chỉ báo/khớp lệnh, không đổi thành nến liên tục.
- Nến thiếu giữ nguyên. Kỳ không có nến: 422 `REPORT_DATA_MISSING`; thiếu một
  phần kỳ vẫn giữ kỳ yêu cầu, trả `available_range` và cảnh báo. Lỗi mạng/nguồn:
  503 `AUTO_FETCH_NETWORK_ERROR`/`AUTO_FETCH_HTTP_ERROR`; dữ liệu sai: 422
  `AUTO_FETCH_INVALID_SOURCE`; không dùng file thay hoặc lặp tải bù để che lỗi.
- `/validate` trả 200 với `valid`, `payload` chỉ cấu hình hợp lệ, `effective_config`,
  `data_metadata`, `warnings`; không tạo run, không ghi kho, không trả nến để gửi lại.
  Gồm cách khớp từng hành động, giả định cùng Close nếu chọn khớp ngay, limit và chính sách 3 nến/DAY
  chỉ khi LO, alias đã giải, số mẫu cần, đơn vị và quy ước mục 2.
  Chạy lấy snapshot của chính lần gọi; không hứa giống snapshot lần validate.

## 5. Response đích và lưu trữ

Kết quả mới dùng `schema_version: 3`, snapshot nội bộ `schema_version: 2`;
phiên bản do máy chủ ghi. HTTP 201 chỉ sau khi công bố nguyên tử thành công.
Ví dụ phần tóm tắt LONG mở 3 tại 100, đóng 1 tại 106, còn 2, Close cuối 103:

```json
{
  "schema_version": 3,
  "summary": {
    "pnl_unit": "point_quantity", "realized_pnl": "6", "unrealized_pnl": "6", "total_pnl": "12",
    "max_drawdown": "6", "closed_positions": 0, "open_positions": 1,
    "winning_positions": 0, "losing_positions": 0, "breakeven_positions": 0, "win_rate": null
  },
  "open_position": {"position_id": "p1", "direction": "LONG", "entry_price": "100", "initial_quantity": 3, "remaining_quantity": 2},
  "pnl_history": [
    {"time": "2026-04-01T09:00:00+07:00", "realized_pnl": "0", "unrealized_pnl": "0", "total_pnl": "0"},
    {"time": "2026-04-01T09:10:00+07:00", "realized_pnl": "6", "unrealized_pnl": "12", "total_pnl": "18"},
    {"time": "2026-04-01T09:15:00+07:00", "realized_pnl": "6", "unrealized_pnl": "6", "total_pnl": "12"}
  ]
}
```

Đây là trích đoạn minh họa, không phải toàn bộ response. Response đầy đủ bắt buộc:

| Nhóm | Nội dung |
| --- | --- |
| `metadata` | run_id, run_at, symbol, timezone, report_range, available_range, input_hash, policy_hash, nguồn/URL/raw_hash/fetched_at, phiên bản bộ chạy và giả định hiệu lực |
| `evaluations` | decision_time, hướng/điều kiện, EVALUABLE/UNEVALUABLE, lý do thiếu mẫu/xung đột |
| `signals` | signal_id, decision_time, hướng, hành động mở/đóng, nguyên nhân |
| `orders` | order_id, signal_id, position_id khi có, cách khớp IMMEDIATE/LO, quantity, thời điểm tạo/khớp; riêng LO có limit và thời hạn; trạng thái/lý do |
| `fills` | fill_id, order_id, position_id, hướng mua/bán, quantity, price, fill_time, fill_phase và nguồn nến |
| `trades` | Mỗi phần đóng: position_id, liên kết fill mở/đóng, giá/lượng, realized_pnl, lý do |
| `open_position` | null hoặc một vị thế còn lượng; các mức bảo vệ có hiệu lực |
| `summary`, `pnl_history` | Các trường như ví dụ, lịch sử từng Close trong kỳ, mốc đầu 0; không có equity/vốn giả |

Lãi/lỗ phần đóng = sign × (giá đóng − giá mở) × lượng đóng; phần chưa chốt =
sign × (Close cuối − giá mở) × lượng còn lại; sign LONG=1, SHORT=−1.
Drawdown là đỉnh total_pnl đã biết (gồm mốc 0) trừ total_pnl hiện tại;
max_drawdown là giá trị lớn nhất, đơn vị điểm × lượng, không phần trăm/VND.
Giá/P&L JSON là chuỗi thập phân không làm tròn tiền; quantity/count là số nguyên.
win_rate = số vị thế lãi / số vị thế đã đóng hết, dạng tỷ lệ 0..1; hòa vốn vẫn
trong mẫu số, vị thế chưa đóng hết không tính. Mẫu số 0 trả null; không có
giao dịch thì P&L và drawdown bằng 0, count 0, open_position null.

Snapshot lưu request gốc, dữ liệu chuẩn hóa, alias đã giải, chính sách và metadata.
Giữ mã băm, kiểm tra toàn vẹn, ghi nguyên tử và trạng thái lỗi hiện có.
Chạy lại nội bộ chỉ dùng snapshot đã ghim, không tải mạng/gọi LLM.
GET lịch sử/input/chart cùng run, phân biệt schema 1/2 cũ với schema 3 mới;
không đổi tên tỷ suất cũ thành điểm hoặc cộng các đơn vị. Lọc/sắp xếp mới theo
realized_pnl/total_pnl/max_drawdown/closed_positions và đơn vị; không tính lại bản cũ.

## 6. Kiểm kê và thay đổi bắt buộc của CANSLIM

| Khả năng | Xử lý trên đường mới |
| --- | --- |
| Chỉ báo, nguồn tách biệt, shift, all/any, cây số học | Giữ, thêm alias và so sánh ngắn, không thêm chỉ báo ngoài danh mục hiện có |
| LONG/SHORT, một vị thế, TP nhiều mức/đóng từng phần, SL/trailing | Chuyển sang sổ vị thế theo điểm, giữ liên kết từng phần đóng |
| Nhiều lần mở, nhiều position_id đồng thời, partial fill do ngân sách | Ngừng nhận mới; hai cách khớp lý tưởng đều khớp đủ lượng khi đủ điều kiện, không mô phỏng đối ứng |
| ATO/ATC/MTL/MOK/MAK/SIMULATED, HNX matching tùy chọn | Ngừng nhận mới, lịch sử vẫn xem theo đơn vị/loại gốc |
| Vốn, ký quỹ, margin breach, phí/thuế, % vốn, sizing theo tài khoản | Ngừng nhận mới, không thay bằng số vốn/hệ số giả |
| Nhập dữ liệu/file, nạp payload đầy đủ, cờ tự lấy | Ngừng nhận mới ở cả API/web; snapshot nội bộ vẫn giữ để kiểm chứng |
| Điều kiện giờ, thời gian giữ, số entry/ngày, điều kiện thoát | Giữ biểu thức nâng cao qua clock.local_time, position.held_bars, day.entry_fill_count; lượng mặc định exit là remaining |
| day.net_pnl | Đổi sang điểm × lượng trên đường mới, tài liệu chuyển đổi phải yêu cầu xác nhận ngưỡng điểm; không dùng ngưỡng % vốn cũ |
| account.equity/required_margin, day.start_equity | Từ chối, không alias sang điểm |

CANSLIM: giữ nguyên R01 trên VNINDEX, MFI55/45, BB khoảng 3, MACD Line,
150 nến, tối đa 18 nến, tối đa 3 entry/ngày và khung giờ đã có.
Bản CANSLIM cũ dùng SL 6 điểm, TP 6/12 điểm và trailing 6 điểm sau TP1; đây
là ngưỡng lịch sử để đối chiếu, không tự chuyển thành 6%/12%. Theo D03 mới,
mẫu bảo vệ dùng % cần chốt bộ ngưỡng chuyển đổi riêng ở T19; không suy từ một
giá ví dụ để áp dụng cho mọi entry hoặc tuyên bố tương đương bản cũ. Không tự chọn quantity theo sizing cũ: người dùng khai báo
quantity cố định. TP1: lượng 1 đóng hết; lượng >=2 dùng floor(initial_quantity/2),
TP2 remaining; cấu hình mẫu theo từng quantity, không tạo phần đóng lượng 0.

Những khác biệt bắt buộc phải ghi khi chuyển mẫu ở T19: bỏ risk 1%/ký quỹ17%/
buffer1,10/hệ số100000/chi phí/vốn100 triệu, margin breach và ngưỡng lỗ ngày
−2% vốn; không suy ra một ngưỡng điểm thay thế. Đóng do time-stop/forced exit
phải khai báo rõ cách khớp: IMMEDIATE đóng ngay tại Close ra tín hiệu, LO có thể
chưa khớp. Đây là khác biệt với Open nến sau của bản cũ; nếu flat_by mà chưa
đóng thì REQUIRED_EXIT_NOT_FILLED, không tạo fill giả. Pending entry LO CANSLIM
vẫn phải bị cấm qua trưa/cutoff bằng điều kiện giờ của mẫu, không biến thành
quy tắc mặc định mọi chiến lược. Quy ước entry tại Close, LO intrabar và SL/TP
chỉ xét/thoát theo Close ở mục 2 cũng là khác biệt so với bảo vệ OHLC bản cũ.
Mẫu chuyển đổi không được gọi tương đương tiền hoặc hành vi bản v1 cũ.

## 7. Bằng chứng và phần chưa triển khai

[Mốc kiểm thử A](../testing/price-only-baseline.md) ghi source commit, lỗi hiện có,
hash lịch sử và dữ liệu thực có. [Fixture tính tay](../../tests/fixtures/price-only-cases.json)
là dữ liệu tổng hợp phục vụ kiểm thử nội bộ, không phải nguồn thị trường.
B–D đã có bộ chạy theo điểm, khớp ngay/LO, toàn bộ bảo vệ đã duyệt,
nguồn tự lấy, lưu/đọc schema 3, lịch sử hỗn hợp và giao diện chỉ cấu hình.
[Báo cáo C–D](../testing/price-only-cd.md) ghi kiểm thử API, danh mục tham số và trình duyệt thực.
`GET /api/strategy-parameters` là danh mục từ cùng schema/alias/toán tử đang dùng;
có ví dụ hợp lệ cho khớp ngay và LO. POST và validate từ chối cấu trúc accounting/dữ liệu cũ.
E còn LLM; F còn notebook/ví dụ, dọn đường cũ và tài liệu, nghiệm thu thị trường thật.
Chưa công bố bản chuyển đổi hoàn tất. Không tự chuyển ngưỡng CANSLIM cũ sang %.
LLM không phải điều kiện chặn B–D.
