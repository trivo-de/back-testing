# Application layer ports for managing backtest runs.
from __future__ import annotations
from typing import Any, Protocol, Sequence
from uuid import UUID

class RunRepository(Protocol):
    """Define run lifecycle operations for the JSON backtest store."""

    def start_inline(self, payload: dict[str, Any], policy: dict[str, Any] | None, data: Any) -> tuple[UUID, str, str]:
        """Pin the complete request and policy without requiring a registered dataset."""
        ...

    def get_input(self, run_id: UUID) -> dict[str, Any] | None:
        """Reload input document by run identifier."""
        ...

    def get_chart(self, run_id: UUID) -> dict[str, Any] | None:
        """Read bars from the immutable dataset and date range of a successful run."""
        ...

    def complete_run(self, run_id: UUID, result: Any, response: dict[str, Any]) -> None:
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

