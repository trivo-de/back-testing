# Web UI Specification — Backtest HPG v0 (legacy baseline)

> **Storage 18/09/2026:** [Parquet + JSON](../plans/technical-plan.md#6-persistence-parquet-json) thay target pickle trong kế hoạch bên dưới. Raw nguồn giữ nguyên; SQLite/PostgreSQL cho metadata/session agent còn chờ chốt. Nội dung implementation/mốc cũ giữ để truy vết; chưa migrate code hoặc nghiệm thu storage mới.


**Yêu cầu 17/09:** quay lại HPG cũ để show kết quả backtest trên chart. Trang chủ
của app có BacktestService mở run HPG gần nhất; nến/volume lấy qua
`GET /api/backtests/{run_id}/chart`, markers/equity từ result cùng run. Chọn fill
để zoom và xem detail; chart VN30F1M snapshot vẫn ở `/market-chart`. Đây là scope
demo được user chọn, không phê duyệt adaptation CANSLIM cho VN30F1M.

**Bổ sung 17/09:** `canslim_breakout_v0` dùng điều kiện thị trường
`VNINDEX Close > SMA200(VNINDEX)`. Chart HPG hiển thị panel riêng VN-Index Close
(xám) và SMA200 (cam), tính server-side từ đúng dataset version của run, gồm
warm-up trước kỳ báo cáo. Không overlay SMA200 này lên giá HPG và frontend không
tự tính indicator.

> Target 18/09: VN30F1M 5 phút, CANSLIM/long-only/normalized baseline; indicator
> mapping và session chờ [C01–C06](../../.agents/checklists/vn30f1m-backtest-checklist.md).
> API + notebook là ưu tiên, chưa cần agent. Marker chỉ từ executed fills;
> storage target là Parquet + JSON. Nội dung HPG daily dưới giữ làm baseline cũ.

Cập nhật: 15/09/2026.

## 1. Mục tiêu

Web UI cho phép người dùng chạy một backtest và xem kết quả của cùng một run. UI
không triển khai lại strategy, execution hoặc accounting logic.

## 2. Phạm vi theo phase

### UI tối thiểu — làm sau khi core/API ổn định

- Form cấu hình run.
- Summary P/L và equity.
- Danh sách fills.
- Lịch sử closed trades.
- Open position cuối kỳ.
- Audit signals và rejected/unfilled orders.
- Run ID, dataset version/hash và strategy parameters.
- Danh sách các run đã lưu và khả năng mở lại kết quả sau service restart.

### Chart tối thiểu — ưu tiên cho đợt push Docker + notebook + chart

Quyết định 15/09: kéo P3.1 (nến) và phần marker P3.3 lên trước Phase 2.
Implementation chưa bắt đầu. [Kế hoạch triển khai](../plans/candlestick-ui-plan.md).

- Candlestick VN30F1M 5 phút trong khoảng thời gian của run, có zoom/scroll và fit view.
- Mỗi executed fill có marker BUY/SELL tại đúng `fill_time` và `fill_price`.
- Phân biệt BUY/SELL bằng chữ và hình dạng, kèm màu; có chú giải.
- Hover/click marker xem ngày, giá khớp, quantity, fee, signal time và reason.
- Giữ bảng fills để tra cứu bằng bàn phím và đối chiếu với chart.
- Volume histogram lấy trực tiếp từ OHLCV, chung trục ngày với nến.
- Equity line riêng lấy từ equity_history; giữ bảng equity và summary hiện có.
- Bảng trades bổ sung entry_price, exit_price và fees đã có trong response.

### Phần Phase 3 còn lại theo baseline

- Indicator overlays/panels; trade return chưa có field/quy ước backend.
- Tương tác chart nâng cao và đồng bộ zoom/crosshair giữa nhiều chart.

## 3. Mapping dữ liệu

| UI component | Backend source | Quy tắc |
| --- | --- | --- |
| Summary cards | `summary` | Không tính lại ở frontend |
| Equity table/line | `equity_history` | Một điểm tại Close mỗi phiên |
| Fill table | `fills` | Hiển thị đúng fill time/price |
| Trade table | `trades` | Chỉ giao dịch đã đóng |
| Open position | `open_position` | Hiển thị unrealized P/L riêng |
| Audit table | `signals` + `orders` | Phân biệt pending/rejected/filled |
| Run history | persisted `backtest_runs` | List/filter và mở lại theo `run_id` |
| Candlestick Phase 3 | OHLCV snapshot của run | Không fetch live dataset khác |
| Marker Phase 3 | `fills` | Không dùng signal làm executed marker |
| Volume histogram | OHLCV `volume` | Cùng ngày với nến, không tự fill dữ liệu |
| Equity line | `equity_history` | Lấy equity backend, không tính lại cash/position |

## 4. Trạng thái giao diện

- **Initial:** chưa chạy, hiển thị form và required input.
- **Loading:** ngăn chạy request trùng.
- **Success with trades:** hiển thị summary, fills, trades và equity.
- **Success without trades:** kết quả hợp lệ; trade/fill table rỗng có giải thích.
- **Open position:** hiển thị unrealized P/L; không tạo SELL giả cuối kỳ.
- **Validation error:** hiển thị field/code/message từ API.
- **Data/internal error:** không render số liệu một phần như kết quả thành công.

Nếu POST đã thành công nhưng chart GET lỗi, Thử lại chỉ tải result/chart theo
run ID đó. Lỗi history hiển thị riêng, không làm mất kết quả hiện tại. Controller
giữ request sequence ID để bỏ response đến muộn; hủy HTTP không coi là hủy run
trong backend. Loading phải ngăn submit trùng và hide/xóa kết quả của run trước.

## 5. Quy tắc chart Phase 3

- BUY/SELL marker đặt tại `fill_time` và `fill_price`.
- Tooltip marker có side, quantity, fee, signal time và reason.
- Rejected/unfilled order không tạo marker giao dịch.
- Nếu chart không có bar khớp `fill_time`, báo data consistency error; không tự dời
  marker sang bar gần nhất.
- Chart, summary và tables phải dùng cùng `run_id` và dataset version.
- Dùng timestamp có timezone rõ ràng, không đổi timezone làm marker lệch bar/phiên.
- Giữ nguyên giá khớp đã gồm slippage, kể cả khi nằm ngoài high/low của nến;
  trục giá phải bao phủ marker. Không ép marker về Open/Close/high/low.
- Khi marker dày, dùng mũi tên nhỏ không kèm nhãn chữ cố định: đầu mũi tên vẫn
  neo đúng `fill_price`; BUY đi từ dưới lên và SELL đi từ trên xuống. Legend và
  tooltip giữ chữ BUY/SELL, bảng fills giữ đường truy cập bằng bàn phím.
- Reason lấy theo quan hệ `fill.order_id -> order.signal_id -> signal.reason`.
- Khi đổi run, xóa chart/tooltip cũ; bỏ qua response đến muộn của run trước.
- Không có fill: vẫn vẽ nến và báo chưa có giao dịch đã khớp. Vị thế đang mở
  chỉ hiển thị các marker fill thực có, không tạo exit giả cuối kỳ.

### Acceptance chart tối thiểu của đợt push

- Fixture có ít nhất hai executed fills với side khác nhau; số marker bằng số fill.
- Ngày/giá của từng marker khớp API và bảng fills, kể cả sau reload run.
- Zoom, scroll, resize không làm marker lệch nến/giá.
- No-fill, pending/rejected và vị thế mở hiển thị đúng các quy tắc trên.
- Thiếu bar, sai OHLC hoặc lệch run/version/hash phải báo lỗi và không vẽ chart
  như dữ liệu hợp lệ; lỗi API không để chart cũ gắn với run mới.
- Acceptance chạy bằng Docker với pickle persist/reload và snapshot đã xác nhận.
- Volume khớp từng bar kể cả zero volume; không che nến/marker.
- Equity line khớp equity_history và summary cuối; có trục giá riêng.
- Các cột entry/exit price, quantity, fees, net_pnl khớp trades API.
- Keyboard/focus/labels và thông báo aria-live; chuỗi từ API được render an toàn
  như text; mở run nhiều lần không nhân canvas/listeners.
- Assets CSS/JS/vendor tải được từ package/Docker cùng origin, có attribution.
- Indicator, trade return và tương tác chart nâng cao không thuộc acceptance đợt này.

## 6. Acceptance trước Phase 3

- UI render đúng initial cash, final equity, realized/unrealized P/L và total return
  từ backend.
- Fills, trades, open position và equity khớp API response.
- Run đã thành công vẫn mở lại được sau khi restart backend.
- No-trade, rejected-order và error fixtures hiển thị đúng semantics.
- Không yêu cầu candlestick chart để nghiệm thu bước UI tối thiểu.

## 7. Acceptance Phase 3

- Render daily candlestick và volume của dataset trong run.
- Marker khớp chính xác fill records.
- BUY/SELL, summary, equity và trade history nhất quán với cùng backend response.

## 8. Lựa chọn triển khai và quyết định còn mở

- HTML/CSS/JavaScript ES modules; FastAPI phục vụ /static cùng backend.
- Chart library: Lightweight Charts v5 standalone ESM. Người triển khai tự chọn
  và xác minh patch release có marker theo giá, pin asset/license/NOTICE.
- Flow/diagram, cây file và test cases: [plan chart](../plans/candlestick-ui-plan.md).
- State công việc: [PROGRESS](../plans/progress.md). CFM-01 dataset nghiệm thu còn chờ
  xác nhận; pagination/filter history và tương tác nâng cao để scope sau.
