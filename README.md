# Backtest HPG trên chart — 17/09/2026

**Ưu tiên 18/09:** triển khai backtest VN30F1M 5 phút qua API và notebook,
1D chỉ hỗ trợ; chưa cần agent. Điền các field C01–C06 và theo dõi W01–W08 tại
[checklist triển khai](.agents/checklists/vn30f1m-backtest-checklist.md). Runtime bên dưới
vẫn là baseline HPG/chart snapshot; chưa nghiệm thu backtest VN30F1M.

Source intraday đã có tại `backtest_hpg.intraday_main:app`, dùng Parquet + JSON,
không cần database hoặc agent. Xem [runbook API/notebook](docs/plans/vn30f1m-backtest-runbook.md).
Hai JSON mới đã import nhưng chỉ bắt đầu 18/03; kỳ báo cáo user giữ 15/03–15/09
nên API hiện fail thiếu phiên 16–17/03, chờ bổ sung lịch sử 5 phút cả hai symbol.

Theo yêu cầu quay lại data cũ để xem backtest: dùng app đầy đủ với PostgreSQL
đã có dataset/run HPG. Trang chủ tự mở run gần nhất, có nến daily, volume,
BUY/SELL tại giá/ngày fill, chọn giao dịch để zoom, equity và các bảng đối chiếu.
Chart chỉ đọc snapshot của run; không chạy lại strategy khi mở lịch sử.

```powershell
.venv\Scripts\python.exe -m uvicorn backtest_hpg.main:app --host 127.0.0.1 --port 8765
```

Mở `http://127.0.0.1:8765/`. Cần `DATABASE_URL` trong environment hoặc `.env` và
database đã import HPG/VNINDEX. Endpoint mới: `GET /api/backtests/{run_id}/chart`.
Phiên local đã kiểm tra run 2020–2023: 1.000 nến, 18 fills, 1.000 điểm equity;
toàn bộ OHLCV chart khớp raw HPG 2019–2023. Giữ nhãn `normalized simulation` và
đơn vị giá nguồn; không nhân giá hoặc đổi strategy để vẽ chart.

## Chart VN30F1M và research agent — bản snapshot riêng

Chart chạy trên snapshot VN30F1M 5 phút đã chốt, gồm nến, volume, crosshair OHLCV,
lọc ngày, zoom/scroll, fit view, bảng đối chiếu và metadata UTC+7. Đây là market
snapshot viewer; chưa có backtest VN30F1M, marker hoặc equity vì strategy và
futures accounting chưa được duyệt. Source HPG bên dưới vẫn là baseline cũ.

Chạy từ repository root, không cần database:

```powershell
.venv\Scripts\python.exe -m uvicorn backtest_hpg.chart_main:app --host 127.0.0.1 --port 8000
```

Mở `http://127.0.0.1:8000/`. Với app HPG đang chạy, mở `/market-chart`.
API snapshot: `GET /api/market-chart?start=2026-03-16&end=2026-09-15`.

Raw snapshot local: `data/vn30f1m-5m-20260316-20260915.json` (Git ignored).
Clone mới phải đặt bản snapshot được cung cấp vào đường dẫn này, hoặc khai báo
`VN30F1M_SNAPSHOT_PATH`. Không tự fetch market data. Server kiểm tra SHA-256
`5930f355e7e5bbc8663835a60fca654a31cc5a83184d534008c284a8d3bbaad5`, 6.174 records
và range theo [data contract](docs/data/vn30f1m/data-contract.md). Thiếu file trả 503,
sai hash/dữ liệu trả 409; không tự sửa raw. Extraction time chưa có evidence
được xác nhận nên metadata giữ null. Dataset version của chart là content hash.

Docker riêng cho chart (cần Docker daemon):

```powershell
docker compose -f compose.chart.yaml up --build
```

Asset Lightweight Charts 5.2.0 được vendor trong package, có LICENSE/NOTICE và
checksum; không cần npm build hoặc CDN khi mở trang. Compose cũ vẫn dành cho
legacy HPG/PostgreSQL. Runtime Docker chart chưa được xác minh khi daemon chưa chạy.

[Plan research agent](docs/plans/agent-research-plan.md) · [Tiến độ](docs/plans/progress.md)

---

# BackTesting HPG

Web backtest HPG daily: strategy → simulated execution → portfolio/P&L → PostgreSQL
history → Web UI.

Phase 1 hiện có deterministic core, `canslim_breakout_v0`, API, PostgreSQL
repository/migration và Web UI dạng cards/tables. Kết quả dùng snapshot VNDIRECT
back-adjusted vẫn mang nhãn `normalized simulation`.

Ưu tiên đợt bàn giao tiếp theo: Docker + notebook + chart nến có điểm BUY/SELL.
[Kế hoạch frontend/chart](docs/plans/candlestick-ui-plan.md) gồm stack, flow, cây file
và test cases; [PROGRESS](docs/plans/progress.md) theo dõi trạng thái từng bước.
Chart implementation chưa bắt đầu.

## Cài đặt trên Windows CMD

```cmd
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
copy .env.example .env
notepad .env
```

Thay `change-me` trong `.env` bằng password PostgreSQL local. Environment variable
`DATABASE_URL` được ưu tiên; nếu không có, `config.py` đọc `.env` tại project root.
Không commit `.env`.

## Database và acceptance

```cmd
python scripts\apply_migrations.py
python scripts\run_postgres_acceptance.py
```

Acceptance runner cần snapshot local dưới `data/`, chạy validator trước khi import,
sau đó persist và reload cùng business result từ PostgreSQL.

`data/preprocessing.ipynb` và `data/dataset_manifest.json` được đưa vào phạm vi Git;
raw snapshot tiếp tục local. Chuẩn bị đúng file snapshot theo manifest và kiểm tra
hash trước khi import. Hiện notebook chọn raw 2024–2026 còn manifest mô tả
2019–2023: cần thống nhất dataset trước acceptance, không sửa riêng hash để chạy qua.

## Chạy test và Web UI

```cmd
python -m unittest discover -s tests -p "test_*.py" -v
python -m uvicorn backtest_hpg.main:app --reload
```

Mở `http://127.0.0.1:8000`. API gồm:

- `POST /api/backtests`
- `GET /api/backtests`
- `GET /api/backtests/{run_id}`

## Xem kết quả bằng notebook

Sau khi backend đang chạy và dataset đã được import:

```cmd
python -m pip install -e .[notebook]
```

Mở `notebooks/backtest-results.ipynb`, chỉnh `API_URL`/`payload` nếu cần và chạy
toàn bộ cell. Notebook hiển thị cùng các nhóm kết quả với Web UI, kèm run ID,
dataset ID/version/content hash, config và strategy parameters.

## Chạy bằng Docker

```cmd
copy .env.example .env
docker compose up --build
```

Đổi `POSTGRES_PASSWORD` trong `.env` trước khi deploy, rồi mở
`http://127.0.0.1:8000`. Container ứng dụng tự chạy migration khi khởi động;
PostgreSQL lưu dữ liệu trong volume `postgres_data`.

Raw snapshot không được đóng vào image. Sau khi đặt snapshot và manifest đã xác
nhận dưới `data/`, import và kiểm tra một lần bằng:

```cmd
docker compose exec app python scripts/run_postgres_acceptance.py
```

Luồng đọc source của một API backtest:

```text
main.py
  -> api/backtest_routes.py
  -> application/run_backtest.py
  -> domain/strategies/<strategy_id>.py
  -> domain/engine.py
  -> infrastructure/database.py
```

## Tài liệu

- [Cấu trúc repository](docs/design/project-structure.md)
- [Software Requirements Specification](docs/requirements/software-requirements-specification.md)
- [System Design](docs/design/system-design.md)
- [Technical Plan](docs/plans/technical-plan.md)
- [Data Contract](docs/data/hpg/data-contract.md)
- [PostgreSQL Schema](docs/design/database-schema.md)
- [CANSLIM Rules](docs/strategies/canslim-rules.md)
- [Accounting Test Cases](docs/testing/hpg/accounting-test-cases.md)
- [Web UI Specification](docs/design/web-ui-specification.md)
- [Backtest Plan v0](docs/plans/backtest-plan-v0.md)

Agent helpers, raw data, local `.env`, generated output và planning workbook nằm
trong các vùng Git-ignored được mô tả tại `docs/design/project-structure.md`.
