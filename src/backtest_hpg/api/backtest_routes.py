from uuid import UUID
from fastapi import APIRouter, HTTPException
from pydantic import ValidationError
from ..application.contracts import RunConfig
from ..application.run_backtest import BacktestService
from ..config import API
from ..domain.strategies import describe_strategy, strategies
from .backtest_schemas import RunRequest

def create_backtest_router(service: BacktestService) -> APIRouter:

    router = APIRouter(prefix=API.backtests_path, tags=["backtests"])

    @router.post("", status_code=201)
    def run_backtest(request: RunRequest):
        """Validate and execute one synchronous backtest request."""

        try:
            return service.run(RunConfig(**request.model_dump()))
        except ValidationError as error:
            raise HTTPException(status_code=422, detail=[
                {"loc": ["body", "strategy_params", *item["loc"]], "type": item["type"],
                 "msg": "Tham số không hợp lệ", "reason": item["msg"]}
                for item in error.errors(include_input=False, include_context=False)
            ]) from error
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except (OSError, KeyError, TypeError) as error:
            raise HTTPException(status_code=503, detail={"code": "BACKTEST_STORAGE_UNAVAILABLE"}) from None

    @router.get("")
    def list_backtests():
        """Return persisted successful runs in repository order."""

        try:
            return service.list()
        except (ValueError, OSError, KeyError, TypeError):
            raise HTTPException(status_code=409, detail={"code": "RESULT_STORAGE_INVALID"}) from None

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

    return router


def create_strategy_router() -> APIRouter:
    router = APIRouter(prefix="/api/strategies", tags=["strategies"])

    @router.get("")
    def list_strategies():
        return [{"strategy_id": key, "strategy_version": value.version,
                 "required_capabilities": sorted(value.required_capabilities)}
                for key, value in strategies.items()]

    @router.get("/{strategy_id}")
    def get_strategy_schema(strategy_id: str, version: str | None = None):
        try:
            return describe_strategy(strategy_id, version)
        except ValueError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    return router
