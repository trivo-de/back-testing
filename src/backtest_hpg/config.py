# Centralized immutable settings and runtime environment loading.
import os
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

# Schemas
@dataclass(frozen=True)
class DatabaseSettings:
    url_environment_variable: str
    env_file: Path

@dataclass(frozen=True)
class ApiSettings:
    title: str
    version: str
    home_path: str
    backtests_path: str

@dataclass(frozen=True)
class BacktestSettings:
    engine_version: str
    supported_symbol: str
    result_label: str

@dataclass(frozen=True)
class ResultSettings:
    quantum: Decimal

@dataclass(frozen=True)
# Fixed parameters for canslim_breakout_v0 strategy.
class CanslimBreakoutV0Settings:
    strategy_id: str
    sma_window: int
    base_window: int
    max_base_depth: Decimal
    volume_window: int
    volume_multiplier: Decimal
    buy_zone_multiplier: Decimal
    stop_loss_pct: Decimal
    take_profit_pct: Decimal
    risk_per_trade_pct: Decimal

    # Return a serializable parameter snapshot for run audit records.
    def parameters(self) -> dict[str, int | str]:
        return {
            "SMA_WINDOW": self.sma_window,
            "BASE_WINDOW": self.base_window,
            "MAX_BASE_DEPTH": str(self.max_base_depth),
            "VOLUME_WINDOW": self.volume_window,
            "VOLUME_MULT": str(self.volume_multiplier),
            "BUY_ZONE_MULT": str(self.buy_zone_multiplier),
            "STOP_LOSS_PCT": str(self.stop_loss_pct),
            "TAKE_PROFIT_PCT": str(self.take_profit_pct),
            "RISK_PER_TRADE_PCT": str(self.risk_per_trade_pct),
        }


# Backend settings
DATABASE = DatabaseSettings(
    url_environment_variable="DATABASE_URL",
    env_file=Path(__file__).resolve().parents[2] / ".env",
)
API = ApiSettings(
    title="HPG Backtest",
    version="0.1.0",
    home_path="/",
    backtests_path="/api/backtests",
)
BACKTEST = BacktestSettings(
    engine_version="0.1.0",
    supported_symbol="HPG",
    result_label="normalized simulation",
)
RESULT = ResultSettings(quantum=Decimal("0.000001"))
CANSLIM_BREAKOUT_V0 = CanslimBreakoutV0Settings(
    strategy_id="canslim_breakout_v0",
    sma_window=200,
    base_window=65,
    max_base_depth=Decimal("0.35"),
    volume_window=50,
    volume_multiplier=Decimal("1.50"),
    buy_zone_multiplier=Decimal("1.05"),
    stop_loss_pct=Decimal("0.07"),
    take_profit_pct=Decimal("0.20"),
    risk_per_trade_pct=Decimal("0.02"),
)


# Runtime secret loading
# Load DATABASE_URL from the process environment, then the local .env file.
def get_database_url(env_file: str | Path | None = None) -> str:
    value = os.getenv(DATABASE.url_environment_variable)
    if value and value.strip():
        return value

    env_path = Path(env_file) if env_file is not None else DATABASE.env_file
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8-sig").splitlines():
            key, separator, value = line.partition("=")
            if separator and key.strip() == DATABASE.url_environment_variable:
                value = value.strip()
                if value.startswith(("'", '"')):
                    if len(value) < 2 or value[-1] != value[0]:
                        raise RuntimeError(f"{DATABASE.url_environment_variable}: unmatched quotes")
                    value = value[1:-1]
                if value.strip():
                    return value

    raise RuntimeError(f"Configure {DATABASE.url_environment_variable} in the project .env or environment")
