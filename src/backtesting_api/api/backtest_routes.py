from uuid import UUID
from fastapi import APIRouter, HTTPException
from ..application.run_backtest import BacktestService
from ..config import API
from .inline_schemas import InlineRunRequest

def create_backtest_router(service: BacktestService) -> APIRouter:

    router = APIRouter(prefix=API.backtests_path, tags=["backtests"])

    @router.post('/validate')
    def validate_inline(request: InlineRunRequest):
        payload = request.model_dump(mode='json', by_alias=True, exclude_none=True)
        try:
            data, _ = service.validate_inline(payload)
        except ValueError as error:
            raise HTTPException(422, detail=str(error)) from error
        except OSError:
            raise HTTPException(503, detail='INLINE_POLICY_UNAVAILABLE') from None
        return {'status': 'STRUCTURE_VALID', 'runnable': service.inline_runner is not None,
                'data_status': 'RESOLVED', 'data': data.metadata,
                'pending': [] if service.inline_runner is not None else ['U08_STRATEGY_RUNTIME'], 'payload': payload}

    @router.post("", status_code=201)
    def run_backtest(request: InlineRunRequest):
        """Validate and execute one synchronous backtest request."""

        try:
            return service.run_inline(request.model_dump(mode='json', by_alias=True, exclude_none=True))
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except (OSError, KeyError, TypeError):
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

    @router.get('/{run_id}/input')
    def get_input(run_id: UUID):
        try:
            document = service.get_input(run_id)
        except (ValueError, OSError, KeyError, TypeError):
            raise HTTPException(409, detail='INPUT_STORAGE_INVALID') from None
        if document is None: raise HTTPException(404, detail='run not found')
        return document

    return router

