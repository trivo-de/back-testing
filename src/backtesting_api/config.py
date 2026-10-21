# Centralized immutable settings and runtime environment loading.
import os
from dataclasses import dataclass
from pathlib import Path

# Schemas
# Hold immutable API metadata and route paths.
@dataclass(frozen=True)
class ApiSettings:
    title: str
    version: str
    home_path: str
    backtests_path: str

# Hold the engine version recorded with backtest results.
@dataclass(frozen=True)
class BacktestSettings:
    engine_version: str

# Hold the configured file-backed run storage path.
@dataclass(frozen=True)
class IntradaySettings:
    store: Path


INTRADAY = IntradaySettings(
    store=Path(os.getenv("BACKTEST_STORE_PATH", "data/backtest-store")),
)
API = ApiSettings(
    title="Backtesting API",
    version="0.1.0",
    home_path="/",
    backtests_path="/api/backtests",
)
BACKTEST = BacktestSettings(
    engine_version="0.2.0",
)

