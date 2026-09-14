# HTTP request schemas for backtest endpoints.
from datetime import date
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field
from ..config import BACKTEST, CANSLIM_BREAKOUT_V0

class RunRequest(BaseModel):
    """Validate the external payload used to start one backtest run."""
    model_config = ConfigDict(extra="forbid")

    dataset_id: str = Field(min_length=1)
    dataset_version: str = Field(min_length=1)
    symbol: str = BACKTEST.supported_symbol
    start_date: date
    end_date: date
    strategy_id: str = CANSLIM_BREAKOUT_V0.strategy_id
    initial_cash: Decimal = Field(gt=0)
    fee_rate: Decimal = Field(ge=0)
    slippage_rate: Decimal = Field(ge=0, lt=1)
