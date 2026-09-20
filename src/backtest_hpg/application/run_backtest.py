from typing import Any, Sequence
from uuid import UUID
from ..domain.strategies import get_strategy, get_strategy_parameters
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

        run_id, dataset = self.repository.start_run(config)
        try:
            market_arguments = {"market_bars": dataset.market_bars} if config.symbol == "VN30F1M" else {}
            result = get_strategy(config.strategy_id)(
                dataset.bars,
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
                strategy_parameters=get_strategy_parameters(config.strategy_id),
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
