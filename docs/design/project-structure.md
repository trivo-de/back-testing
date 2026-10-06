# Cấu trúc repository

Kho dữ liệu dùng [Parquet + JSON](../plans/technical-plan.md).
Đầu vào và kết quả chạy được lưu trong kho file; dữ liệu nguồn giữ nguyên.
Kho lưu phiên và trạng thái agent còn chờ thiết kế khi triển khai agent.


## 1. Cây thư mục

```text
back-testing/
├── .env.example
├── .gitignore
├── README.md
├── pyproject.toml
├── requirements.txt
├── docs/                          # Specification và quyết định kỹ thuật
├── data/
│   ├── preprocessing.ipynb        # Adapter/validator được quản lý trên Git
│   └── dataset_manifest.json      # Metadata snapshot; raw data vẫn local
├── notebooks/
│   └── backtest-results.ipynb     # Trình bày result từ HTTP API
├── src/
│   └── backtesting_api/
│       ├── main.py                # Composition root của FastAPI
│       ├── config.py              # Cấu hình API, phiên bản engine và kho file
│       ├── api/
│       │   ├── app.py             # Tạo FastAPI app
│       │   ├── backtest_routes.py # HTTP endpoints
│       │   └── inline_schemas.py  # Kiểm tra yêu cầu JSON bằng Pydantic
│       ├── application/
│       │   ├── ports.py           # Giao diện kho lưu đầu vào và kết quả
│       │   ├── inline_data.py     # Kiểm tra và ánh xạ dữ liệu JSON
│       │   ├── inline_strategy.py # Thực thi chỉ báo và điều kiện chiến lược JSON
│       │   ├── inline_results.py  # Chuyển kết quả engine thành JSON
│       │   └── run_backtest.py    # Điều phối kiểm tra, chạy và lưu kết quả
│       ├── domain/
│       │   ├── market.py          # Bar, StrategyBar và thời điểm nến
│       │   ├── trading.py         # Signal, order, fill và trade models
│       │   ├── results.py         # Equity, summary và BacktestResult
│       │   ├── engine.py          # Event loop và next-open execution
│       │   ├── portfolio.py       # Cash, position và P/L ledger
│       │   ├── indicators.py      # Tính chỉ báo
│       │   ├── expressions.py     # Kiểm tra và đánh giá cây biểu thức
│       │   ├── execution.py       # Khớp lệnh
│       │   └── contract_accounting.py # Tính tiền hợp đồng
│       ├── infrastructure/
│       │   ├── file_repository.py # Kho JSON và đọc dataset lịch sử Parquet
│       │   └── market_snapshot.py # Kiểm tra, chuẩn hóa OHLCV nguồn
│       └── web/
│           ├── index.html
│           ├── backtest-app.mjs
│           ├── backtest-data.mjs
│           ├── backtest-chart.mjs
│           ├── theme.css
│           ├── theme.mjs
│           ├── preview.css
│           ├── preview-theme.mjs
│           ├── canslim-v1-example.json # Mẫu yêu cầu JSON
│           └── vendor/           # Lightweight Charts và giấy phép
└── tests/
    ├── fixtures/                  # JSON nhỏ, cố định và offline
    └── test_*.py
```

Không dùng file chung chung như `models.py` hoặc `services.py`. Model được đặt theo
khái niệm nghiệp vụ (`market`, `trading`, `results`); use case chạy backtest nằm rõ
trong `application/run_backtest.py`.

## 2. Nhóm cấu hình

`backtesting_api/config.py` khai báo cấu hình dùng chung của backend:

| Nhóm                   | Nội dung                                                       |
| ----------------------- | --------------------------------------------------------------- |
| `API`                 | API title, version và backtest route prefix                    |
| `BACKTEST`            | Phiên bản engine |
| `INTRADAY`            | Đường dẫn kho file, lấy từ `BACKTEST_STORE_PATH` hoặc `data/backtest-store` |

Chỉ báo, điều kiện chiến lược, cách tính tiền và kỳ báo cáo được cung cấp trong
yêu cầu JSON, theo [hướng dẫn payload](strategy-payload-guide.md).
`main.py` đọc `INLINE_POLICY_PATH` và `AUTO_FETCH_POLICY_PATH` để nối đường dẫn
chính sách vào `BacktestService`.

## 3. Ownership và dependency

| Khu vực            | Sở hữu                                         | Không được chứa                  |
| ------------------- | ------------------------------------------------ | ------------------------------------- |
| `api/`            | HTTP route và Pydantic schema                   | Strategy, accounting hoặc SQL        |
| `application/`    | Use case, port và result mapping                | FastAPI route hoặc SQL cụ thể      |
| `domain/`         | Model, indicator, strategy, execution, portfolio | FastAPI, cơ sở dữ liệu ngoài hoặc agent provider |
| `infrastructure/` | Adapter kho tệp (JSON + Parquet)                 | Strategy rule                         |
| `web/`            | Presentation dùng API result                    | Tự tính signal, fill hoặc P/L      |
| `notebooks/`      | Presentation và kiểm tra API result             | Tự tính signal, fill hoặc P/L      |

Dependency đi từ ngoài vào trong:

```text
api ───────────────┐
                   v
              application -> domain
                   ^
                   |
infrastructure ----┘
```

Domain không import từ `api`, `application`, `infrastructure` hoặc `web`.

## 4. Đường đi của API backtest

Khi đọc source của `POST /api/backtests`, đi theo thứ tự:

```text
backtesting_api.main:app
  -> api/backtest_routes.py
  -> application/run_backtest.py
  -> application/inline_data.py
  -> application/inline_strategy.py
  -> domain/engine.py
  -> application/inline_results.py
  -> infrastructure/file_repository.py
```

`main.py` là nơi duy nhất nối config, file repository, application service và
FastAPI app. `BacktestService` kiểm tra đầu vào, gọi `run_inline_strategy()` và
lưu kết quả qua giao diện `RunRepository`. Kho file ghim đầu vào cùng chính sách
bằng mã băm; đọc chart không chạy lại chiến lược.

## 5. Mở rộng strategy và agent

Chiến lược được mô tả bằng chỉ báo và cây điều kiện trong JSON. Các yêu cầu
dùng chung `inline_strategy.py` và `domain/engine.py`; không tạo engine hoặc
sổ tiền riêng cho từng tên chiến lược.

Khi bắt đầu Phase agent, production code dùng `src/backtesting_api/strategy_agent/`:

```text
strategy_agent/
├── interpreter.py     # Natural language → StrategySpec đã validate
└── provider.py        # Adapter tới model/LLM được chọn
```

Chưa tạo folder này trước khi có implementation. Agent chỉ tạo `StrategySpec` và
gọi application use case; agent không tính indicator, signal, fill hoặc P/L.
Folder `.agents/` ở project root vẫn chỉ là helper/artifact local của coding agent,
không phải production agent.

### Giao diện hiện tại

`web/index.html` nạp các module `.mjs`; `backtest-app.mjs` điều phối giao diện,
`backtest-data.mjs` ánh xạ kết quả và `backtest-chart.mjs` dựng biểu đồ.
Lightweight Charts nằm trong `web/vendor/`. FastAPI phục vụ tài nguyên qua
`/static`; `pyproject.toml` khai báo tài nguyên đóng gói để Docker có đủ file.

## 6. Cây local-only

Các đường dẫn sau bị Git ignore:

```text
.env              # cấu hình môi trường local nếu có
.venv/            # Python virtual environment
.agents/           # helper, scratch và artifact local
data/*             # trừ preprocessing.ipynb và dataset_manifest.json
local_only_docs/   # Gantt/WBS và tài liệu cá nhân
outputs/           # export backtest
logs/              # runtime logs
```

Không commit password, raw market snapshot hoặc output lớn. Fixture nhỏ phục vụ
test nằm trong `tests/fixtures/`.

Quyết định 15/09: đưa notebook preprocessing và manifest lên Git để review và
tái lập luồng import. Việc mở tracking không xác nhận dữ liệu đã nhất quán:
notebook hiện chọn raw 2024–2026 còn manifest mô tả 2019–2023; cần giải quyết
provenance trước acceptance. Hai file được giữ nguyên nội dung ở bước lập plan.

## 7. Cách chạy

Editable install qua `requirements.txt` nên không cần đặt `PYTHONPATH`:

```cmd
python -m pip install -r requirements.txt
python -m unittest discover -s tests -p "test_*.py" -v
python -m uvicorn backtesting_api.main:app --reload
```

## 8. Cơ sở lựa chọn

- [PyPA: src layout vs flat layout](https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/)
  giải thích việc đặt import package dưới `src/` để tránh import nhầm source chưa cài.
- [FastAPI: Bigger Applications](https://fastapi.tiangolo.com/tutorial/bigger-applications/)
  minh họa cách tách application thành package và router khi API mở rộng.
- [Python unittest discovery](https://docs.python.org/3/library/unittest.html#test-discovery)
  mô tả điều kiện để test module có thể được discover và import.
