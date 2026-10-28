from uuid import UUID
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Literal
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from ..application.run_backtest import BacktestService
from ..config import API
from .price_schemas import PriceRunRequest
from ..infrastructure.auto_fetch_data import AutoFetchError


# Describe one saved run in a history response.
class HistoryItem(BaseModel):
    run_id: UUID
    run_at: datetime | None = None
    symbol: str | None = None
    resolution: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    money_unit: str | None = None
    pnl_unit: str | None = None
    schema_version: int | None = None
    total_return: str | None = None
    final_equity: str | None = None
    realized_pnl: str | None = None
    unrealized_pnl: str | None = None
    total_pnl: str | None = None
    max_drawdown: str | None = None
    closed_positions: int | None = None
    open_positions: int | None = None
    win_rate: str | None = None


# Describe a history page and its continuation cursor.
class HistoryPage(BaseModel):
    items: list[HistoryItem]
    next_cursor: UUID | None = None


# Bind backtest validation, execution, and retrieval routes to the service.
def create_backtest_router(service: BacktestService) -> APIRouter:

    router = APIRouter(prefix=API.backtests_path, tags=["backtests"])

    # Validate request data and report whether the configured runner is available.
    @router.post('/validate')
    def validate_inline(request: PriceRunRequest):
        try:
            data, _, _, spec, original = service.prepare_price(request)
            from ..application.inline_results import exact_json
            return exact_json({'valid': True, 'payload': original, 'effective_config': spec,
                               'data_metadata': data.metadata, 'warnings': data.metadata['warnings']})
        except ValueError as error:
            raise HTTPException(422, detail=str(error)) from error
        except AutoFetchError as error:
            raise HTTPException(503, detail=str(error)) from error
        except OSError:
            raise HTTPException(503, detail='INLINE_POLICY_UNAVAILABLE') from None

    @router.post("", status_code=201)
    def run_backtest(request: PriceRunRequest):
        """Validate and execute one synchronous backtest request."""

        try:
            return service.run_price(request)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except AutoFetchError as error:
            raise HTTPException(503, detail=str(error)) from error
        except (OSError, KeyError, TypeError):
            raise HTTPException(status_code=503, detail={"code": "BACKTEST_STORAGE_UNAVAILABLE"}) from None

    @router.get("")
    def list_backtests():
        """Return persisted successful runs in repository order."""

        try:
            return service.list()
        except (ValueError, OSError, KeyError, TypeError):
            raise HTTPException(status_code=409, detail={"code": "RESULT_STORAGE_INVALID"}) from None

    # Return a filtered page of saved runs after validating filter bounds.
    @router.get('/history', response_model=HistoryPage)
    def history(min_total_return_pct: Decimal | None = Query(None, allow_inf_nan=False),
                max_total_return_pct: Decimal | None = Query(None, allow_inf_nan=False),
                min_equity: Decimal | None = Query(None, allow_inf_nan=False),
                max_equity: Decimal | None = Query(None, allow_inf_nan=False),
                unit: Literal['all', 'point_quantity', 'legacy'] = 'all',
                min_total_pnl: Decimal | None = Query(None, allow_inf_nan=False),
                max_total_pnl: Decimal | None = Query(None, allow_inf_nan=False),
                min_realized_pnl: Decimal | None = Query(None, allow_inf_nan=False),
                max_realized_pnl: Decimal | None = Query(None, allow_inf_nan=False),
                min_max_drawdown: Decimal | None = Query(None, ge=0, allow_inf_nan=False),
                max_max_drawdown: Decimal | None = Query(None, ge=0, allow_inf_nan=False),
                min_closed_positions: int | None = Query(None, ge=0),
                max_closed_positions: int | None = Query(None, ge=0),
                sort_by: Literal['run_id', 'total_pnl', 'realized_pnl', 'max_drawdown', 'closed_positions'] = 'run_id',
                sort_order: Literal['asc', 'desc'] = 'desc',
                limit: int = Query(20, ge=1, le=100), after: UUID | None = None):
        point_pairs = ((min_total_pnl, max_total_pnl), (min_realized_pnl, max_realized_pnl),
                       (min_max_drawdown, max_max_drawdown), (min_closed_positions, max_closed_positions))
        legacy_pairs = ((min_total_return_pct, max_total_return_pct), (min_equity, max_equity))
        for low, high in (*legacy_pairs, *point_pairs):
            if low is not None and high is not None and low > high:
                raise HTTPException(422, detail='Giá trị từ phải nhỏ hơn hoặc bằng giá trị đến.')
        has_points = any(value is not None for pair in point_pairs for value in pair) or sort_by != 'run_id'
        has_legacy = any(value is not None for pair in legacy_pairs for value in pair)
        if (has_points and (has_legacy or unit == 'legacy')) or (has_legacy and unit == 'point_quantity'):
            raise HTTPException(422, detail='INCOMPATIBLE_HISTORY_UNITS')
        try:
            return service.history(min_total_return=min_total_return_pct / 100 if min_total_return_pct is not None else None,
                                   max_total_return=max_total_return_pct / 100 if max_total_return_pct is not None else None,
                                   min_equity=min_equity, max_equity=max_equity, unit=unit,
                                   min_total_pnl=min_total_pnl, max_total_pnl=max_total_pnl,
                                   min_realized_pnl=min_realized_pnl, max_realized_pnl=max_realized_pnl,
                                   min_max_drawdown=min_max_drawdown, max_max_drawdown=max_max_drawdown,
                                   min_closed_positions=min_closed_positions, max_closed_positions=max_closed_positions,
                                   sort_by=sort_by, sort_order=sort_order, limit=limit, after=after)
        except (ValueError, InvalidOperation, OSError, KeyError, TypeError):
            raise HTTPException(409, detail={'code': 'RESULT_STORAGE_INVALID'}) from None

    @router.get("/{run_id}")
    def get_backtest(run_id: UUID):
        """Return one persisted successful run or HTTP 404."""

        try:
            result = service.get(run_id)
        except (ValueError, OSError, KeyError, TypeError):
            raise HTTPException(status_code=409, detail={"code": "RESULT_STORAGE_INVALID"}) from None
        if result is None:
            raise HTTPException(status_code=404, detail="run not found")
        return result

    # Return chart data for a saved run or translate storage errors to HTTP errors.
    @router.get("/{run_id}/chart")
    def get_chart(run_id: UUID):
        try:
            chart = service.get_chart(run_id)
        except ValueError:
            raise HTTPException(409, detail={"code": "CHART_DATA_INCONSISTENT"}) from None
        except Exception:
            raise HTTPException(500, detail={"code": "CHART_STORAGE_ERROR"}) from None
        if chart is None:
            raise HTTPException(404, detail={"code": "RUN_NOT_FOUND"})
        return chart

    # Return the pinned input document for a saved run.
    @router.get('/{run_id}/input')
    def get_input(run_id: UUID):
        try:
            document = service.get_input(run_id)
        except (ValueError, OSError, KeyError, TypeError):
            raise HTTPException(409, detail='INPUT_STORAGE_INVALID') from None
        if document is None: raise HTTPException(404, detail='run not found')
        return document

    return router

