"""Shared application entrypoint; backend selection never depends on the port."""
import os
from pathlib import Path
from .api.app import create_app
from .application.run_backtest import BacktestService
from .config import get_database_url, INTRADAY
from .infrastructure.file_repository import FileRunRepository
from .infrastructure.database import PostgresRunRepository
from .application.inline_strategy import run_inline_strategy

def build_service():
    files = FileRunRepository(INTRADAY.store, INTRADAY.policy_path)
    backend = os.getenv('BACKTEST_LEGACY_BACKEND', 'file')
    if backend not in ('file', 'postgres'):
        raise ValueError('BACKTEST_LEGACY_BACKEND must be file or postgres')
    legacy = PostgresRunRepository(get_database_url()) if backend == 'postgres' else files
    return BacktestService(legacy, inline_repository=files, inline_runner=run_inline_strategy,
                          inline_policy_path=Path(os.getenv('INLINE_POLICY_PATH', 'docs/data/vn30f1m/runtime-policy-v1.json')))


app = create_app(build_service(), preview=True)
