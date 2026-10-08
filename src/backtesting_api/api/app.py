"""FastAPI application factory and packaged Web UI route."""

from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from ..application.run_backtest import BacktestService
from ..config import API
from .backtest_routes import create_backtest_router


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


def create_app(service: BacktestService | None = None, *, preview: bool = False) -> FastAPI:
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

    @app.get(API.home_path, include_in_schema=False)
    def index():
        """Serve the packaged single-page backtest interface."""

        return page("index.html")

    @app.get('/ui-data/{source}', include_in_schema=False)
    def input_data(source: str):
        """Read only the two local snapshots approved for the input form."""
        filenames = {
            'trade_data': 'trade/vn30f1m-5m-20260316-20260915.json',
            'market_data': 'market/VNINDEX_5&from=1772323200&to=1789516800.json',
        }
        filename = filenames.get(source)
        if filename is None:
            raise HTTPException(404, 'Không có nguồn dữ liệu này.')
        path = Path('data') / filename
        if not path.is_file():
            raise HTTPException(404, 'Không tìm thấy file dữ liệu có sẵn. Bạn có thể tải JSON lên.')
        return FileResponse(path, media_type='application/json')

    return app
