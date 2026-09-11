# Software Requirements Specification — Backtest HPG v0

Cập nhật: 11/09/2026.

## 1. Mục tiêu

Xây một backtest có thể tái lập và giải thích được cho
`canslim_breakout_v0` trên HPG daily: từ dữ liệu, signal, simulated execution đến
cash, position, P/L, equity, API và Web UI hiển thị kết quả.

Correctness được đánh giá bằng việc khớp rule, timing, accounting và dữ liệu đầu
vào; không đánh giá bằng việc strategy có lợi nhuận hay không.

## 2. Phạm vi sản phẩm và Phase 1

Deliverable cuối có Web UI. Trước khi xây chart nến ở Phase 3, UI tối thiểu cần
hiển thị summary P/L, equity, fills, open position, lịch sử giao dịch và thông tin
run/dataset/config.

- HPG và VN-Index daily.
- Long-only, tối đa một vị thế, không leverage hoặc pyramiding.
- Entry/exit theo [canslim-rules.md](canslim-rules.md).
- Market execution mô phỏng ở Open phiên kế tiếp.
- Fixed fractional risk sizing 2%.
- Core xử lý một run trong memory; application persist dataset/version và toàn bộ
  result history vào PostgreSQL để Web UI có thể mở lại sau khi restart.
- Chưa yêu cầu authentication nhiều user, realtime hoặc UI đầy đủ.

## 3. Functional requirements

| ID     | Requirement                                                                                                             |
| ------ | ----------------------------------------------------------------------------------------------------------------------- |
| FR-001 | Hệ thống nhận dataset snapshot và run config có version/provenance.                                                |
| FR-002 | Hệ thống từ chối input sai schema, thiếu required column/metadata, duplicate/out-of-order date hoặc invalid OHLC. |
| FR-003 | Indicator chỉ sử dụng completed bars đến thời điểm decision và trả trạng thái warm-up rõ ràng.            |
| FR-004 | Strategy tạo BUY/SELL signal và reason đúng CANSLIM rule; signal không tự trở thành fill.                       |
| FR-005 | Pending signal chỉ được execution xử lý tại Open phiên kế tiếp.                                               |
| FR-006 | BUY quantity được tính theo fixed fractional risk 2% và bị giới hạn bởi cash gồm entry fee.                   |
| FR-007 | Hệ thống ghi rejected, pending và filled order riêng biệt.                                                         |
| FR-008 | Portfolio ghi cash, position, fees, realized/unrealized P/L và equity tại mỗi Close.                                 |
| FR-009 | Open position cuối kỳ được giữ và mark-to-market; final-session signal không tạo fill giả.                    |
| FR-010 | Kết quả gồm metadata/config, signals, orders/fills, closed trades, open position, equity history và summary.       |
| FR-011 | Cùng dataset version và config phải cho cùng kết quả.                                                             |
| FR-012 | API tối thiểu chỉ được thêm sau khi domain core chạy đúng các fixture.                                       |
| FR-013 | Web UI render result của backend; không tự tính signal, fill, P/L hoặc equity.                                    |
| FR-014 | UI hiển thị summary P/L, equity history, fills, open position và trade history của cùng run ID.                  |
| FR-015 | Candlestick chart và BUY/SELL marker trực quan được triển khai ở Phase 3; marker phải lấy từ fill thực tế.      |
| FR-016 | Mỗi run thành công phải persist metadata, signals, orders, fills, trades, open position và equity history.     |
| FR-017 | Web UI/API có thể liệt kê và mở lại run đã lưu theo `run_id`; restart service không làm mất history.             |
| FR-018 | Dataset dùng cho run phải tham chiếu immutable dataset version/content hash để kết quả có thể tái lập.          |

## 4. Non-functional requirements

- **Causality:** kết quả đến `t` không đổi nếu bỏ toàn bộ dữ liệu sau `t`.
- **Auditability:** mỗi signal/order/fill có time, reason, status và dữ liệu tham
  chiếu đủ để đối chiếu.
- **Determinism:** không đọc live API, current time hoặc random state trong core.
- **Separation of concerns:** giữ riêng data, indicator, strategy, signal,
  execution, portfolio và metrics.
- **Fail explicitly:** missing/invalid data không được coi là strategy pass.
- **Reproducibility:** lưu dataset hash/version, strategy parameters, fee/slippage
  và engine version trong result.
- **Presentation consistency:** mọi component Web UI phải dùng cùng một response và
  `run_id`; frontend không được tính lại số liệu nghiệp vụ.
- **Durability:** run đã báo thành công phải còn truy cập được sau process restart.
- **Atomicity:** không được để một run thành công chỉ lưu một phần signals/fills/
  trades/equity; failure phải có status/error riêng.
- **Storage isolation:** domain core không import PostgreSQL driver hoặc ORM.

## 5. Acceptance Phase 1

- Boundary tests cho SMA/pivot/volume/depth/buy-zone/stop/target pass.
- ACC-01–03 khớp cash, fees, P/L và equity.
- Signal dùng Close `t` không fill trước Open phiên kế tiếp.
- Insufficient cash, quantity dưới 1, missing next bar và final signal không tạo
  fill giả.
- Full-vs-truncated causality test pass.
- Cùng fixture/config chạy lặp lại cho output giống nhau.
- Một application call chạy core, persist thành công và trả đủ response contract
  mà không cần Web UI tham gia tính toán.
- Run thành công được reload từ PostgreSQL và cho cùng business result DTO.

### Acceptance Web UI trước chart nến

- Hiển thị initial cash, final equity, realized P/L, unrealized P/L và total return
  từ backend.
- Equity history, fills và trade history khớp response của cùng `run_id`.
- Open position, no-trade, rejected-order, loading và error state được phân biệt rõ.
- Chưa yêu cầu candlestick chart ở bước này.

### Acceptance Web UI Phase 3

- Render daily candlestick và volume của dataset trong run.
- BUY/SELL marker dùng `fill_time` và `fill_price`, không dùng `signal_time` làm vị
  trí giao dịch đã khớp.
- Chart, summary và trade table khớp cùng backend response.

## 6. Ngoài phạm vi Phase 1

- C/A/L/I đầy đủ khi chưa có data/rule tương ứng.
- Multi-symbol portfolio, short selling, leverage và nhiều vị thế đồng thời.
- Intraday execution, stop order trong phiên, partial fill và liquidity model.
- Thuế, settlement T+, board lot và price-limit nếu chưa có specification.
- Optimization để chọn threshold theo kết quả HPG.
- Production authentication và distributed/background job infrastructure.
- Realtime price, live trading và portfolio dashboard nhiều user.

## 7. Quyết định dữ liệu/config và open requirements

Đã chốt cho MVP:

- Working dataset là snapshot VNDIRECT dchart daily: tải `[2019-01-01,
  2024-01-01)`, dùng năm 2019 làm warm-up và báo cáo `[2020-01-01, 2023-12-31]`.
- Timestamp Unix 00:00 UTC được map thành `trading_date`.
- Config báo cáo: `initial_cash = 10000000`, `fee_rate = 0.001`,
  `slippage_rate = 0.002`.

Còn mở:

- Đơn vị giá chính thức, volume adjustment và corporate-action treatment của
  VNDIRECT; trong lúc chưa xác nhận, output phải mang nhãn normalized simulation.
- API/ORM/migration framework và phiên bản dependency.
- Retention, backup và artifact-storage production policy.
