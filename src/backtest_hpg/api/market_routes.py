"""Read-only snapshot chart routes, independent of strategy and database."""

import os
from datetime import date, datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from ..config import VN30F1M_SNAPSHOT_DEFAULT
from ..infrastructure.market_snapshot import LOCAL_TZ, read_snapshot


def create_market_router(snapshot_path: Path | None = None) -> APIRouter:
    router = APIRouter()

    @router.get("/market-chart", include_in_schema=False)
    def chart_page():
        return FileResponse(Path(__file__).parents[1] / "web" / "market-chart.html")

    @router.get("/api/market-chart")
    def market_chart(start: date | None = None, end: date | None = None):
        if start and end and start > end:
            raise HTTPException(422, "Start date must not exceed end date")
        path = snapshot_path or Path(os.getenv("VN30F1M_SNAPSHOT_PATH", VN30F1M_SNAPSHOT_DEFAULT))
        try:
            payload = read_snapshot(path)
        except FileNotFoundError:
            raise HTTPException(503, "VN30F1M snapshot is not installed; see README") from None
        except ValueError:
            raise HTTPException(409, "VN30F1M snapshot failed integrity validation") from None
        except OSError:
            raise HTTPException(503, "VN30F1M snapshot is unavailable") from None
        payload["bars"] = [bar for bar in payload["bars"]
                           if (start is None or datetime.fromtimestamp(bar["time"], LOCAL_TZ).date() >= start)
                           and (end is None or datetime.fromtimestamp(bar["time"], LOCAL_TZ).date() <= end)]
        payload["metadata"]["selected_bars"] = len(payload["bars"])
        return payload

    return router
