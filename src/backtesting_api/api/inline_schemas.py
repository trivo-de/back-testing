from datetime import date, datetime, time
from decimal import Decimal
from typing import Annotated, Literal, get_args
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import re
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, model_validator
from ..domain.expressions import STATE_REFS, validate_expression
from ..infrastructure.market_snapshot import normalize_raw_source
from ..application.order_config import strategy_orders
from ..domain.orders import MARKET_TYPES

Positive = Annotated[Decimal, Field(gt=0, allow_inf_nan=False)]
Nonnegative = Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]
Period = Annotated[StrictInt, Field(gt=0)]
AuctionQuantity = Annotated[StrictInt, Field(ge=0)]


# Reject unknown fields and nonfinite numbers in request models.
class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)

    # Reject coerced values for fields that require literal JSON booleans.
    @model_validator(mode='before')
    @classmethod
    def boolean_keywords(cls, value):
        if isinstance(value, dict):
            for key, field in cls.model_fields.items():
                boolean = field.annotation in (Literal[True], Literal[False]) or any(
                    arg in (Literal[True], Literal[False]) for arg in get_args(field.annotation))
                if boolean and key in value and value[key] is not None and type(value[key]) is not bool:
                    raise ValueError('BOOLEAN_KEYWORD_REQUIRED: ' + key)
        return value


# Describe contract margin, multiplier, tax, and fee inputs.
class ContractAccountingInput(StrictModel):
    model: Literal['contract']
    contract_multiplier: Positive = Decimal('100000')
    margin_rate: Annotated[Positive, Field(le=1)]
    pit_rate: Annotated[Nonnegative, Field(le=1)]
    exchange_fee_per_contract: Nonnegative
    clearing_fee_per_contract: Nonnegative
    broker_fee_per_contract: Nonnegative


# Describe normalized accounting and its fee rate.
class NormalizedAccountingInput(StrictModel):
    model: Literal['normalized']
    fee_rate: Nonnegative


AccountingInput = Annotated[ContractAccountingInput | NormalizedAccountingInput, Field(discriminator='model')]


# Describe one source candle and its availability timestamps.
class CandleInput(StrictModel):
    time: StrictInt
    open: Positive
    high: Positive
    low: Positive
    close: Positive
    volume: Nonnegative | None = None
    close_time: StrictInt | None = None
    available_at: StrictInt | None = None

    # Require candle prices to stay within their declared high and low.
    @model_validator(mode='after')
    def prices(self):
        if not self.low <= min(self.open, self.close) <= max(self.open, self.close) <= self.high:
            raise ValueError('INVALID_OHLC')
        return self


# Identify a contract and its expiry timestamps.
class ContractMapInput(StrictModel):
    contract_code: str = Field(min_length=1)
    expiry_date: date
    expiry_unix: StrictInt


# Map one trading date to its contract code.
class ContractDateInput(StrictModel):
    date: date
    contract_code: str = Field(min_length=1)


# Record the source provider and timestamp convention.
class ProvenanceInput(StrictModel):
    provider: str = Field(min_length=1)
    timestamp_convention: Literal['bar_open']
    note: str = Field(min_length=1)


# Describe an ATC observation without requiring a matched price.
class AuctionInput(StrictModel):
    phase: Literal['ATC'] = 'ATC'
    contract_code: str = Field(min_length=1)
    match_time: StrictInt
    available_at: StrictInt
    status: Literal['matched', 'no_match']
    price: Positive | None = None
    source: str = Field(min_length=1)

    # Require auction prices to agree with match status and tick size.
    @model_validator(mode='after')
    def price_status(self):
        if (self.status == 'matched') != (self.price is not None):
            raise ValueError('AUCTION_PRICE_STATUS_MISMATCH')
        if self.price is not None and self.price % Decimal('.1'):
            raise ValueError('AUCTION_PRICE_OFF_TICK')
        return self


# Describe sourced floor and ceiling prices for one contract day.
class PriceLimitInput(StrictModel):
    trading_date: date
    contract_code: str = Field(min_length=1)
    floor_price: Positive
    ceiling_price: Positive
    available_at: StrictInt
    source: str = Field(min_length=1)

    # Validate price bounds, tick size, and source identity.
    @model_validator(mode='after')
    def bounds(self):
        if (self.floor_price > self.ceiling_price or self.floor_price % Decimal('.1')
                or self.ceiling_price % Decimal('.1') or not self.source.strip() or not self.contract_code.strip()):
            raise ValueError('INVALID_PRICE_LIMITS')
        return self


# Describe source candles, session metadata, and contract mappings.
class DataInput(StrictModel):
    resolution: Literal['5', 'D'] = '5'
    bars: list[CandleInput] = Field(min_length=1)
    symbol: str | None = None
    timestamp_unit: Literal['s', 'ms'] = 's'
    timezone: str = 'Asia/Ho_Chi_Minh'
    price_unit: str | None = None
    contract_map: list[ContractMapInput] = Field(default_factory=list)
    contract_dates: list[ContractDateInput] = Field(default_factory=list)
    auctions: list[AuctionInput] = Field(default_factory=list)
    provenance: ProvenanceInput | None = None
    price_limits: list[PriceLimitInput] = Field(default_factory=list)

    # Normalize supported raw source documents before field validation.
    @model_validator(mode='before')
    @classmethod
    def parse_raw_data(cls, value):
        return normalize_raw_source(value)

    # Validate source time ordering, availability, contracts, and auction records.
    @model_validator(mode='after')
    def timestamps(self):
        try:
            zone = ZoneInfo(self.timezone)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError('INVALID_TIMEZONE') from None
        scale = 1000 if self.timestamp_unit == 'ms' else 1
        previous = None
        for bar in self.bars:
            if self.resolution == 'D' and (bar.close_time is None or bar.available_at is None):
                raise ValueError('DAILY_EXPLICIT_TIMES_REQUIRED')
            close = bar.close_time if bar.close_time is not None else bar.time + 300 * scale
            available = bar.available_at if bar.available_at is not None else close
            if not bar.time < close <= available:
                raise ValueError('INVALID_BAR_TIMES')
            if previous and (bar.time <= previous[0] or bar.time < previous[1] or available <= previous[2]):
                raise ValueError('UNORDERED_OR_OVERLAPPING_BARS')
            try:
                for stamp in (bar.time, close, available):
                    datetime.fromtimestamp(stamp / scale, zone)
            except (ValueError, OverflowError, OSError):
                raise ValueError('INVALID_UNIX_TIME') from None
            previous = (bar.time, close, available)
        codes = set()
        dates = [item.date for item in self.contract_dates]
        if dates != sorted(set(dates)):
            raise ValueError('UNORDERED_CONTRACT_DATES')
        previous_match = None
        for auction in self.auctions:
            try:
                matched = datetime.fromtimestamp(auction.match_time / scale, zone)
                available = datetime.fromtimestamp(auction.available_at / scale, zone)
            except (ValueError, OverflowError, OSError):
                raise ValueError('INVALID_AUCTION_TIME') from None
            if (zone.key != 'Asia/Ho_Chi_Minh' or matched.time() != time(14, 45)
                    or available < matched or available.date() != matched.date()
                    or (previous_match is not None and matched <= previous_match)):
                raise ValueError('INVALID_AUCTION_TIME')
            previous_match = matched
        previous_date = None
        for item in self.contract_map:
            try:
                day = datetime.fromtimestamp(item.expiry_unix, zone).date()
            except (ValueError, OverflowError, OSError):
                raise ValueError('INVALID_EXPIRY_UNIX') from None
            if day != item.expiry_date or item.contract_code in codes or (previous_date and day <= previous_date):
                raise ValueError('INVALID_CONTRACT_MAP')
            codes.add(item.contract_code)
            previous_date = day
        return self


# Describe an indicator and its explicitly supplied parameters.
class IndicatorInput(StrictModel):
    type: Literal['SMA', 'EMA', 'BB', 'MACD', 'MFI', 'HIGHEST', 'LOWEST']
    source: str
    period: Period | None = None
    stddev_multiplier: Positive | None = None
    fast_period: Period | None = None
    slow_period: Period | None = None
    signal_period: Period | None = None
    histogram: Literal['line'] | None = None

    # Require exactly the parameters supported by the selected indicator.
    @model_validator(mode='after')
    def parameters(self):
        required = {'type', 'source'} | ({'fast_period', 'slow_period', 'signal_period', 'histogram'}
                    if self.type == 'MACD' else {'period'})
        if self.type == 'BB': required.add('stddev_multiplier')
        if self.model_fields_set != required or any(getattr(self, k) is None for k in required):
            raise ValueError('INDICATOR_PARAMETERS_MISMATCH')
        if self.type == 'MACD' and self.fast_period >= self.slow_period:
            raise ValueError('MACD_FAST_MUST_BE_LESS_THAN_SLOW')
        sources = {'trade_data', 'market_data'}
        if self.type != 'MFI':
            columns = ('open', 'high', 'low', 'close', 'volume') if self.type in ('SMA', 'HIGHEST', 'LOWEST') else ('open', 'high', 'low', 'close')
            sources = {f'{s}.{c}' for s in sources for c in columns}
        if self.source not in sources: raise ValueError('UNSUPPORTED_INDICATOR_SOURCE')
        return self


# Require a time string in canonical HH:MM format.
def check_time(value):
    try:
        if time.fromisoformat(value).strftime('%H:%M') != value: raise ValueError()
    except (TypeError, ValueError):
        raise ValueError('INVALID_HH_MM') from None


# Limit how long an order may remain pending within a session.
class PendingInput(StrictModel):
    max_execution_bars: Annotated[StrictInt, Field(ge=1)]
    cross_lunch: Literal[False]
    cross_cutoff: Literal[False]
    cross_session: Literal[False]


# Describe order intent separately from the selected matching model.
class OrderInput(StrictModel):
    type: Literal['SIMULATED', 'LO', 'ATO', 'ATC', 'MTL', 'MOK', 'MAK']
    limit_price: dict | None = None
    pending: PendingInput | None = None

    # Validate order-specific prices and pending restrictions.
    @model_validator(mode='after')
    def parameters(self):
        if (self.type == 'LO') != (self.limit_price is not None):
            raise ValueError('LIMIT_PRICE_REQUIRED_ONLY_FOR_LO')
        if self.pending is not None and self.type in ('ATO', 'ATC'):
            raise ValueError('AUCTION_LIFETIME_IS_FIXED')
        if self.pending is not None and self.type in ('MAK', 'MOK'):
            raise ValueError('MARKET_ORDER_PENDING_NOT_APPLICABLE')
        return self


# Describe the direction and optional order for an entry action.
class EntryActionInput(StrictModel):
    side: Literal['BUY', 'LONG', 'SHORT']
    order: OrderInput | None = None


# Describe the optional order for a closing action.
class CloseActionInput(StrictModel):
    order: OrderInput | None = None


# Describe entry conditions, directions, orders, and signal windows.
class EntryInput(StrictModel):
    conditions: dict[str, dict] = Field(min_length=1)
    any: list[str] = Field(min_length=1)
    details: dict[str, dict] = Field(default_factory=dict)
    require_flat: StrictBool | None = None
    require_no_pending: StrictBool | None = None
    signal_windows: list[tuple[str, str]] | None = Field(default=None, min_length=1)
    on_conflict: Literal['SIGNAL_CONFLICT'] | None = None
    reentry: Literal['next_bar_close_after_exit'] | None = None
    pending: PendingInput | None = None
    limit_price: dict | None = None
    order: OrderInput | None = None
    actions: dict[str, EntryActionInput] = Field(default_factory=dict)
    priority: list[str] | None = Field(default=None, min_length=1)

    # Validate entry condition coverage, action directions, and signal windows.
    @model_validator(mode='after')
    def directions(self):
        if set(self.any) != set(self.conditions) or len(set(self.any)) != len(self.any):
            raise ValueError('INVALID_ENTRY_DIRECTIONS')
        if self.actions:
            if set(self.actions) != set(self.conditions):
                raise ValueError('ENTRY_ACTIONS_MUST_MATCH_CONDITIONS')
        elif set(self.conditions) - {'BUY', 'LONG', 'SHORT'}:
            raise ValueError('INVALID_ENTRY_DIRECTIONS')
        if self.priority is not None and (
                set(self.priority) != set(self.any) or len(self.priority) != len(self.any)):
            raise ValueError('INVALID_ENTRY_PRIORITY')
        previous_end = None
        if len(self.conditions) > 1 and self.on_conflict is None and self.priority is None:
            raise ValueError('MISSING_CONFLICT_POLICY')
        for start, end in self.signal_windows or ():
            check_time(start); check_time(end)
            if start > end or (previous_end is not None and start <= previous_end):
                raise ValueError('INVALID_SIGNAL_WINDOWS')
            previous_end = end
        return self


# Describe the approved trailing-stop activation and update policy.
class TrailingInput(StrictModel):
    activate_after: Literal['TP1_fill']
    distance_points: Positive
    seed: Literal['TP1_price']
    extrema_from: Literal['bar_after_TP1']
    update_at: Literal['bar_close']
    effective_from: Literal['next_bar']
    combine: Literal['tightest']
    allow_widening: Literal[False]


# Describe target quantity selection based on initial position size.
class SplitQuantity(StrictModel):
    if_initial_quantity_eq: Period
    then: Literal['remaining']
    else_: dict = Field(alias='else')


# Describe a protective stop and its optional trailing configuration.
class StopInput(StrictModel):
    type: Literal['protective_stop']
    distance_points: Positive
    quantity: Literal['remaining']
    trailing: TrailingInput | None = None


# Describe a named target touch and its exit quantity.
class TargetInput(StrictModel):
    type: Literal['target_touch']
    level: Literal['TP1', 'TP2']
    quantity: Literal['remaining'] | SplitQuantity
    requires: Literal['TP1_filled'] | None = None


# Describe intrabar exit conditions and their evaluation priority.
class IntrabarInput(StrictModel):
    conditions: dict[str, Annotated[StopInput | TargetInput, Field(discriminator='type')]] = Field(min_length=1)
    any: list[str] = Field(min_length=1)
    priority: list[str] = Field(min_length=1)


# Describe bar-close exit conditions, priority, and order overrides.
class CloseInput(StrictModel):
    conditions: dict[str, dict] = Field(min_length=1)
    any: list[str] = Field(min_length=1)
    priority: list[str] = Field(min_length=1)
    quantity: Literal['remaining']
    fill_policy: Literal['next_open', 'limit', 'atc'] | None = None
    limit_price: dict | None = None
    order: OrderInput | None = None
    actions: dict[str, CloseActionInput] = Field(default_factory=dict)


# Group target formulas and intrabar or bar-close exit rules.
class ExitInput(StrictModel):
    targets: dict[str, dict[str, dict]] = Field(default_factory=dict)
    intrabar: IntrabarInput | None = None
    bar_close: CloseInput | None = None
    flat_by: str | None = None
    allow_overnight: Literal[False] | None = None


# Describe risk and margin limits for contract sizing.
class ContractSizingInput(StrictModel):
    type: Literal['risk_and_margin']
    risk_fraction: Annotated[Positive, Field(le=1)]
    stop_points: Positive
    margin_buffer: Annotated[Decimal, Field(ge=1, allow_inf_nan=False)]
    max_contracts: Period
    pyramiding: StrictBool


# Describe risk and position limits for normalized sizing.
class NormalizedSizingInput(StrictModel):
    type: Literal['fixed_fractional']
    risk_fraction: Annotated[Positive, Field(le=1)]
    stop_loss_fraction: Annotated[Positive, Field(lt=1)]


SizingInput = Annotated[ContractSizingInput | NormalizedSizingInput, Field(discriminator='type')]


# Describe the expression that stops new entries.
class LimitsInput(StrictModel):
    stop_new_entry: dict


# Describe indicators, entries, exits, sizing, and strategy limits.
class StrategyInput(StrictModel):
    warmup_bars: Period | None = None
    indicators: dict[str, IndicatorInput] = Field(default_factory=dict)
    entry: EntryInput
    exit: ExitInput
    sizing: SizingInput
    daily_limits: LimitsInput | None = None

    # List source and indicator references allowed in strategy expressions.
    def references(self):
        refs = {f'{s}.{c}' for s in ('trade_data', 'market_data') for c in ('open', 'high', 'low', 'close', 'volume')}
        for name, spec in self.indicators.items():
            outputs = {'BB': ('middle', 'upper', 'lower'), 'MACD': ('line', 'signal', 'histogram')}.get(spec.type)
            refs.update(f'{name}.{part}' for part in outputs) if outputs else refs.add(name)
        return refs | STATE_REFS | {f'position.entry_{name}' for name in self.entry.details}

    # Validate expression types, references, action priorities, and order compatibility.
    @model_validator(mode='after')
    def expressions(self):
        reserved = {'trade_data', 'market_data', 'position', 'account', 'day', 'clock'}
        if any(not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*', n) or n in reserved for n in self.indicators):
            raise ValueError('INVALID_INDICATOR_NAME')
        refs = self.references()
        entry_refs = refs - {r for r in STATE_REFS if r.startswith('position.')}
        for node in self.entry.conditions.values():
            validate_expression(node, entry_refs, self.entry.conditions, 'bool')
        for group, available in ((self.entry, entry_refs), (self.exit.bar_close, refs)):
            if group is None:
                continue
            if set(group.actions) - set(group.conditions):
                raise ValueError('UNKNOWN_ACTION_CONDITION')
            for order in [group.order, *(action.order for action in group.actions.values())]:
                if order is not None and order.limit_price is not None:
                    validate_expression(order.limit_price, available, expected='number')
        if self.entry.limit_price is not None:
            validate_expression(self.entry.limit_price, entry_refs, expected='number')
        for name, node in self.entry.details.items():
            if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*', name):
                raise ValueError('INVALID_ENTRY_DETAIL_NAME')
            validate_expression(node, entry_refs, expected='number')
        if self.daily_limits:
            validate_expression(self.daily_limits.stop_new_entry, entry_refs, expected='bool')
        if self.exit.flat_by is not None:
            check_time(self.exit.flat_by)
            if self.entry.signal_windows and self.entry.signal_windows[-1][1] >= self.exit.flat_by:
                raise ValueError('ENTRY_WINDOW_AFTER_FLAT_BY')
        if self.exit.intrabar is None and self.exit.bar_close is None:
            raise ValueError('MISSING_EXIT_ACTIONS')
        directions = {action.side for action in self.entry.actions.values()} if self.entry.actions else set(self.entry.conditions)
        if set(self.exit.targets) - directions:
            raise ValueError('UNKNOWN_TARGET_DIRECTION')
        for levels in self.exit.targets.values():
            if set(levels) - {'TP1', 'TP2'}: raise ValueError('UNKNOWN_TARGET_LEVEL')
            for node in levels.values():
                validate_expression(node, {'position.entry_price'}, expected='number')
        for group in (self.exit.intrabar, self.exit.bar_close):
            if group is None: continue
            if (set(group.any) != set(group.conditions) or set(group.priority) != set(group.any)
                    or len(group.any) != len(set(group.any)) or len(group.priority) != len(set(group.priority))):
                raise ValueError('INVALID_EXIT_PRIORITY')
        if self.exit.bar_close:
            if self.exit.bar_close.fill_policy is not None and (
                    (self.exit.bar_close.fill_policy == 'limit') != (self.exit.bar_close.limit_price is not None)):
                raise ValueError('CLOSE_LIMIT_PRICE_REQUIRED_ONLY_FOR_LO')
            if self.exit.bar_close.limit_price is not None:
                validate_expression(self.exit.bar_close.limit_price, refs, expected='number')
            for node in self.exit.bar_close.conditions.values():
                validate_expression(node, refs, self.exit.bar_close.conditions, 'bool')
        if self.exit.intrabar:
            actions = list(self.exit.intrabar.conditions.values())
            ordered = [self.exit.intrabar.conditions[name] for name in self.exit.intrabar.priority]
            if any(isinstance(action, StopInput) for action in ordered[1:]):
                raise ValueError('STOP_MUST_PRECEDE_TARGETS')
            ordered_levels = [action.level for action in ordered if isinstance(action, TargetInput)]
            if ordered_levels != sorted(ordered_levels):
                raise ValueError('TP1_MUST_PRECEDE_TP2')
            levels = [a.level for a in actions if isinstance(a, TargetInput)]
            if len(levels) != len(set(levels)) or sum(isinstance(a, StopInput) for a in actions) > 1:
                raise ValueError('DUPLICATE_EXIT_ACTION')
            for action in actions:
                if isinstance(action, TargetInput):
                    if any(action.level not in self.exit.targets.get(side, {}) for side in directions):
                        raise ValueError('MISSING_TARGET_LEVEL')
                    if action.requires and (action.level == 'TP1' or 'TP1' not in levels):
                        raise ValueError('INVALID_TARGET_DEPENDENCY')
                    if isinstance(action.quantity, SplitQuantity):
                        validate_expression(action.quantity.else_, {'position.initial_quantity'}, expected='number')
                else:
                    if action.distance_points != self.sizing.stop_points:
                        raise ValueError('SIZING_STOP_MISMATCH')
                    if action.trailing and 'TP1' not in levels:
                        raise ValueError('TRAILING_REQUIRES_TP1')
        return self


# Describe matching-model selection and execution simulation parameters.
class ExecutionInput(StrictModel):
    entry_fill_policy: Literal['next_open', 'limit', 'ato'] | None = None
    slippage_rate: Annotated[Nonnegative, Field(lt=1)]
    matching_model: Literal['next_open', 'hnx_sessions_v1'] | None = None
    auction_match_quantity: AuctionQuantity | None = None
    continuous_match_quantity: AuctionQuantity | None = None


# Describe the requested reporting interval.
class ReportInput(StrictModel):
    start_date: date
    end_date: date

    # Require the report start date to precede or equal its end date.
    @model_validator(mode='after')
    def date_order(self):
        if self.start_date > self.end_date:
            raise ValueError('INVALID_REPORT_RANGE')
        return self


# Describe a complete inline backtest request and its required data sources.
class InlineRunRequest(StrictModel):
    auto_fetch_data: StrictBool = Field(
        False, description='Tự lấy VN30F1M và VNINDEX 5 phút trong sáu tháng gần nhất; ưu tiên và bỏ qua dữ liệu nhập tay.')
    trade_data: DataInput | None = None
    market_data: DataInput | None = None
    strategy: StrategyInput
    execution: ExecutionInput
    accounting: AccountingInput
    initial_cash: Positive
    report: ReportInput | None = None

    # Discard manual sources when automatic fetching is explicitly enabled.
    @model_validator(mode='before')
    @classmethod
    def prefer_auto_data(cls, value):
        if isinstance(value, dict) and value.get('auto_fetch_data') is True:
            return {key: item for key, item in value.items() if key not in ('trade_data', 'market_data')}
        return value

    # Require the data sources referenced by the selected strategy and execution.
    @model_validator(mode='after')
    def requirements(self):
        if not self.auto_fetch_data and self.trade_data is None:
            raise ValueError('MISSING_REQUIRED_DATA: trade_data')
        needed = set()
        volumes = set()
        for indicator in self.strategy.indicators.values():
            source = indicator.source.split('.')[0]
            needed.add(source)
            if indicator.type == 'MFI' or indicator.source.endswith('.volume'): volumes.add(source)
        # Collect source requirements from nested strategy references.
        def visit(value):
            if isinstance(value, dict):
                ref = value.get('ref', '')
                if ref.startswith(('market_data.', 'trade_data.')):
                    needed.add(ref.split('.')[0])
                    if ref.endswith('.volume'): volumes.add(ref.split('.')[0])
                for child in value.values(): visit(child)
            elif isinstance(value, list):
                for child in value: visit(child)
        visit(self.strategy.model_dump(by_alias=True))
        for name in needed:
            if self.auto_fetch_data: continue
            source = getattr(self, name)
            if source is None: raise ValueError('MISSING_REQUIRED_DATA: ' + name)
            if name in volumes and any(b.volume is None for b in source.bars):
                raise ValueError('MISSING_REQUIRED_VOLUME: ' + name)
        entry_actions, close_actions = strategy_orders(self.model_dump(by_alias=True, exclude_none=True))
        sides = {action['side'] for action in entry_actions.values()}
        entry_types = {action['order']['type'] for action in entry_actions.values()}
        close_types = {action['order']['type'] for action in close_actions.values()}
        market_types = (entry_types | close_types) & MARKET_TYPES
        if entry_types - {'SIMULATED', 'LO', 'ATO', *MARKET_TYPES} or close_types - {'SIMULATED', 'LO', 'ATC', *MARKET_TYPES}:
            raise ValueError('ORDER_UNSUPPORTED_FOR_ACTION')
        session = self.execution.matching_model == 'hnx_sessions_v1'
        if market_types:
            if not session or self.accounting.model != 'contract':
                raise ValueError('ORDER_UNSUPPORTED_BY_MATCHING_MODEL')
            if self.execution.continuous_match_quantity is None:
                raise ValueError('MARKET_ORDER_REQUIRES_MATCH_QUANTITY')
            if self.auto_fetch_data or not self.trade_data.price_limits:
                raise ValueError('MISSING_PRICE_LIMITS')
            old_pending = self.strategy.entry.pending
            if old_pending is not None and (entry_types | close_types) & {'MAK', 'MOK'} and old_pending.max_execution_bars != 1:
                raise ValueError('MARKET_ORDER_PENDING_NOT_APPLICABLE')
        if self.execution.continuous_match_quantity is not None and not session:
            raise ValueError('SESSION_MATCHING_REQUIRED')
        multi = getattr(self.strategy.sizing, 'pyramiding', False)
        entry = self.strategy.entry
        if multi:
            if not session or self.accounting.model != 'contract' or entry_types - {'LO', 'ATO', *MARKET_TYPES}:
                raise ValueError('MULTI_ENTRY_REQUIRES_SESSION_LO_OR_ATO')
            if not entry.priority:
                raise ValueError('MULTI_ENTRY_REQUIRES_PRIORITY')
            if entry.on_conflict is not None or entry.require_flat is True or entry.require_no_pending is True:
                raise ValueError('MULTI_ENTRY_CONFLICTING_SINGLE_POSITION_FLAGS')
        elif entry.require_flat is False or entry.require_no_pending is False:
            raise ValueError('MULTI_ENTRY_FLAGS_REQUIRE_PYRAMIDING')
        close = self.strategy.exit.bar_close
        if session:
            if (self.accounting.model != 'contract' or self.execution.slippage_rate != 0
                    or (not self.auto_fetch_data and self.trade_data.resolution != '5')):
                raise ValueError('SESSION_MATCHING_REQUIRES_CONTRACT_5M_ZERO_SLIPPAGE')
            if not self.auto_fetch_data:
                if self.trade_data.timezone != 'Asia/Ho_Chi_Minh':
                    raise ValueError('CONTRACT_TIMEZONE_MISMATCH')
                if not self.trade_data.contract_dates or self.trade_data.provenance is None:
                    raise ValueError('SESSION_MATCHING_REQUIRES_CONTRACT_DATES_AND_PROVENANCE')
            if 'ATC' in close_types and self.strategy.exit.flat_by and self.strategy.exit.flat_by < '14:45':
                raise ValueError('ATC_AFTER_FLAT_DEADLINE')
            if (self.execution.auction_match_quantity is not None
                    and 'ATO' not in entry_types and 'ATC' not in close_types):
                raise ValueError('AUCTION_MATCH_QUANTITY_REQUIRES_AUCTION_ORDER')
        elif (entry_types | close_types != {'SIMULATED'}
              or any(action['order'].get('pending', {}).get('max_execution_bars', 1) != 1
                     for action in (*entry_actions.values(), *close_actions.values()))
              or self.execution.auction_match_quantity is not None
              or (self.trade_data and (self.trade_data.auctions or self.trade_data.contract_dates))):
            raise ValueError('SESSION_MATCHING_REQUIRED')
        if self.market_data and self.market_data.auctions:
            raise ValueError('AUCTIONS_REQUIRE_TRADE_DATA')
        if self.market_data and self.market_data.price_limits:
            raise ValueError('PRICE_LIMITS_REQUIRE_TRADE_DATA')
        if self.accounting.model == 'normalized':
            if sides != {'BUY'} or self.strategy.sizing.type != 'fixed_fractional' or self.strategy.exit.intrabar:
                raise ValueError('NORMALIZED_REQUIRES_BUY_FIXED_FRACTIONAL_AND_BAR_CLOSE_EXIT')
        elif (not sides <= {'LONG', 'SHORT'} or self.strategy.sizing.type != 'risk_and_margin'):
            raise ValueError('CONTRACT_REQUIRES_LONG_SHORT_AND_RISK_AND_MARGIN')
        return self
