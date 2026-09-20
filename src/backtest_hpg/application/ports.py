# Application layer ports for managing backtest runs.
from __future__ import annotations
from typing import Any, Protocol, Sequence
from uuid import UUID
from ..domain.market import DatasetSnapshot
from ..domain.results import BacktestResult
from .contracts import RunConfig

class RunRepository(Protocol):
    """Define run lifecycle operations without coupling the core to PostgreSQL."""

    def get_chart(self, run_id: UUID) -> dict[str, Any] | None:
        """Read bars from the immutable dataset and date range of a successful run."""
        ...

    def start_run(self, config: RunConfig) -> tuple[UUID, DatasetSnapshot]:
        """Create a running record and return its immutable dataset snapshot."""
        ...

    def complete_run(self, run_id: UUID, result: BacktestResult, response: dict[str, Any]) -> None:
        """Persist a successful result and atomically complete the run."""
        ...

    def fail_run(self, run_id: UUID, error: Exception) -> None:
        """Mark a started run as failed with an auditable error."""
        ...

    def get_run(self, run_id: UUID) -> dict[str, Any] | None:
        """Reload one successful run by identifier."""
        ...

    def list_runs(self) -> Sequence[dict[str, Any]]:
        """List successful runs in repository-defined order."""
        ...
