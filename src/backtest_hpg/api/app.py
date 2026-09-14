"""FastAPI application factory and packaged Web UI route."""

from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import FileResponse
from ..application.run_backtest import BacktestService
from ..config import API
from .backtest_routes import create_backtest_router

def create_app(service: BacktestService) -> FastAPI:
    app = FastAPI(title=API.title, version=API.version)
    app.include_router(create_backtest_router(service))

    @app.get(API.home_path, include_in_schema=False)
    def index():
        """Serve the packaged single-page backtest interface."""

        return FileResponse(Path(__file__).parents[1] / "web" / "index.html")

    return app
