"""FastAPI application factory and packaged Web UI route."""

from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from ..application.run_backtest import BacktestService
from ..config import API
from .backtest_routes import create_backtest_router
from .market_routes import create_market_router


class WebStaticFiles(StaticFiles):
    """Serve JavaScript modules with a browser-valid MIME type on every OS."""

    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        if path.lower().endswith('.mjs') and response.status_code == 200:
            response.headers['content-type'] = 'text/javascript; charset=utf-8'
        return response


def create_app(service: BacktestService | None = None, *, snapshot_path: Path | None = None) -> FastAPI:
    app = FastAPI(title=API.title, version=API.version)
    if service is not None:
        app.include_router(create_backtest_router(service))
    app.include_router(create_market_router(snapshot_path))
    web = Path(__file__).parents[1] / "web"
    app.mount("/static", WebStaticFiles(directory=web), name="static")

    @app.get(API.home_path, include_in_schema=False)
    def index():
        """Serve the packaged single-page backtest interface."""

        return FileResponse(web / ("index.html" if service is not None else "market-chart.html"))

    return app
