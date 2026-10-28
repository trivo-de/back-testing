from dataclasses import replace
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Sequence
from uuid import UUID
import json
from pathlib import Path
from .inline_data import resolve_inline
from .inline_results import inline_result_to_dict
from .ports import RunRepository
from ..infrastructure.auto_fetch_data import AutoFetchError
from .inline_strategy import check_runtime
from .order_config import strategy_orders
from ..domain.strategy_terms import required_history

# Compute required history from indicator seeds, warm-up, and shifted references.
def _warmup_bars(strategy):
    return required_history(strategy)


class BacktestService:
    """Coordinate a strategy run through the repository lifecycle."""

    def __init__(self, repository: RunRepository, *, inline_runner=None,
                 inline_policy_path=Path('docs/data/vn30f1m/runtime-policy-v1.json'),
                 auto_fetch_policy_path=Path('docs/data/vn30f1m/runtime-policy.json'), data_fetcher=None):
        """Bind the use case to a repository port implementation."""

        self.repository = repository
        self.inline_runner = inline_runner
        self.inline_policy_path = Path(inline_policy_path)
        self.auto_fetch_policy_path = Path(auto_fetch_policy_path)
        self.data_fetcher = data_fetcher


    def prepare_inline(self, payload):
        """Resolve supplied or automatically fetched data without creating a run."""
        fetch_metadata = None
        policy = None
        if payload.get('auto_fetch_data'):
            if self.data_fetcher is None:
                raise AutoFetchError('AUTO_FETCH_UNAVAILABLE')
            history_start = None
            if payload['accounting']['model'] == 'contract':
                mapping_policy = json.loads(self.auto_fetch_policy_path.read_bytes())
                if not mapping_policy['rollover']:
                    raise ValueError('CONTRACT_MAP_COVERAGE_MISSING')
                policy = json.loads(self.inline_policy_path.read_bytes())
                history_start = max(
                    policy['calendar_range']['start'],
                    date.fromisoformat(mapping_policy['rollover'][0]['expiry']).replace(day=1).isoformat())
            report = payload.get('report')
            if report:
                entry_actions, _ = strategy_orders(payload)
                warmup = max(_warmup_bars(payload['strategy']),
                             int(any(action['order']['type'] == 'ATO' for action in entry_actions.values())))
                calendar_policy = policy or (json.loads(self.inline_policy_path.read_bytes()) if warmup else None)
                resolved, fetch_metadata = self.data_fetcher.fetch_by_range(
                    report['start_date'], report['end_date'], warmup_bars=warmup,
                    session_policy=calendar_policy, continuous_only=payload['accounting']['model'] == 'contract',
                    history_start=history_start)
            else:
                resolved, fetch_metadata = self.data_fetcher.fetch()
            if payload['accounting']['model'] == 'contract':
                resolved['trade_data']['contract_map'] = [
                    {'contract_code': row['contract'], 'expiry_date': row['expiry'],
                     'expiry_unix': row['expiry_unix']} for row in mapping_policy['rollover']]
                fetch_metadata['rollover_source'] = mapping_policy['rollover_source']
                if payload['execution'].get('matching_model') == 'hnx_sessions_v1':
                    fetch_metadata['contract_mapping_assumption'] = 'expiry_inclusive'
                    resolved['trade_data']['provenance'] = {
                        'provider': fetch_metadata['provider'], 'timestamp_convention': 'bar_open',
                        'note': ('Tự lấy nến 5 phút; timestamp được diễn giải là đầu nến, '
                                 'Close và available_at bằng Open + 5 phút theo quy ước mô phỏng. '
                                 'Dùng bảng đáo hạn đã cung cấp để gắn mã theo giả định đã được người dùng đồng ý: '
                                 'giữ mã cũ đến hết ngày đáo hạn, chuyển mã từ ngày sau đó. '
                                 'Chưa đối chiếu lịch chuyển mã và timestamp với nhà cung cấp.')}
            payload.update(resolved)
            payload['auto_fetch_data'] = False
        if policy is None and (payload['trade_data'].get('contract_map')
                               or payload['execution'].get('matching_model') == 'hnx_sessions_v1'):
            policy = json.loads(self.inline_policy_path.read_bytes())
        data = resolve_inline(payload, policy, derive_contract_dates=(
            fetch_metadata is not None and payload['execution'].get('matching_model') == 'hnx_sessions_v1'))
        if fetch_metadata is not None:
            data = replace(data, metadata={**data.metadata, 'input_origin': 'auto_fetch',
                                           'auto_fetch': fetch_metadata})
        return data, policy

    def validate_inline(self, payload):
        """Apply the same data and runtime checks used immediately before a run."""
        data, policy = self.prepare_inline(payload)
        if any(bar.available_at != bar.closed_at for bar in data.bars):
            raise ValueError('PRIMARY_AVAILABILITY_DELAY_UNSUPPORTED')
        check_runtime(payload)
        return data, policy

    def run_inline(self, payload):
        """Use an explicit inline runner; never substitute a legacy strategy."""
        data, policy = self.validate_inline(payload)
        if self.inline_runner is None:
            raise ValueError('INLINE_STRATEGY_RUNTIME_NOT_IMPLEMENTED')
        run_at = datetime.now(timezone.utc).isoformat()
        run_id, input_hash, policy_hash = self.repository.start_inline(payload, policy, data)
        try:
            result = self.inline_runner(data, payload)
            if any(not data.start_date <= fill.fill_date.date() <= data.end_date for fill in result.fills):
                raise ValueError('FILL_OUTSIDE_REPORT_RANGE')
            response = inline_result_to_dict(run_id, data, result, input_hash=input_hash,
                                             policy_hash=policy_hash, accounting=payload['accounting'])
            response['metadata']['run_at'] = run_at
            self.repository.complete_run(run_id, result, response)
            return response
        except Exception as error:
            self.repository.fail_run(run_id, error)
            raise

    def get(self, run_id: UUID) -> dict[str, Any] | None:
        """Return one successful persisted run if it exists."""
        return self.repository.get_run(run_id)

    def prepare_price(self, request):
        """Fetch and validate a price-only snapshot without fabricating accounting."""
        from ..api.inline_schemas import DataInput
        from pydantic import ValidationError
        from .price_strategy import resolve_price_data
        spec = request.compiled()
        if self.data_fetcher is None:
            raise AutoFetchError('AUTO_FETCH_UNAVAILABLE')
        policy = json.loads(self.inline_policy_path.read_bytes())
        payload = request.model_dump(mode='json', by_alias=True, exclude_none=True, exclude_unset=True)
        if request.from_ is not None:
            sources, metadata = self.data_fetcher.fetch_by_range(
                request.from_, request.to, warmup_bars=spec['required_history'], session_policy=policy,
                continuous_only=True)
        else:
            sources, metadata = self.data_fetcher.fetch()
        mapping = json.loads(self.auto_fetch_policy_path.read_bytes()).get('rollover', [])
        if not isinstance(sources, dict) or not isinstance(sources.get('trade_data'), dict):
            raise ValueError('AUTO_FETCH_INVALID_SOURCE')
        sources['trade_data'] = {**sources['trade_data'], 'contract_map': [
            {'contract_code': row['contract'], 'expiry_date': row['expiry'], 'expiry_unix': row['expiry_unix']}
            for row in mapping]}
        try:
            sources = {name: DataInput.model_validate(source).model_dump(mode='json', exclude_none=True)
                       for name, source in sources.items()}
        except ValidationError as error:
            raise ValueError('AUTO_FETCH_INVALID_SOURCE') from error
        if any(source['resolution'] != '5' or source['timezone'] != 'Asia/Ho_Chi_Minh' for source in sources.values()):
            raise ValueError('SOURCE_REQUIRES_5M_LOCAL_TIME')
        data = resolve_price_data(sources, payload, policy, metadata)
        return data, policy, sources, spec, payload

    def run_price(self, request):
        """Pin the request and source snapshot, run, and atomically save schema 3."""
        from .price_strategy import run_price_strategy
        from .inline_results import exact_json
        data, policy, sources, spec, payload = self.prepare_price(request)
        snapshot = {'request': payload, 'sources': sources, 'effective_config': exact_json(spec)}
        run_id, input_hash, policy_hash = self.repository.start_inline(snapshot, policy, data)
        try:
            result = run_price_strategy(data, spec, sources, policy)
            response = exact_json({'schema_version': 3, **result, 'metadata': {
                **data.metadata, 'run_id': str(run_id), 'run_at': datetime.now(timezone.utc).isoformat(),
                'input_hash': input_hash, 'policy_hash': policy_hash, 'effective_config': spec,
                'default_profile_version': spec['default_profile_version'],
                'engine_version': 'price-only-v2',
                'assumptions': {'immediate': 'decision -> order -> full fill at same Close; zero latency',
                                'lo': 'next observed bar; better Open or limit touch; 3 bars/DAY',
                                'costs': 'no fees, slippage, margin or multiplier', 'allow_overnight': False,
                                'session_end': 'expire pending orders; close remaining quantity at scheduled final continuous candle Close'}}})
            self.repository.complete_run(run_id, result, response)
            return response
        except Exception as error:
            self.repository.fail_run(run_id, error)
            raise

    def list(self) -> Sequence[dict[str, Any]]:
        """Return successful persisted runs."""
        return self.repository.list_runs()

    def history(self, *, min_total_return=None, max_total_return=None,
                min_equity=None, max_equity=None, unit='all',
                min_total_pnl=None, max_total_pnl=None, min_realized_pnl=None, max_realized_pnl=None,
                min_max_drawdown=None, max_max_drawdown=None, min_closed_positions=None, max_closed_positions=None,
                sort_by='run_id', sort_order='desc', limit=20, after=None):
        """Filter compact summaries by their original units and paginate without mixing metrics."""
        point_bounds = {'total_pnl': (min_total_pnl, max_total_pnl),
                        'realized_pnl': (min_realized_pnl, max_realized_pnl),
                        'max_drawdown': (min_max_drawdown, max_max_drawdown),
                        'closed_positions': (min_closed_positions, max_closed_positions)}
        legacy_bounds = {'total_return': (min_total_return, max_total_return),
                         'final_equity': (min_equity, max_equity)}
        has_points = any(value is not None for pair in point_bounds.values() for value in pair)
        has_legacy = any(value is not None for pair in legacy_bounds.values() for value in pair)

        def matches(item):
            """Compare only fields that have the requested meaning and finite values."""
            point = item.get('pnl_unit') == 'point_quantity'
            if ((unit == 'point_quantity' and not point) or (unit == 'legacy' and point)
                    or (has_points and not point) or (has_legacy and point)
                    or (sort_by != 'run_id' and not point)):
                return False
            bounds = point_bounds if point else legacy_bounds
            for name, (low, high) in bounds.items():
                value = Decimal(str(item[name]))
                if not value.is_finite():
                    raise ValueError('RESULT_SUMMARY_INVALID')
                if (low is not None and value < low) or (high is not None and value > high):
                    return False
            return True

        if sort_by == 'run_id' and sort_order == 'desc':
            items = []
            for item in self.repository.iter_run_summaries(after):
                if not matches(item):
                    continue
                if len(items) == limit:
                    return {'items': items, 'next_cursor': items[-1]['run_id']}
                items.append(item)
            return {'items': items, 'next_cursor': None}
        # Sorting metrics needs only compact summaries, never a list of full run documents.
        candidates = [item for item in self.repository.iter_run_summaries() if matches(item)]
        candidates.sort(key=lambda item: (item['run_id'] if sort_by == 'run_id' else Decimal(str(item[sort_by])),
                                          item['run_id']), reverse=sort_order == 'desc')
        if after is not None:
            cursor = next((index for index, item in enumerate(candidates) if item['run_id'] == str(after)), None)
            candidates = candidates[cursor + 1:] if cursor is not None else []
        items = candidates[:limit]
        return {'items': items, 'next_cursor': items[-1]['run_id'] if len(candidates) > limit else None}

    def replay_price(self, run_id):
        """Reproduce business events using only pinned sources, calendar and resolved defaults."""
        from .price_strategy import resolve_price_data, run_price_strategy
        from .inline_results import exact_json
        document = self.repository.get_input(run_id)
        if document is None or document.get('schema_version') != 2:
            raise ValueError('PRICE_SNAPSHOT_REQUIRED')
        snapshot = document['payload']
        data = resolve_price_data(snapshot['sources'], snapshot['request'], document['policy'],
                                  document['data_metadata']['auto_fetch'])
        return exact_json(run_price_strategy(data, snapshot['effective_config'], snapshot['sources'], document['policy']))

    def get_chart(self, run_id: UUID) -> dict[str, Any] | None:
        """Read chart data without executing the strategy again."""
        return self.repository.get_chart(run_id)

    # Read the saved input document through the configured repository.
    def get_input(self, run_id: UUID):
        return self.repository.get_input(run_id)
