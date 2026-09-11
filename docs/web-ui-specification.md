# Web UI Specification — Backtest HPG v0

Cập nhật: 11/09/2026.

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

### Phase 3 — chưa xây ở bước hiện tại

- Daily candlestick HPG.
- Volume.
- BUY/SELL marker từ executed fills.
- Equity chart và tương tác chart chi tiết.

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

## 4. Trạng thái giao diện

- **Initial:** chưa chạy, hiển thị form và required input.
- **Loading:** ngăn chạy request trùng.
- **Success with trades:** hiển thị summary, fills, trades và equity.
- **Success without trades:** kết quả hợp lệ; trade/fill table rỗng có giải thích.
- **Open position:** hiển thị unrealized P/L; không tạo SELL giả cuối kỳ.
- **Validation error:** hiển thị field/code/message từ API.
- **Data/internal error:** không render số liệu một phần như kết quả thành công.

## 5. Quy tắc chart Phase 3

- BUY/SELL marker đặt tại `fill_time` và `fill_price`.
- Tooltip marker có side, quantity, fee, signal time và reason.
- Rejected/unfilled order không tạo marker giao dịch.
- Nếu chart không có bar khớp `fill_time`, báo data consistency error; không tự dời
  marker sang bar gần nhất.
- Chart, summary và tables phải dùng cùng `run_id` và dataset version.

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

## 8. Quyết định còn mở

- Web framework.
- Chart library trước Phase 3.
- UI chạy cùng backend process hay build/deploy riêng.
- Pagination/filter chi tiết cho danh sách run history.
