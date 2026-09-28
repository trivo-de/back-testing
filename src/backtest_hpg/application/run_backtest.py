from typing import Any, Sequence
from dataclasses import replace
from copy import deepcopy
from datetime import date
from uuid import UUID
from ..domain.strategies import get_strategy_definition
from .contracts import RunConfig
from .ports import RunRepository
from .result_mapper import result_to_dict


class BacktestService:
    """Coordinate a strategy run through the repository lifecycle."""

    def __init__(self, repository: RunRepository):
        """Bind the use case to a repository port implementation."""

        self.repository = repository

    def run(self, config: RunConfig) -> dict[str, Any]:
        """Load a fixed dataset, run the selected strategy, and persist the result."""

        definition = get_strategy_definition(config.strategy_id, config.strategy_version)
        values = {} if config.strategy_params is None else config.strategy_params
        params = definition.parameter_model.model_validate(values)
        requirements = definition.data_requirements(params)
        if set(requirements) - {"primary", "market"}:
            raise ValueError("UNSUPPORTED_DATA_REQUIREMENTS")
        if "market" in requirements and requirements["market"].get("symbol") != "VNINDEX":
            raise ValueError("UNSUPPORTED_DATA_REQUIREMENTS: market symbol")
        # Sao chép yêu cầu để các lần chạy không dùng chung đối tượng tham số.
        config = replace(config, strategy_version=definition.version,
                         strategy_params=deepcopy(values))
        run_id, dataset = self.repository.start_run(config)
        try:
            market_arguments = {}
            if "market" in requirements:
                if dataset.market_bars:
                    market_arguments["market_bars"] = dataset.market_bars
                elif any(bar.index_close is None for bar in dataset.bars):
                    raise ValueError("MISSING_REQUIRED_DATA: market")
            if dataset.metadata.get("rollover_action") == "close_at_expiry_open":
                market_arguments["flat_dates"] = frozenset(date.fromisoformat(value) for value in dataset.metadata["expiry_dates"])
            result = definition.runner(
                dataset.bars,
                params=params,
                initial_cash=config.initial_cash,
                fee_rate=config.fee_rate,
                slippage_rate=config.slippage_rate,
                start_date=config.start_date,
                end_date=config.end_date,
                **market_arguments,
            )
            response = result_to_dict(
                run_id,
                dataset.metadata,
                config,
                result,
                strategy_parameters=params.model_dump(mode="json"),
            )
            self.repository.complete_run(run_id, result, response)
            return response
        except Exception as error:
            self.repository.fail_run(run_id, error)
            raise

    def get(self, run_id: UUID) -> dict[str, Any] | None:
        """Return one successful persisted run if it exists."""

        return self.repository.get_run(run_id)

    def list(self) -> Sequence[dict[str, Any]]:
        """Return successful persisted runs."""

        return self.repository.list_runs()

    def get_chart(self, run_id: UUID) -> dict[str, Any] | None:
        """Read chart data without executing the strategy again."""
        return self.repository.get_chart(run_id)
