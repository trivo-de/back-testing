> **Xác nhận 17/09/2026:** User chốt giữ rule CANSLIM, dùng VN30F1M thay HPG,
> giữ VN-Index cho R1 và mô hình tiền normalized như baseline.
> **Cập nhật 18/09:** strategy/execution chính dùng 5 phút, 1D chỉ hỗ trợ.
> C01–C03 đã chốt window 200/65/50 nến 5 phút; C04 chốt Close/available_at
> = Open + 5 phút, kể cả ATC. Map tham khảo được user cho phép, giữ vị thế.
> Source intraday đã implement/test fixture; report thật còn thiếu history.
> Xem [plan hiện hành](../plans/technical-plan.md).

## Mapping đã xác nhận trong checklist — 18/09

Refactor R1–R2 (21/09) giữ mọi công thức/threshold bên dưới. Snapshot indicator,
fixed fractional sizing 2%/stop 7% và entry pivot thuộc module CANSLIM. Pivot
đi theo pending intent; chỉ thành state vị thế sau BUY fill, BUY reject không
giữ pivot, SELL fill mới xóa state. State mới cho mỗi run. Stop reference được
strategy xác định từ giá fill; mapper chỉ xuất projection tương thích, không
tính lại. Ledger không sở hữu pivot/stop; quantity vẫn tính tại Open execution
sau slippage, cash trước fill và fee như baseline.

- R1: VN-Index 5 phút, SMA200 dùng 200 nến liên tục qua phiên; thiếu lịch sử
  thì UNEVALUABLE, không fallback daily.
- R2: pivot/base-low theo 65 nến 5 phút trước t, không gồm t.
- R3: volume riêng nến t đã đóng, so với trung bình cộng 50 nến trước t;
  average > 0, volume[t] >= 1.50 * average. Không reset đầu ngày, không fill.
- Đây là thay đổi đơn vị window so với baseline daily được user xác nhận;
  các con số, công thức và thresholds giữ nguyên. Daily specification bên dưới
  chỉ là baseline lịch sử. C04 nay chốt Open + 5 phút như assumption mô phỏng.
- C05: giữ vị thế/pending qua nghỉ trưa/qua đêm; fill tại Open bar hợp lệ
  đầu tiên khi mở lại. Missing expected bar hoặc thiếu static rollover map
  cho bất kỳ đoạn nào phải fail validation; không nội suy hay tự đóng vị thế.
- User xác nhận thêm 18/09: cho phép dùng lịch/mã tham khảo của
  [static map](../data/vn30f1m/vn30f1m-rollover-map.md) làm assumption mô phỏng;
  **giữ vị thế/pending qua đáo hạn**, không forced exit hoặc price adjustment.

## Quyết định áp dụng VN30F1M — 17/09/2026

- Giữ R1–R4, công thức indicator, các window/threshold, long-only, một vị thế,
  không vay/pyramiding, stop 7%, target 20% và risk budget 2% như baseline bên dưới.
- R1 tiếp tục dùng VN-Index Close và SMA200 của VN-Index. Không thay market
  series bằng VN30 hoặc VN30F1M, không bỏ R1 khi thiếu dữ liệu.
- Giữ công thức sizing, cash, fees, realized/unrealized P/L và equity cũ.
  Config báo cáo vẫn là initial_cash 10.000.000, fee_rate 0.001,
  slippage_rate 0.002. Quantity là đơn vị mô phỏng theo giá nguồn; kết quả mang
  nhãn `normalized simulation`, không diễn giải thành số hợp đồng hay P/L futures
  thực tế. Không thêm multiplier, margin, thuế hoặc settlement phái sinh.
- Giữ nguyên nguyên tắc signal sau Close, fill ở Open kế tiếp. Định nghĩa bar/
  phiên hợp lệ trên VN30F1M còn chờ chốt; timeframe chính đã chọn 5 phút ngày 18/09.
- Các window 200/65/50 baseline là phiên ngày; C01–C03 đã xác nhận chuyển
  đơn vị sang nến 5 phút như mapping bên trên. Chưa duyệt daily aggregation.
- Snapshot VN-Index phù hợp kỳ chạy, warm-up, session/timestamp và cách xử lý
  chuỗi VN30F1M qua rollover còn cần đặc tả. Thiếu input thì không đánh giá được;
  không tự fetch nguồn bổ sung hoặc fill dữ liệu để tạo giao dịch.

Phần VIE/ENG dưới đây giữ đặc tả HPG daily làm baseline công thức. Contract nguồn
VN30F1M và đề xuất aggregation chưa duyệt nằm tại
[VN30F1M Data Contract](../data/vn30f1m/data-contract.md).

Confirmed scope: retain CANSLIM rules, VN-Index R1 and baseline normalized
accounting when replacing HPG with VN30F1M. As of 18/09, evaluation/execution
use 5-minute bars; daily data is auxiliary only. Window units, volume mapping,
Open/Close availability uses the approved five-minute simulation convention;
rollover retains positions under the user-approved reference map. The daily HPG specification
below is the formula baseline, not an implemented intraday specification.

VIE

# CANSLIM Rule — canslim_breakout_v0

## 1. Khái niệm

- C — Current quarterly earnings: lợi nhuận/EPS quý hiện tại.
- A — Annual earnings growth: tăng trưởng lợi nhuận/EPS hằng năm.
- N — New: yếu tố mới như sản phẩm, lãnh đạo hoặc mức giá cao mới.
- S — Supply and demand: cung và cầu.
- L — Leader or laggard: cổ phiếu dẫn dắt hay tụt lại.
- I — Institutional sponsorship: sự tham gia của nhà đầu tư tổ chức.
- M — Market direction: xu hướng thị trường chung.
- Filter: điều kiện cho phép cân nhắc mua; chưa phải lệnh mua.
- Base / pivot / breakout: vùng nền / điểm tham chiếu mua / sự vượt nền.
- Signal / fill: tín hiệu / giao dịch khớp trong mô phỏng.
- Stop loss / take profit: cắt lỗ / chốt lời.

## 2. Phạm vi

- HPG, nến ngày, long-only, một vị thế; không vay hoặc mua thêm khi đang giữ.
- Dữ liệu: OHLCV HPG và Close VN-Index (dùng cho điều kiện M).
- Chỉ dùng bar ngày đã hoàn tất tại thời điểm ra quyết định. Thiếu dữ liệu
  cần thiết tại `t` thì điều kiện liên quan không đánh giá được, không coi là đạt.
- Input daily snapshot, warm-up và kỳ báo cáo tuân theo
  [data-contract.md](../data/hpg/data-contract.md); strategy không sở hữu endpoint hoặc data
  provenance.

## 3. Điều kiện vào lệnh — tính sau Close phiên t

t-1 là phiên giao dịch trước (không phải ngày lịch). Chỉ dùng thông tin có
tới Close phiên `t`.

- **R1 — Thị trường (M):** `index_close[t] > SMA200(index_close)[t]`. Bằng SMA thì không đạt.
- **R2 — Nền giá (N):** `pivot = max(high, BASE_WINDOW phiên trước t)`;
  `base_low = min(low, cùng cửa sổ)`; `depth = (pivot - base_low)/pivot <= MAX_BASE_DEPTH`.
- **R3 — Breakout & khối lượng (S):** `avg_volume = trung bình volume, VOLUME_WINDOW phiên trước t` (phải > 0);
  yêu cầu `pivot < close[t] <= pivot * BUY_ZONE_MULT` AND `volume[t] >= VOLUME_MULT * avg_volume`.
- **R4 — Tín hiệu BUY:** R1 AND R2 AND R3, đang không giữ vị thế và không có lệnh chờ.
  Lưu `pivot` của tín hiệu để làm mốc chốt lời cố định cho vị thế.
- **Khớp lệnh:** signal sau Close[t] → khớp tại Open phiên kế tiếp (không khớp tại
  chính Close vừa tạo signal). `buy_fill = Open * (1 + slippage_rate)`.

## 4. Điều kiện ra lệnh — khi đang giữ vị thế

- **STOP_LOSS:** `close[t] <= entry_fill_price * (1 - STOP_LOSS_PCT)` (entry_fill_price là giá khớp mua, chưa gồm phí).
- **TAKE_PROFIT:** `close[t] >= entry_pivot * (1 + TAKE_PROFIT_PCT)` (dùng pivot lúc mua, giữ cố định).
- Ưu tiên STOP_LOSS nếu cả hai cùng đạt; bán toàn bộ vị thế.
- Khớp tại Open phiên kế tiếp: `sell_fill = Open * (1 - slippage_rate)`. Vì stop tính
  theo Close và khớp phiên sau, lỗ thực tế có thể vượt STOP_LOSS_PCT (không phải stop
  order khớp ngay trong phiên).

## 5. Quản lý vốn

- **Position sizing [P]: Fixed fractional risk** với
  `RISK_PER_TRADE_PCT = 2%`. Đây là giá trị cố định của strategy v0, không phải
  tham số được tự tối ưu theo kết quả backtest.
- Tại Open phiên execution, sau khi biết `entry_fill_price`:
  - `risk_budget = equity_before_fill * RISK_PER_TRADE_PCT`.
  - `stop_reference = entry_fill_price * (1 - STOP_LOSS_PCT)`.
  - `risk_per_share = entry_fill_price - stop_reference`.
  - `risk_quantity = floor(risk_budget / risk_per_share)`.
  - `affordable_quantity = floor(cash_before_fill / (entry_fill_price * (1 + fee_rate)))`.
  - `quantity = min(risk_quantity, affordable_quantity)`.
- Vì BUY chỉ được tạo khi đang flat và v0 không có nạp/rút vốn giữa signal và fill,
  `equity_before_fill = cash_before_fill`. Vẫn lưu cả hai field để công thức không
  phụ thuộc ngầm vào ràng buộc một vị thế nếu engine được mở rộng sau này.
- Nếu `quantity < 1`, giữ nguyên BUY signal nhưng từ chối order/fill và ghi lý do;
  không sửa quantity sau khi order đã được tạo.
- `initial_cash > 0`; `fee_rate >= 0`; `0 <= slippage_rate < 1`.
  Phí mỗi chiều = `quantity * giá khớp chiều đó * fee_rate`.
- `risk_budget` là mức lỗ giá danh nghĩa tới stop reference, chưa gồm phí và gap ở
  phiên thoát. Vì exit signal tính theo Close và khớp tại Open phiên sau, realized
  loss vẫn có thể vượt `RISK_PER_TRADE_PCT`.

## 6. Bảng tham số

| Tham số                | Giá trị   | Dùng ở       |
| ----------------------- | ----------- | -------------- |
| SMA_WINDOW              | 200 phiên  | R1             |
| BASE_WINDOW             | 65 phiên   | R2             |
| MAX_BASE_DEPTH          | 35%         | R2             |
| VOLUME_WINDOW           | 50 phiên   | R3             |
| VOLUME_MULT             | 1.50x       | R3             |
| BUY_ZONE_MULT           | 1.05x pivot | R3             |
| STOP_LOSS_PCT           | 7%          | Exit           |
| TAKE_PROFIT_PCT         | 20%         | Exit           |
| RISK_PER_TRADE_PCT      | 2%          | Quản lý vốn |
| initial_cash (MVP report) | 10.000.000 VND | Portfolio |
| fee_rate (MVP report)   | 0.001       | Khớp lệnh    |
| slippage_rate (MVP report) | 0.002     | Khớp lệnh    |
| fee_rate (fixture)      | 0.001       | Khớp lệnh    |
| slippage_rate (fixture) | 0           | Khớp lệnh    |

ENG

# CAN SLIM — canslim_breakout_v0 (condensed)

## 1. Terms

- C: Current quarterly earnings; A: Annual earnings growth; N: New.
- S: Supply and demand; L: Leader or laggard; I: Institutional sponsorship; M: Market direction.
- Filter: permission to consider an entry, not an order itself.
- Base/pivot/breakout: reference range/entry reference/exceeding that range.
- Signal/fill: trading decision/executed simulated trade.
- Stop loss/take profit: exit conditions for losses/gains.

## 2. Scope

- Daily HPG, long-only, one position, no borrowing or additional entries.
- Data: HPG OHLCV and VN-Index Close (used for the M condition).
- Use only completed daily bars at decision time. A missing required input at `t`
  makes the relevant condition unevaluable, never treated as passed.
- Daily input snapshots, warm-up, provenance, and adjusted-data limitations follow
  [data-contract.md](../data/hpg/data-contract.md); the strategy does not own data endpoints or
  source policy.

## 3. Entry rules — after Close of session t

t-1 is the prior trading session (not calendar day). Use only information
available up to Close of session `t`.

- **R1 (Market):** `index_close[t] > SMA200(index_close)[t]`. Equality fails.
- **R2 (Base):** `pivot = max(high, BASE_WINDOW sessions before t)`;
  `base_low = min(low, same window)`; `depth = (pivot - base_low)/pivot <= MAX_BASE_DEPTH`.
- **R3 (Breakout & volume):** `avg_volume = mean volume, VOLUME_WINDOW sessions before t` (must be > 0);
  require `pivot < close[t] <= pivot * BUY_ZONE_MULT` AND `volume[t] >= VOLUME_MULT * avg_volume`.
- **R4 (BUY signal):** R1 AND R2 AND R3, no open position and no pending order.
  Store the signal's `pivot` as the fixed profit-target reference.
- **Execution:** signal after Close[t] → fill at the next session's Open (never at the
  same Close that generated the signal). `buy_fill = Open * (1 + slippage_rate)`.

## 4. Exit rules — while holding a position

- **STOP_LOSS:** `close[t] <= entry_fill_price * (1 - STOP_LOSS_PCT)` (entry price excludes fees).
- **TAKE_PROFIT:** `close[t] >= entry_pivot * (1 + TAKE_PROFIT_PCT)` (pivot fixed at entry).
- STOP_LOSS takes priority if both trigger; exit the full position.
- Fill at the next session's Open: `sell_fill = Open * (1 - slippage_rate)`. Because the
  stop is Close-based and fills the following session, realized loss can exceed
  STOP_LOSS_PCT — this is not an intraday stop order.

## 5. Capital management

- **Position sizing [P]: Fixed fractional risk** with
  `RISK_PER_TRADE_PCT = 2%`. This is fixed for strategy v0 and must not be
  optimized against backtest results.
- At the execution session's Open, after `entry_fill_price` is known:
  - `risk_budget = equity_before_fill * RISK_PER_TRADE_PCT`.
  - `stop_reference = entry_fill_price * (1 - STOP_LOSS_PCT)`.
  - `risk_per_share = entry_fill_price - stop_reference`.
  - `risk_quantity = floor(risk_budget / risk_per_share)`.
  - `affordable_quantity = floor(cash_before_fill / (entry_fill_price * (1 + fee_rate)))`.
  - `quantity = min(risk_quantity, affordable_quantity)`.
- A BUY is generated only while flat and v0 has no cash flows between signal and
  fill, so `equity_before_fill = cash_before_fill`. Keep both fields explicit so
  the formula does not silently depend on the one-position constraint if the
  engine is extended later.
- If `quantity < 1`, retain the BUY signal but reject the order/fill with a reason;
  never mutate quantity after the order has been created.
- `initial_cash > 0`; `fee_rate >= 0`; `0 <= slippage_rate < 1`.
  Fee per side = `quantity * that side's fill price * fee_rate`.
- `risk_budget` represents nominal price loss to the stop reference and excludes
  fees and an exit gap. Because the exit signal is evaluated at Close and filled
  at the following Open, realized loss can still exceed `RISK_PER_TRADE_PCT`.

## 6. Parameter table

| Parameter               | Value        | Used in            |
| ----------------------- | ------------ | ------------------ |
| SMA_WINDOW              | 200 sessions | R1                 |
| BASE_WINDOW             | 65 sessions  | R2                 |
| MAX_BASE_DEPTH          | 35%          | R2                 |
| VOLUME_WINDOW           | 50 sessions  | R3                 |
| VOLUME_MULT             | 1.50x        | R3                 |
| BUY_ZONE_MULT           | 1.05x pivot  | R3                 |
| STOP_LOSS_PCT           | 7%           | Exit               |
| TAKE_PROFIT_PCT         | 20%          | Exit               |
| RISK_PER_TRADE_PCT      | 2%           | Capital management |
| initial_cash (MVP report) | VND 10,000,000 | Portfolio       |
| fee_rate (MVP report)   | 0.001        | Execution          |
| slippage_rate (MVP report) | 0.002      | Execution          |
| fee_rate (fixture)      | 0.001        | Execution          |
| slippage_rate (fixture) | 0            | Execution          |
