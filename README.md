# BackTesting HPG

Web backtest HPG daily: strategy → simulated execution → portfolio/P&L → PostgreSQL
history → Web UI.

Phase 1 hiện có deterministic core, `canslim_breakout_v0`, API, PostgreSQL
repository/migration và Web UI dạng cards/tables. Kết quả dùng snapshot VNDIRECT
back-adjusted vẫn mang nhãn `normalized simulation`.

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

## Chạy test và Web UI

```cmd
python -m unittest discover -s tests -p "test_*.py" -v
python -m uvicorn backtest_hpg.main:app --reload
```

Mở `http://127.0.0.1:8000`. API gồm:

- `POST /api/backtests`
- `GET /api/backtests`
- `GET /api/backtests/{run_id}`

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

- [Cấu trúc repository](docs/project-structure.md)
- [Software Requirements Specification](docs/software-requirements-specification.md)
- [System Design](docs/system-design.md)
- [Technical Plan](docs/technical-plan.md)
- [Data Contract](docs/data-contract.md)
- [PostgreSQL Schema](docs/database-schema.md)
- [CANSLIM Rules](docs/canslim-rules.md)
- [Accounting Test Cases](docs/accounting-test-cases.md)
- [Web UI Specification](docs/web-ui-specification.md)
- [Backtest Plan v0](docs/backtest-plan-v0.md)

Agent helpers, raw data, local `.env`, generated output và planning workbook nằm
trong các vùng Git-ignored được mô tả tại `docs/project-structure.md`.
