# Cấu trúc repository

Cập nhật: 14/09/2026.

## 1. Cây thư mục

```text
back-testing/
├── .env.example
├── .gitignore
├── README.md
├── pyproject.toml
├── requirements.txt
├── docs/                          # Specification và quyết định kỹ thuật
├── migrations/
│   └── 001_initial.sql
├── scripts/
│   ├── apply_migrations.py
│   └── run_postgres_acceptance.py
├── src/
│   └── backtest_hpg/
│       ├── main.py                # Composition root của FastAPI
│       ├── config.py              # Nhóm database/API/backtest/result/strategy settings
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
│       │   └── database.py        # PostgreSQL RunRepository adapter
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
| `DATABASE`            | Tên environment variable và đường dẫn`.env`             |
| `API`                 | API title, version và backtest route prefix                    |
| `BACKTEST`            | Engine version, symbol hỗ trợ và result label                |
| `RESULT`              | Precision/rounding quantum                                      |
| `CANSLIM_BREAKOUT_V0` | Strategy ID, indicator windows, threshold, exit và risk sizing |

`DATABASE_URL` thật không phải static value: nó tiếp tục được đọc runtime từ
environment hoặc `.env`, vì credential thay đổi theo máy. Strategy settings là
giá trị cố định theo [CANSLIM Rule](canslim-rules.md), không phải tham số tự tối ưu.

## 3. Ownership và dependency

| Khu vực            | Sở hữu                                         | Không được chứa                  |
| ------------------- | ------------------------------------------------ | ------------------------------------- |
| `api/`            | HTTP route và Pydantic schema                   | Strategy, accounting hoặc SQL        |
| `application/`    | Use case, port và result mapping                | FastAPI route hoặc SQL cụ thể      |
| `domain/`         | Model, indicator, strategy, execution, portfolio | FastAPI, Psycopg hoặc agent provider |
| `infrastructure/` | Adapter PostgreSQL                               | Strategy rule                         |
| `web/`            | Presentation dùng API result                    | Tự tính signal, fill hoặc P/L      |

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
  -> infrastructure/database.py
```

`main.py` là nơi duy nhất nối config, PostgreSQL repository, application service và
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

## 6. Cây local-only

Các đường dẫn sau bị Git ignore:

```text
.env              # credential PostgreSQL local
.venv/            # Python virtual environment
.agents/           # helper, scratch và artifact local
data/              # raw snapshot và preprocessing notebook local
local_only_docs/   # Gantt/WBS và tài liệu cá nhân
outputs/           # export backtest
logs/              # runtime logs
```

Không commit password, raw market snapshot hoặc output lớn. Fixture nhỏ phục vụ
test nằm trong `tests/fixtures/`.

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
