# Composition root used by ``uvicorn backtest_hpg.main:app``.
from .api.app import create_app
from .application.run_backtest import BacktestService
from .config import get_database_url
from .infrastructure.database import PostgresRunRepository

app = create_app(
    BacktestService(PostgresRunRepository(get_database_url()))
)
