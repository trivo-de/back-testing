# Data Contract — Backtest HPG v0

Cập nhật: 11/09/2026. Phase 1/MVP dùng snapshot từ VNDIRECT dchart theo profile
bên dưới; metadata nguồn chưa công bố rõ phải được lưu thành limitation, không
được tự suy diễn.

## 1. Dataset metadata bắt buộc

| Field                   | Ý nghĩa                                                               |
| ----------------------- | ----------------------------------------------------------------------- |
| dataset_id              | Stable identifier của snapshot                                         |
| dataset_version         | Version do project/source gán                                          |
| content_hash            | Hash nội dung dùng để tái lập run                                 |
| source                  | Nguồn dữ liệu                                                        |
| extracted_at            | Thời điểm snapshot được lấy                                      |
| timeframe               | Phải là`1D` cho strategy v0                                         |
| timezone                | Timezone dùng để xác định trading session                         |
| price_unit              | Đơn vị giá                                                          |
| currency                | Dự kiến`VND`, phải xác nhận từ nguồn                           |
| price_adjustment        | `raw`, `back_adjusted` hoặc giá trị được nguồn định nghĩa |
| volume_adjustment       | Cách volume liên hệ với price adjustment                            |
| corporate_action_policy | Các event đã được phản ánh và cách phản ánh                 |

Các metadata ảnh hưởng accounting cần được xác nhận trước khi chạy report backtest.

## 2. HPG daily bar

| Field        | Type                              | Rule                                 |
| ------------ | --------------------------------- | ------------------------------------ |
| symbol       | string                            | `HPG` trong v0                     |
| trading_date | date                              | Unique, tăng dần                   |
| open         | finite number                     | `> 0`                              |
| high         | finite number                     | `>= max(open, close)`              |
| low          | finite number                     | `<= min(open, close)` và `> 0`  |
| close        | finite number                     | `> 0`                              |
| volume       | finite number/integer theo nguồn | `>= 0`; unit phải được ghi rõ |

`high >= low` là bắt buộc. Null, NaN, duplicate date và out-of-order row là input error.

## 3. VN-Index daily bar

| Field        | Type          | Rule                                                       |
| ------------ | ------------- | ---------------------------------------------------------- |
| symbol       | string        | Canonical value được data adapter map thành`VNINDEX` |
| trading_date | date          | Unique, tăng dần                                         |
| close        | finite number | `> 0`                                                    |

Lưu ý: Rule R1 cần 200 VN-Index sessions kết thúc tại `t` để có warm-up.

## 4. Alignment và availability

- Strategy chỉ nhận completed daily bars.
- `t-1` là prior trading session trong validated series, không phải prior calendar
  date.
- HPG và VN-Index phải align bằng `trading_date`; missing required index value tại
  `t` làm R1 unevaluable.
- Không dùng bar sau `t` để bù warm-up tại `t`.
- Data gap phải được phân biệt với ngày thị trường đóng bằng calendar/profile hoặc
  source metadata; chưa có profile thì report gap thay vì tự suy diễn.

## 5. Adjusted-data policy

- VNDIRECT dchart back-adjusted data được chọn làm working dataset cho MVP.
- Cửa sổ tải là `[2019-01-01, 2024-01-01)`: năm 2019 dùng làm warm-up; kỳ báo cáo
  backtest là `[2020-01-01, 2023-12-31]`.
- HPG dùng `resolution=D`, `symbol=HPG`, `from=1546300800`, `to=1704067200`;
  VN-Index dùng cùng params thời gian với `symbol=VNINDEX`.
- Lần kiểm tra ngày 11/09/2026, mỗi endpoint trả 1.250 phiên từ 02/01/2019 đến
  29/12/2023.
- Không query live endpoint trong mỗi backtest run; snapshot phải có hash/version.
- Trước khi promote một adjusted dataset, xác nhận cả O/H/L/C có cùng convention,
  volume có được điều chỉnh hay không và event nào được phản ánh.
- Không trộn adjusted indicator prices với raw execution prices nếu chưa có
  adjustment factor/corporate-action model explicit.
- Nếu toàn bộ run dùng adjusted units, result phải ghi đây là normalized simulation;
  cash/P&L không mặc nhiên đại diện số tiền giao dịch lịch sử thực tế.
- Payload quan sát được xác nhận `resolution=D` và timestamp Unix ở 00:00 UTC;
  adapter map calendar date UTC thành `trading_date`.
- Đơn vị giá chính thức, volume adjustment và corporate-action policy chưa được
  endpoint công bố rõ. Giữ các field này ở trạng thái unknown/limitation thay vì
  điền giá trị suy đoán.

## 6. Run config tối thiểu

```text
dataset_id
dataset_version
symbol
start_date
end_date
strategy_id
initial_cash
fee_rate
slippage_rate
```

Strategy parameters cố định của `canslim_breakout_v0` được ghi trong
[canslim-rules.md](canslim-rules.md) và phải được copy vào result metadata.

## 7. Result contract

| Group          | Fields chính                                                                |
| -------------- | ---------------------------------------------------------------------------- |
| metadata       | run_id, dataset ID/version/hash, engine version, config, strategy parameters |
| signals        | signal_time, side, reason, pivot/reference values                            |
| orders         | order_id, signal_id, side, status, rejection reason                          |
| fills          | order_id, fill_time, fill_price, quantity, fee                               |
| trades         | entry/exit time/price, quantity, fees, net P/L                               |
| open_position  | quantity, entry data, cost basis, unrealized P/L                             |
| equity_history | trading_date, cash, quantity, market value, equity, unrealized P/L           |
| summary        | final equity, closed P/L, unrealized P/L, total return                       |

Các field không tồn tại vì chưa fill phải là null/absent theo schema đã chọn, không
được tạo giá giả.

## 8. Contract phục vụ Web UI

- UI lấy summary, equity, fills, trades và open position từ cùng một response và
  `run_id`; không tự tính lại nghiệp vụ ở frontend.
- Bảng executed orders lấy `fill_time`, `fill_price`, `side`, `quantity`, `fee` và
  `order_id` từ `fills`.
- Equity view lấy trực tiếp `trading_date` và `equity` từ `equity_history`.
- Open position hiển thị riêng từ `open_position`, không ép thành closed trade.
- Signals và rejected/unfilled orders hiển thị ở audit view, không trộn với fills.
- Khi xây chart nến ở Phase 3, OHLCV phải lấy từ chính dataset snapshot của run;
  BUY/SELL marker phải dùng fill time/price, không dùng signal time/price.

## 9. Persistence contract

- PostgreSQL là system of record cho dataset metadata và backtest history.
- `run_id`, `signal_id`, `order_id`, `fill_id` và `trade_id` là stable IDs sau khi
  persist; API reload phải trả đúng relationships này.
- Mỗi run tham chiếu đúng một immutable dataset version/content hash; không copy
  cùng OHLCV vào từng run.
- Raw source snapshot và export lớn lưu qua artifact-storage URI kèm content hash;
  database lưu metadata và reference.
- Run result chỉ được đánh dấu `succeeded` khi metadata, signals, orders, fills,
  trades, position và equity history đã được ghi nguyên vẹn trong một transaction.
- Failed run lưu status/error nhưng không được expose partial result như một lần
  backtest thành công.
- Các field thường filter/sort/join phải là relational columns. JSONB chỉ dùng cho
  config, strategy parameters và details ít ổn định; không nhét toàn bộ history vào
  một JSON document duy nhất.
