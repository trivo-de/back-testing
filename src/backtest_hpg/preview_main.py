"""Runway UI preview: run on localhost:8001 alongside main:app on port 8000."""
from .api.app import create_app
from .application.run_backtest import BacktestService
from .config import get_database_url
from .infrastructure.database import PostgresRunRepository

app = create_app(BacktestService(PostgresRunRepository(get_database_url())), preview=True)
