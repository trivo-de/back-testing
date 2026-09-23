"""FastAPI application factory and packaged Web UI route."""

from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse
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


class PreviewStaticFiles(WebStaticFiles):
    async def get_response(self, path, scope):
        return await super().get_response("preview-theme.mjs" if path == "theme.mjs" else path, scope)


def create_app(service: BacktestService | None = None, *, snapshot_path: Path | None = None,
               preview: bool = False) -> FastAPI:
    app = FastAPI(title=API.title, version=API.version)
    if service is not None:
        app.include_router(create_backtest_router(service))
    web = Path(__file__).parents[1] / "web"
    static_files = PreviewStaticFiles if preview else WebStaticFiles
    app.mount("/static", static_files(directory=web), name="static")

    def page(filename):
        if not preview:
            return FileResponse(web / filename)
        html = (web / filename).read_text(encoding="utf-8")
        html = html.replace('</head>', '<link rel="stylesheet" href="/static/preview.css"></head>')
        return HTMLResponse(html)

    if preview:
        @app.get("/market-chart", include_in_schema=False)
        def preview_market_chart():
            return page("market-chart.html")

    app.include_router(create_market_router(snapshot_path))

    @app.get(API.home_path, include_in_schema=False)
    def index():
        """Serve the packaged single-page backtest interface."""

        return page("index.html" if service is not None else "market-chart.html")

    return app
