# Backtest HPG trên chart — 17/09/2026

## API chung — cập nhật U07/U08 ngày 29/09/2026

```powershell
.venv\Scripts\python.exe -m uvicorn backtest_hpg.main:app --host 127.0.0.1 --port 8000
```

Mặc định lưu trữ tại `data/backtest-store`; `/docs` hiển thị đặc tả API.
`intraday_main:app` là tên tương thích trỏ cùng ứng dụng. Hệ thống sử dụng kho
file cục bộ (JSON + Parquet), không kết nối cơ sở dữ liệu bên ngoài.

`POST /api/backtests/validate` kiểm tra/ánh xạ JSON, kỳ báo cáo, map hợp đồng và
khoảng thiếu dữ liệu. `POST /api/backtests` chạy cây JSON với SMA/EMA/BB/MACD/MFI,
long/short, chốt từng phần và sổ tiền hợp đồng. Trang `/` nhận JSON hoặc file JSON,
có nút kiểm tra, chạy và xem lại kết quả. Mẫu v1 trên form chỉ có hai nến minh họa.
Đã kiểm thử bằng dữ liệu tổng hợp; nghiệm thu dữ liệu thật sáu tháng thuộc U09.
Chi tiết: [U07–U08](docs/plans/engine-upgrade-u07-u08.md).

Phần hướng dẫn lịch sử bên dưới áp dụng v0.

**Ưu tiên 18/09:** triển khai backtest VN30F1M 5 phút qua API và notebook,
1D chỉ hỗ trợ; chưa cần agent. Điền các field C01–C06 và theo dõi W01–W08 tại
[checklist triển khai](.agents/checklists/vn30f1m-backtest-checklist.md). Runtime bên dưới
vẫn là baseline HPG/chart snapshot; chưa nghiệm thu backtest VN30F1M.

Source intraday đã có tại `backtest_hpg.intraday_main:app`, dùng Parquet + JSON,
không cần database hoặc agent. Xem [runbook API/notebook](docs/plans/vn30f1m-backtest-runbook.md).
Hai JSON mới đã import nhưng chỉ bắt đầu 18/03; kỳ báo cáo user giữ 15/03–15/09
nên API hiện fail thiếu phiên 16–17/03, chờ bổ sung lịch sử 5 phút cả hai symbol.

[Plan research agent](docs/plans/agent-research-plan.md) · [Tiến độ](docs/plans/progress.md)

---

# BackTesting HPG

Luồng backtest hiện tại: JSON → kiểm tra dữ liệu → chỉ báo → điều kiện chiến lược
→ tín hiệu → khớp lệnh → tài khoản → kết quả trong kho file → Web UI.

API lưu đầu vào và kết quả JSON qua `FileRunRepository` tại `data/backtest-store`.
Giao diện đọc cùng kết quả từ API để hiển thị biểu đồ và các bảng đối chiếu.

Ưu tiên đợt bàn giao tiếp theo: Docker + notebook + chart nến có điểm BUY/SELL.
[Kế hoạch frontend/chart](docs/plans/candlestick-ui-plan.md) gồm stack, flow, cây file
và test cases; [PROGRESS](docs/plans/progress.md) theo dõi trạng thái từng bước.
Chart implementation chưa bắt đầu.

## Cài đặt trên Windows CMD

```cmd
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
```

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
docker compose up --build
```

Mở `http://127.0.0.1:8000`.

Luồng đọc source của một API backtest:

```text
main.py
  -> api/backtest_routes.py
  -> application/run_backtest.py
  -> application/inline_strategy.py
  -> domain/engine.py
  -> infrastructure/file_repository.py
```

## Tài liệu

- [Cấu trúc repository](docs/design/project-structure.md)
- [Software Requirements Specification](docs/requirements/software-requirements-specification.md)
- [System Design](docs/design/system-design.md)
- [Technical Plan](docs/plans/technical-plan.md)
- [Data Contract](docs/data/hpg/data-contract.md)
- [CANSLIM Rules](docs/strategies/canslim-rules.md)
- [Accounting Test Cases](docs/testing/hpg/accounting-test-cases.md)
- [Web UI Specification](docs/design/web-ui-specification.md)
- [Backtest Plan v0](docs/plans/backtest-plan-v0.md)

Agent helpers, raw data, local `.env`, generated output và planning workbook nằm
trong các vùng Git-ignored được mô tả tại `docs/design/project-structure.md`.
