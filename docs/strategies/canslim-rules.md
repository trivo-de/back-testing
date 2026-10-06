# Công thức nền CANSLIM — normalized

Đây là đặc tả công thức nền dùng đối chiếu kết quả normalized lịch sử và cây
JSON tương đương. Các giá trị quy tắc bên dưới giữ nguyên. Yêu cầu chạy cung
cấp chỉ báo, điều kiện và sizing trong strategy JSON theo
[hướng dẫn payload](../design/strategy-payload-guide.md), không chọn bộ chạy
bằng ID hoặc gửi strategy_params riêng.

Mapping VN30F1M đã chốt cho công thức nền: R1 dùng 200 mẫu VNINDEX đã khả dụng;
R2 dùng 65 nến giao dịch trước t; R3 dùng volume nến t so với 50 nến trước t.
Signal sau Close, khớp tại Open hợp lệ kế tiếp; không fallback daily hoặc điền
nến thiếu. Policy/run lịch sử giữ nguyên; quy tắc v1 riêng tại
[CANSLIM v1](canslim-v1-rules.md).

## Đặc tả công thức nền

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

## Các trường hợp biên và không áp dụng

Bảng này là nơi tra cứu tập trung cho các tình huống không tạo ra kết quả giao dịch
bình thường. Công thức chi tiết vẫn nằm ở mục rule tương ứng; các mã `V0-EX-*`
dùng làm tham chiếu khi bổ sung test.

| Case ID | Điều kiện | Kết quả bắt buộc |
| --- | --- | --- |
| `V0-EX-01` | Thiếu bar, indicator hoặc dữ liệu VN-Index cần tại `t`, hoặc chưa đủ warm-up | Điều kiện liên quan là `UNEVALUABLE`; không coi là đạt, không tạo BUY và không tự lùi kỳ báo cáo. |
| `V0-EX-02` | R1 bằng SMA; depth vượt giới hạn; breakout nằm ngoài buy zone; average volume không dương; volume không đạt ngưỡng | Điều kiện không đạt; không tạo BUY. Không làm tròn hoặc thay ngưỡng để cho qua. |
| `V0-EX-03` | Đang có vị thế hoặc lệnh chờ tại thời điểm xét R4 | Không tạo tín hiệu vào mới; không mở thêm vị thế. |
| `V0-EX-04` | Có signal nhưng không có Open phiên kế tiếp hoặc bar thực thi hợp lệ | Giữ record pending/unfilled theo execution contract; không tạo fill giả. |
| `V0-EX-05` | `quantity < 1` sau khi tính theo risk và khả năng chi trả | Giữ BUY signal, từ chối order/fill và ghi lý do; không sửa quantity sau khi tạo order. |
| `V0-EX-06` | `initial_cash <= 0`, `fee_rate < 0` hoặc `slippage_rate` ngoài `[0, 1)` | Từ chối input; không chạy chiến lược. |
| `V0-EX-07` | VN30F1M thiếu expected bar, session label hoặc rollover map cần thiết | Validation thất bại; không nội suy, không tự điền và không tự đóng vị thế. Quyết định giữ/đóng tại đáo hạn lấy từ runtime policy hiện hành. |
| `V0-EX-08` | STOP_LOSS và TAKE_PROFIT cùng đạt trong cùng nến; stop/exit khớp ở Open kế tiếp | Ưu tiên STOP_LOSS, bán toàn bộ; gap có thể làm lỗ thực tế vượt tỷ lệ stop/risk budget. |

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

## CANSLIM normalized (condensed)

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
