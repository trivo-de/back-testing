"""Keep legacy engine/storage regression routes isolated from the production API."""
from fastapi import HTTPException
from backtesting_api.api.app import create_app
from backtesting_api.api.inline_schemas import InlineRunRequest
from backtesting_api.infrastructure.auto_fetch_data import AutoFetchError


def legacy_inline_app(service):
    """Mount legacy POSTs only on a test-only prefix; GETs still use production routes."""
    app = create_app(service)

    @app.post('/internal-test/legacy/backtests/validate')
    def validate_legacy(request: InlineRunRequest):
        """Exercise the retained legacy normalization and data-preparation use case."""
        payload = request.model_dump(mode='json', by_alias=True, exclude_none=True)
        try:
            data, _ = service.validate_inline(payload)
        except ValueError as error:
            raise HTTPException(422, detail=str(error)) from error
        except AutoFetchError as error:
            raise HTTPException(503, detail=str(error)) from error
        except OSError:
            raise HTTPException(503, detail='INLINE_POLICY_UNAVAILABLE') from None
        return {'status': 'STRUCTURE_VALID', 'runnable': service.inline_runner is not None,
                'data_status': 'RESOLVED', 'data': data.metadata,
                'pending': [] if service.inline_runner is not None else ['U08_STRATEGY_RUNTIME'], 'payload': payload}

    @app.post('/internal-test/legacy/backtests', status_code=201)
    def run_legacy(request: InlineRunRequest):
        """Seed and verify old-format artifacts without exposing legacy input publicly."""
        try:
            return service.run_inline(request.model_dump(mode='json', by_alias=True, exclude_none=True))
        except ValueError as error:
            raise HTTPException(422, detail=str(error)) from error
        except AutoFetchError as error:
            raise HTTPException(503, detail=str(error)) from error
        except (OSError, KeyError, TypeError):
            raise HTTPException(503, detail={'code': 'BACKTEST_STORAGE_UNAVAILABLE'}) from None

    return app
