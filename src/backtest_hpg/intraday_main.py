"""Local Parquet/JSON composition root; no database or agent is required."""

from .api.app import create_app
from .application.run_backtest import BacktestService
from .config import INTRADAY
from .infrastructure.file_repository import FileRunRepository

app = create_app(BacktestService(FileRunRepository(INTRADAY.store, INTRADAY.policy_path)))
