from datetime import date, datetime, time
from decimal import Decimal
from typing import Annotated, Literal, get_args
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import re
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, model_validator
from ..domain.expressions import STATE_REFS, validate_expression
from ..infrastructure.market_snapshot import normalize_raw_source

Positive = Annotated[Decimal, Field(gt=0, allow_inf_nan=False)]
Nonnegative = Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]
Period = Annotated[StrictInt, Field(gt=0)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)

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


class ContractAccountingInput(StrictModel):
    model: Literal['contract']
    contract_multiplier: Positive = Decimal('100000')
    margin_rate: Annotated[Positive, Field(le=1)]
    pit_rate: Annotated[Nonnegative, Field(le=1)]
    exchange_fee_per_contract: Nonnegative
    clearing_fee_per_contract: Nonnegative
    broker_fee_per_contract: Nonnegative


class NormalizedAccountingInput(StrictModel):
    model: Literal['normalized']
    fee_rate: Nonnegative


AccountingInput = Annotated[ContractAccountingInput | NormalizedAccountingInput, Field(discriminator='model')]


class CandleInput(StrictModel):
    time: StrictInt
    open: Positive
    high: Positive
    low: Positive
    close: Positive
    volume: Nonnegative | None = None
    close_time: StrictInt | None = None
    available_at: StrictInt | None = None

    @model_validator(mode='after')
    def prices(self):
        if not self.low <= min(self.open, self.close) <= max(self.open, self.close) <= self.high:
            raise ValueError('INVALID_OHLC')
        return self


class ContractMapInput(StrictModel):
    contract_code: str = Field(min_length=1)
    expiry_date: date
    expiry_unix: StrictInt


class DataInput(StrictModel):
    resolution: Literal['5', 'D'] = '5'
    bars: list[CandleInput] = Field(min_length=1)
    symbol: str | None = None
    timestamp_unit: Literal['s', 'ms'] = 's'
    timezone: str = 'Asia/Ho_Chi_Minh'
    price_unit: str | None = None
    contract_map: list[ContractMapInput] = Field(default_factory=list)

    @model_validator(mode='before')
    @classmethod
    def parse_raw_data(cls, value):
        return normalize_raw_source(value)

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


class IndicatorInput(StrictModel):
    type: Literal['SMA', 'EMA', 'BB', 'MACD', 'MFI', 'HIGHEST', 'LOWEST']
    source: str
    period: Period | None = None
    stddev_multiplier: Positive | None = None
    fast_period: Period | None = None
    slow_period: Period | None = None
    signal_period: Period | None = None
    histogram: Literal['line'] | None = None

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


def check_time(value):
    try:
        if time.fromisoformat(value).strftime('%H:%M') != value: raise ValueError()
    except (TypeError, ValueError):
        raise ValueError('INVALID_HH_MM') from None


class PendingInput(StrictModel):
    max_execution_bars: Annotated[StrictInt, Field(ge=1, le=1)]
    cross_lunch: Literal[False]
    cross_cutoff: Literal[False]
    cross_session: Literal[False]


class EntryInput(StrictModel):
    conditions: dict[str, dict] = Field(min_length=1)
    any: list[str] = Field(min_length=1)
    details: dict[str, dict] = Field(default_factory=dict)
    require_flat: Literal[True] | None = None
    require_no_pending: Literal[True] | None = None
    signal_windows: list[tuple[str, str]] | None = Field(default=None, min_length=1)
    on_conflict: Literal['SIGNAL_CONFLICT'] | None = None
    reentry: Literal['next_bar_close_after_exit'] | None = None
    pending: PendingInput | None = None

    @model_validator(mode='after')
    def directions(self):
        if set(self.conditions) - {'BUY', 'LONG', 'SHORT'} or set(self.any) != set(self.conditions) or len(set(self.any)) != len(self.any):
            raise ValueError('INVALID_ENTRY_DIRECTIONS')
        previous_end = None
        if len(self.conditions) > 1 and self.on_conflict is None:
            raise ValueError('MISSING_CONFLICT_POLICY')
        for start, end in self.signal_windows or ():
            check_time(start); check_time(end)
            if start > end or (previous_end is not None and start <= previous_end):
                raise ValueError('INVALID_SIGNAL_WINDOWS')
            previous_end = end
        return self


class TrailingInput(StrictModel):
    activate_after: Literal['TP1_fill']
    distance_points: Positive
    seed: Literal['TP1_price']
    extrema_from: Literal['bar_after_TP1']
    update_at: Literal['bar_close']
    effective_from: Literal['next_bar']
    combine: Literal['tightest']
    allow_widening: Literal[False]


class SplitQuantity(StrictModel):
    if_initial_quantity_eq: Period
    then: Literal['remaining']
    else_: dict = Field(alias='else')


class StopInput(StrictModel):
    type: Literal['protective_stop']
    distance_points: Positive
    quantity: Literal['remaining']
    trailing: TrailingInput | None = None


class TargetInput(StrictModel):
    type: Literal['target_touch']
    level: Literal['TP1', 'TP2']
    quantity: Literal['remaining'] | SplitQuantity
    requires: Literal['TP1_filled'] | None = None


class IntrabarInput(StrictModel):
    conditions: dict[str, Annotated[StopInput | TargetInput, Field(discriminator='type')]] = Field(min_length=1)
    any: list[str] = Field(min_length=1)
    priority: list[str] = Field(min_length=1)


class CloseInput(StrictModel):
    conditions: dict[str, dict] = Field(min_length=1)
    any: list[str] = Field(min_length=1)
    priority: list[str] = Field(min_length=1)
    quantity: Literal['remaining']
    fill_policy: Literal['next_open']


class ExitInput(StrictModel):
    targets: dict[str, dict[str, dict]] = Field(default_factory=dict)
    intrabar: IntrabarInput | None = None
    bar_close: CloseInput | None = None
    flat_by: str | None = None
    allow_overnight: Literal[False] | None = None


class ContractSizingInput(StrictModel):
    type: Literal['risk_and_margin']
    risk_fraction: Annotated[Positive, Field(le=1)]
    stop_points: Positive
    margin_buffer: Annotated[Decimal, Field(ge=1, allow_inf_nan=False)]
    max_contracts: Period
    pyramiding: Literal[False]


class NormalizedSizingInput(StrictModel):
    type: Literal['fixed_fractional']
    risk_fraction: Annotated[Positive, Field(le=1)]
    stop_loss_fraction: Annotated[Positive, Field(lt=1)]


SizingInput = Annotated[ContractSizingInput | NormalizedSizingInput, Field(discriminator='type')]


class LimitsInput(StrictModel):
    stop_new_entry: dict


class StrategyInput(StrictModel):
    warmup_bars: Period | None = None
    indicators: dict[str, IndicatorInput] = Field(default_factory=dict)
    entry: EntryInput
    exit: ExitInput
    sizing: SizingInput
    daily_limits: LimitsInput | None = None

    def references(self):
        refs = {f'{s}.{c}' for s in ('trade_data', 'market_data') for c in ('open', 'high', 'low', 'close', 'volume')}
        for name, spec in self.indicators.items():
            outputs = {'BB': ('middle', 'upper', 'lower'), 'MACD': ('line', 'signal', 'histogram')}.get(spec.type)
            refs.update(f'{name}.{part}' for part in outputs) if outputs else refs.add(name)
        return refs | STATE_REFS | {f'position.entry_{name}' for name in self.entry.details}

    @model_validator(mode='after')
    def expressions(self):
        reserved = {'trade_data', 'market_data', 'position', 'account', 'day', 'clock'}
        if any(not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*', n) or n in reserved for n in self.indicators):
            raise ValueError('INVALID_INDICATOR_NAME')
        refs = self.references()
        entry_refs = refs - {r for r in STATE_REFS if r.startswith('position.')}
        for node in self.entry.conditions.values():
            validate_expression(node, entry_refs, self.entry.conditions, 'bool')
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
        if set(self.exit.targets) - set(self.entry.conditions):
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
                    if any(action.level not in self.exit.targets.get(side, {}) for side in self.entry.conditions):
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


class ExecutionInput(StrictModel):
    entry_fill_policy: Literal['next_open']
    slippage_rate: Annotated[Nonnegative, Field(lt=1)]


class ReportInput(StrictModel):
    start_date: date
    end_date: date


class InlineRunRequest(StrictModel):
    trade_data: DataInput | None = None
    market_data: DataInput | None = None
    strategy: StrategyInput
    execution: ExecutionInput
    accounting: AccountingInput
    initial_cash: Positive
    report: ReportInput | None = None

    @model_validator(mode='after')
    def requirements(self):
        if self.trade_data is None:
            raise ValueError('MISSING_REQUIRED_DATA: trade_data')
        needed = set()
        volumes = set()
        for indicator in self.strategy.indicators.values():
            source = indicator.source.split('.')[0]
            needed.add(source)
            if indicator.type == 'MFI' or indicator.source.endswith('.volume'): volumes.add(source)
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
            source = getattr(self, name)
            if source is None: raise ValueError('MISSING_REQUIRED_DATA: ' + name)
            if name in volumes and any(b.volume is None for b in source.bars):
                raise ValueError('MISSING_REQUIRED_VOLUME: ' + name)
        if self.report and self.trade_data is not None:
            r = self.report
            scale = 1000 if self.trade_data.timestamp_unit == 'ms' else 1
            zone = ZoneInfo(self.trade_data.timezone)
            first, last = [datetime.fromtimestamp(b.time / scale, zone).date()
                           for b in (self.trade_data.bars[0], self.trade_data.bars[-1])]
            if not first <= r.start_date <= r.end_date <= last:
                raise ValueError('INVALID_REPORT_RANGE')
        sides = set(self.strategy.entry.conditions)
        if self.accounting.model == 'normalized':
            if sides != {'BUY'} or self.strategy.sizing.type != 'fixed_fractional' or self.strategy.exit.intrabar:
                raise ValueError('NORMALIZED_REQUIRES_BUY_FIXED_FRACTIONAL_AND_BAR_CLOSE_EXIT')
        elif (not sides <= {'LONG', 'SHORT'} or self.strategy.sizing.type != 'risk_and_margin'):
            raise ValueError('CONTRACT_REQUIRES_LONG_SHORT_AND_RISK_AND_MARGIN')
        return self
