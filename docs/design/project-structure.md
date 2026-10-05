# Cấu trúc repository

Kho dữ liệu dùng [Parquet + JSON](../plans/technical-plan.md#6-persistence-parquet-json).
Đầu vào và kết quả chạy được lưu trong kho file; dữ liệu nguồn giữ nguyên.
Kho lưu phiên và trạng thái agent còn chờ thiết kế khi triển khai agent.


Cập nhật: 15/09/2026.

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
│   └── backtest_hpg/
│       ├── main.py                # Composition root của FastAPI
│       ├── config.py              # Nhóm API/backtest/result/strategy settings
│       ├── api/
│       │   ├── app.py             # Tạo FastAPI app
│       │   ├── backtest_routes.py # HTTP endpoints
│       │   └── backtest_schemas.py # Pydantic request model
│       ├── application/
│       │   ├── contracts.py       # RunConfig
│       │   ├── ports.py           # RunRepository protocol
│       │   ├── result_mapper.py   # Domain result → response/storage DTO
│       │   └── run_backtest.py    # BacktestService use case
│       ├── domain/
│       │   ├── market.py          # Bar, StrategyBar, DatasetSnapshot
│       │   ├── trading.py         # Signal, order, fill và trade models
│       │   ├── results.py         # Equity, summary và BacktestResult
│       │   ├── engine.py          # Event loop và next-open execution
│       │   ├── portfolio.py       # Cash, position và P/L ledger
│       │   ├── indicators.py      # Indicator calculation
│       │   └── strategies/
│       │       ├── __init__.py    # Strategy registry
│       │       └── canslim_breakout_v0.py
│       ├── infrastructure/
│       │   └── file_repository.py # FileRunRepository adapter (JSON + Parquet)
│       └── web/
│           └── index.html
└── tests/
    ├── fixtures/                  # JSON nhỏ, cố định và offline
    └── test_*.py
```

Không dùng file chung chung như `models.py` hoặc `services.py`. Model được đặt theo
khái niệm nghiệp vụ (`market`, `trading`, `results`); use case chạy backtest nằm rõ
trong `application/run_backtest.py`.

## 2. Nhóm cấu hình

`backtest_hpg/config.py` là nơi duy nhất khai báo các static settings của backend:

| Nhóm                   | Nội dung                                                       |
| ----------------------- | --------------------------------------------------------------- |
| `API`                 | API title, version và backtest route prefix                    |
| `BACKTEST`            | Engine version, symbol hỗ trợ và result label                |
| `RESULT`              | Precision/rounding quantum                                      |
| `CANSLIM_BREAKOUT_V0` | Strategy ID, indicator windows, threshold, exit và risk sizing |

Strategy settings là giá trị cố định theo [CANSLIM Rule](../strategies/canslim-rules.md), không phải tham số tự tối ưu.

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
backtest_hpg.main:app
  -> api/backtest_routes.py
  -> application/run_backtest.py
  -> domain/strategies/__init__.py
  -> domain/strategies/<strategy_id>.py
  -> domain/engine.py
  -> infrastructure/file_repository.py
```

`main.py` là nơi duy nhất nối config, file repository, application service và
FastAPI app. Strategy registry là mapping nhỏ từ `strategy_id` tới hàm chạy; không
cần factory hoặc class hierarchy.

## 5. Mở rộng strategy và agent

Thêm strategy mới bằng một module mới dưới `domain/strategies/`, rồi đăng ký trong
`domain/strategies/__init__.py`. Strategy mới dùng cùng `domain/engine.py`; không tạo
engine hoặc accounting riêng.

Khi bắt đầu Phase agent, production code dùng `src/backtest_hpg/strategy_agent/`:

```text
strategy_agent/
├── interpreter.py     # Natural language → StrategySpec đã validate
└── provider.py        # Adapter tới model/LLM được chọn
```

Chưa tạo folder này trước khi có implementation. Agent chỉ tạo `StrategySpec` và
gọi application use case; agent không tính indicator, signal, fill hoặc P/L.
Folder `.agents/` ở project root vẫn chỉ là helper/artifact local của coding agent,
không phải production agent.

### Frontend dự kiến cho đợt chart

Tách CSS/JavaScript đang inline thành `web/styles.css`, `web/app.js` và
`web/chart.js`, giữ `web/index.html`. Vendor Lightweight Charts nằm `web/vendor/`;
`web/package.json` chỉ khai báo ES module cho Node tests. Serve assets qua /static
cùng FastAPI và khai báo package-data để Docker có đủ file.
Cây đầy đủ, ownership và test files dự kiến nằm ở
[plan chart mục 3.7](../plans/candlestick-ui-plan.md#37-cây-frontend-và-các-file-liên-quan-khi-build).
Đây là cấu trúc sẽ tạo khi build, không phải các file đã tồn tại.

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
python -m uvicorn backtest_hpg.main:app --reload
```

## 8. Cơ sở lựa chọn

- [PyPA: src layout vs flat layout](https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/)
  giải thích việc đặt import package dưới `src/` để tránh import nhầm source chưa cài.
- [FastAPI: Bigger Applications](https://fastapi.tiangolo.com/tutorial/bigger-applications/)
  minh họa cách tách application thành package và router khi API mở rộng.
- [Python unittest discovery](https://docs.python.org/3/library/unittest.html#test-discovery)
  mô tả điều kiện để test module có thể được discover và import.
