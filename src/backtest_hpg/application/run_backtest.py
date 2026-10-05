from dataclasses import replace
from typing import Any, Sequence
from uuid import UUID
import json
from pathlib import Path
from .inline_data import resolve_inline
from .inline_results import inline_result_to_dict
from .ports import RunRepository


class BacktestService:
    """Coordinate a strategy run through the repository lifecycle."""

    def __init__(self, repository: RunRepository, *, inline_repository=None, inline_runner=None,
                 inline_policy_path=Path('docs/data/vn30f1m/runtime-policy-v1.json'),
                 auto_fetch_policy_path=Path('docs/data/vn30f1m/runtime-policy.json'), data_fetcher=None):
        """Bind the use case to a repository port implementation."""

        self.repository = repository
        self.inline_repository = inline_repository if inline_repository is not None else repository
        self.inline_runner = inline_runner
        self.inline_policy_path = Path(inline_policy_path)
        self.auto_fetch_policy_path = Path(auto_fetch_policy_path)
        self.data_fetcher = data_fetcher

    def prepare_inline(self, payload):
        """Resolve supplied or automatically fetched data without creating a run."""
        fetch_metadata = None
        if payload.get('auto_fetch_data'):
            policy = json.loads(self.auto_fetch_policy_path.read_bytes())
            supplied_report = payload.get('report')
            resolved, fetch_metadata = self.data_fetcher.fetch(policy)
            payload.update(resolved)
            if supplied_report is not None:
                payload['report'] = supplied_report
            payload['auto_fetch_data'] = False
        else:
            policy = (json.loads(self.inline_policy_path.read_bytes())
                      if payload['trade_data'].get('contract_map') else None)
        data = resolve_inline(payload, policy)
        if fetch_metadata is not None:
            data = replace(data, metadata={**data.metadata, 'input_origin': 'auto_fetch',
                                           'auto_fetch': fetch_metadata})
        return data, policy

    def validate_inline(self, payload):
        """Apply the same data and runtime checks used immediately before a run."""
        data, policy = self.prepare_inline(payload)
        if any(bar.available_at != bar.closed_at for bar in data.bars):
            raise ValueError('PRIMARY_AVAILABILITY_DELAY_UNSUPPORTED')
        from .inline_strategy import check_runtime
        check_runtime(payload)
        return data, policy

    def run_inline(self, payload):
        """Use an explicit inline runner; never substitute a legacy strategy."""
        data, policy = self.validate_inline(payload)
        if self.inline_runner is None:
            raise ValueError('INLINE_STRATEGY_RUNTIME_NOT_IMPLEMENTED: U08')
        run_id, input_hash, policy_hash = self.inline_repository.start_inline(payload, policy, data)
        try:
            result = self.inline_runner(data, payload)
            if any(not data.start_date <= fill.fill_date.date() <= data.end_date for fill in result.fills):
                raise ValueError('FILL_OUTSIDE_REPORT_RANGE')
            response = inline_result_to_dict(run_id, data, result, input_hash=input_hash,
                                             policy_hash=policy_hash, accounting=payload['accounting'])
            self.inline_repository.complete_run(run_id, result, response)
            return response
        except Exception as error:
            self.inline_repository.fail_run(run_id, error)
            raise

    def get(self, run_id: UUID) -> dict[str, Any] | None:
        """Return one successful persisted run if it exists."""

        result = self.inline_repository.get_run(run_id)
        return (self.repository.get_run(run_id)
                if result is None and self.inline_repository is not self.repository else result)

    def list(self) -> Sequence[dict[str, Any]]:
        """Return successful persisted runs."""

        results = self.inline_repository.list_runs()
        return (results + list(self.repository.list_runs())
                if self.inline_repository is not self.repository else results)

    def get_chart(self, run_id: UUID) -> dict[str, Any] | None:
        """Read chart data without executing the strategy again."""
        result = self.inline_repository.get_chart(run_id)
        return (self.repository.get_chart(run_id)
                if result is None and self.inline_repository is not self.repository else result)

    def get_input(self, run_id):
        if not hasattr(self.inline_repository, 'get_input'):
            raise ValueError('INLINE_INPUT_NOT_AVAILABLE_FOR_LEGACY_RUN')
        return self.inline_repository.get_input(run_id)
