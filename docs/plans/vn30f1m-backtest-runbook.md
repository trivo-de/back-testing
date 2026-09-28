# VN30F1M 5 phút — chạy API và notebook

**Policy mới 25/09:** `close_at_expiry_open` đóng toàn bộ tại Open đầu phiên
đáo hạn, hủy pending cũ, không entry trong ngày đáo hạn. Signal audit là
`SCHEDULED_EXIT`; phí/slippage áp dụng như SELL thường. Chạy lại notebook để
tạo run mới; các kết quả/ghi chú `hold` trước đó vẫn là lịch sử, không rewrite.

Runbook này dành cho bản chạy **VN30F1M — CANSLIM v0** đã điều chỉnh kỳ ngày 25/09:
**25/03/2026–15/09/2026**. Không cần agent hoặc PostgreSQL
cho app intraday. App HPG cũ vẫn có composition root riêng.

## 1. Dependencies và import offline

```powershell
.venv\Scripts\python.exe -m pip install -e ".[test,intraday,notebook]"
.venv\Scripts\python.exe -m backtest_hpg.infrastructure.snapshot_bundle --vn30f1m 'data/30f1m_5&from=1772323200&to=1789516800.json' --vnindex 'data/VNINDEX_5&from=1772323200&to=1789516800.json'
.venv\Scripts\python.exe -m backtest_hpg.infrastructure.file_repository 'data/intraday-bundles/bundle-52ca9fbe68ce00878bf9cc10d65a088e47eb80b84086f4ec26deb67a1f4e4f9b.json'
```

Manifest pin cả hai raw hashes và Parquet hashes. Raw files user giữ nguyên;
artifact chuẩn hóa nằm trong `data/backtest-store/`, được Git ignore. Giá/volume
trong Parquet dùng chuỗi Decimal; timestamp Unix int64 giữ nguyên.

Bundle hiện tại có **18/03–15/09**. User cho phép lùi report, giữ window
200/65/50 nến 5 phút. Dùng 18–24/03 làm warm-up: 245 nến VN30F1M và 240 nến
VNINDEX. SMA200 đủ lần đầu 24/03 lúc 09:55 UTC+7; chọn đầu phiên 25/03 vì API
nhận start_date theo ngày. Không cần daily, không sửa raw/version hoặc policy.
File/query name bắt đầu 01/03 không chứng minh payload có range đó.

## 2. Static policy

[runtime-policy.json](../data/vn30f1m/runtime-policy.json) là deliverable tĩnh:

- Calendar weekdays/holidays cho 01/03–17/09/2026, có nguồn thông báo HNX.
- Futures có 49 required Open labels/ngày. Market có 48 required và 6 optional
  labels biến thiên theo snapshot; optional records vẫn tham gia SMA khi available.
- Map nhãn tháng tham khảo theo [rollover map](../data/vn30f1m/vn30f1m-rollover-map.md).
  User cho phép dùng như assumption normalized simulation, **giữ vị thế/pending**,
  không forced close/roll trade hoặc chỉnh raw price.
- Timestamp Open; Close/available_at = Open + 5 phút, kể cả ATC 14:45 theo
  assumption mô phỏng đã chốt. Đây không phải mô hình auction/liquidity thực tế.

Missing required bar/session, thiếu roll coverage hoặc thiếu policy fail trước core.
Không suy ra ngày thiếu từ raw là holiday. Để đổi policy, cập nhật nguồn xác nhận
trước và tạo run mới; mỗi run pin policy_hash và dataset_manifest_hash.

## 3. API

```powershell
$env:PYTHONIOENCODING='utf-8'
.venv\Scripts\python.exe -m uvicorn backtest_hpg.intraday_main:app --host 127.0.0.1 --port 8770
```

Runtime settings: `BACKTEST_STORE_PATH` (default `data/backtest-store`),
`VN30F1M_POLICY_PATH` (default `docs/data/vn30f1m/runtime-policy.json`).

API giữ endpoints `POST /api/backtests`, `GET /api/backtests`,
`GET /api/backtests/{run_id}` và `GET /api/backtests/{run_id}/chart`.
POST chọn dataset_id của bundle và dataset_version là bundle hash; không truyền
local paths vào HTTP request. Request example với bundle hiện tại:

```json
{
  "dataset_id": "vndirect-vn30f1m-vnindex-5m-20260301-20260915",
  "dataset_version": "52ca9fbe68ce00878bf9cc10d65a088e47eb80b84086f4ec26deb67a1f4e4f9b",
  "symbol": "VN30F1M",
  "start_date": "2026-03-25",
  "end_date": "2026-09-15",
  "strategy_id": "canslim_breakout_v0",
  "initial_cash": "10000000",
  "fee_rate": "0.001",
  "slippage_rate": "0.002"
}
```

Kỳ mới đã pass validation coverage/session/rollover, gồm cả warm-up. Kỳ cũ
15/03 vẫn bị từ chối do thiếu expected bars ngày 16/03; không nới validator.
Không dùng fixture output làm acceptance dữ liệu thật.

Result thêm `evaluations` và `evaluation_status`: EVALUABLE, PARTIALLY_EVALUABLE
hoặc UNEVALUABLE. No-trade không đồng nghĩa đủ input. Signal/equity tại Close,
fill tại Open; timestamp giữ UTC offset. Market samples độc lập, không lặp daily
hay market Close thành nhiều mẫu để làm đủ SMA200. Cuối kỳ không tự SELL.

App intraday dùng một writer/process; không chạy nhiều Uvicorn workers. JSON complete
result publish bằng atomic replace, failed/running runs không xuất hiện như thành
công. Restart app vẫn GET được complete result đã lưu. File hỏng trả lỗi rõ.

## 4. Notebook và tests

Mở `notebooks/backtest-results.ipynb` bằng kernel `.venv`, chạy tất cả cell.
Notebook đọc manifest pin sẵn, POST tạo run và GET lại cùng run_id để đối chiếu.
Nó hiển thị input hashes/ranges, config, assumptions/warm-up, evaluation coverage,
summary, fills/trades/open position, audit và equity; không tính lại strategy/P&L.

Notebook settings: `BACKTEST_API_URL`, `BACKTEST_DATASET_MANIFEST`,
`BACKTEST_REPORT_START`, `BACKTEST_REPORT_END`. Defaults là API port 8770,
bundle hiện tại và kỳ báo cáo đã chốt. Override range không phải tự động phê duyệt
strategy/data policy; dùng range đã xác nhận hoặc synthetic test rõ nhãn.

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Tests intraday dùng fixture synthetic cho timing, independent market samples,
causality, determinism, HTTP, Parquet/Decimal round-trip, reload/restart, missing
policy/roll map/bar và interrupted publish. Các kết quả đó không chứng minh
snapshot hiện tại đã đủ report coverage; evidence runtime ghi ở checklist local.

### Evidence kỳ mới — 25/09/2026

- Bundle thật đã pin ở trên; report 25/03–15/09, warm-up VN30F1M/VNINDEX:
  245/240 nến. `evaluation_status=EVALUABLE`: 5.831 evaluated, 0 unevaluable.
- Run `9330a365-78d6-40a7-a010-929750f2e8e1`: 1 fill, 0 closed trades;
  không ép đóng vị thế cuối kỳ. Kết quả lưu tại file store local.
- FastAPI TestClient chạy POST/GET/chart; tạo app/repository mới đọc lại khớp
  result. Run lặp khớp summary/evaluations/equity/evaluation_status.
- Tất cả code cell notebook chạy với bundle thật qua TestClient, POST và GET
  cùng run_id khớp nhau. Đây là kiểm tra in-process; chưa kiểm tra server HTTP
  độc lập hoặc giao diện browser/Docker trong lượt này.
