from uuid import UUID
from fastapi import APIRouter, HTTPException
from ..application.contracts import RunConfig
from ..application.run_backtest import BacktestService
from ..config import API
from .backtest_schemas import RunRequest

def create_backtest_router(service: BacktestService) -> APIRouter:

    router = APIRouter(prefix=API.backtests_path, tags=["backtests"])

    @router.post("", status_code=201)
    def run_backtest(request: RunRequest):
        """Validate and execute one synchronous backtest request."""

        try:
            return service.run(RunConfig(**request.model_dump()))
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @router.get("")
    def list_backtests():
        """Return persisted successful runs in repository order."""

        return service.list()

    @router.get("/{run_id}")
    def get_backtest(run_id: UUID):
        """Return one persisted successful run or HTTP 404."""

        result = service.get(run_id)
        if result is None:
            raise HTTPException(status_code=404, detail="run not found")
        return result

    return router
