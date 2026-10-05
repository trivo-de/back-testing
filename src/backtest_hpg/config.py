# Centralized immutable settings and runtime environment loading.
import os
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

# Schemas
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
class IntradaySettings:
    store: Path
    policy_path: Path

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
VN30F1M_DATASET_ID = "vndirect-vn30f1m-5m-20260316-20260915"
VN30F1M_CONTENT_HASH = "5930f355e7e5bbc8663835a60fca654a31cc5a83184d534008c284a8d3bbaad5"
VN30F1M_SNAPSHOT_DEFAULT = "data/vn30f1m-5m-20260316-20260915.json"

# Approved C06 offline capture; keep the existing chart snapshot unchanged.
INTRADAY_SNAPSHOT_URLS = {
    symbol: "https://dchart-api.vndirect.com.vn/dchart/history?resolution=5"
    f"&symbol={symbol}&from=1772323200&to=1789516800"
    for symbol in ("VN30F1M", "VNINDEX")
}
INTRADAY = IntradaySettings(
    store=Path(os.getenv("BACKTEST_STORE_PATH", "data/backtest-store")),
    policy_path=Path(os.getenv("VN30F1M_POLICY_PATH", "docs/data/vn30f1m/runtime-policy.json")),
)
API = ApiSettings(
    title="HPG Backtest",
    version="0.1.0",
    home_path="/",
    backtests_path="/api/backtests",
)
BACKTEST = BacktestSettings(
    engine_version="0.2.0",
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
