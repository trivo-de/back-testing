"""Shared application entrypoint; backend selection never depends on the port."""
import os
from pathlib import Path
from .api.app import create_app
from .application.run_backtest import BacktestService
from .config import INTRADAY
from .infrastructure.file_repository import FileRunRepository
from .application.inline_strategy import run_inline_strategy

def build_service():
    files = FileRunRepository(INTRADAY.store, INTRADAY.policy_path)
    return BacktestService(
        files, inline_repository=files, inline_runner=run_inline_strategy,
        inline_policy_path=Path(os.getenv('INLINE_POLICY_PATH', 'docs/data/vn30f1m/runtime-policy-v1.json')),
        auto_fetch_policy_path=Path(os.getenv('AUTO_FETCH_POLICY_PATH', 'docs/data/vn30f1m/runtime-policy.json')),
    )


app = create_app(build_service(), preview=True)
