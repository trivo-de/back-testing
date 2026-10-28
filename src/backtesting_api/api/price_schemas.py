"""Validate the approved price-only request without accepting market data."""
from datetime import date, datetime
from typing import Annotated, Any, Literal
from zoneinfo import ZoneInfo
import re
from pydantic import Field, StrictInt, model_validator
from .inline_schemas import StrictModel, IndicatorInput, Positive, check_time
from ..domain.expressions import STATE_REFS, validate_expression
from ..domain.strategy_terms import ALIASES, expand_condition, references, required_history
from ..domain.portfolio import decimal


class PriceOrder(StrictModel):
    """Choose immediate Close execution or a fixed three-bar intraday limit."""
    type: Literal['IMMEDIATE', 'LO'] = 'IMMEDIATE'
    limit_price: Any = None

    @model_validator(mode='after')
    def limit(self):
        """Require a limit only for LO and forbid silently ignored parameters."""
        if (self.type == 'LO') != (self.limit_price is not None):
            raise ValueError('LIMIT_PRICE_REQUIRED_ONLY_FOR_LO')
        return self


class PriceTarget(StrictModel):
    """Describe one ordered target with an explicit quantity and one price basis."""
    pct: Positive | None = None
    price: Any = None
    quantity: Any

    @model_validator(mode='after')
    def basis(self):
        """Require exactly one target basis and reject invalid literal quantities."""
        if (self.pct is None) == (self.price is None):
            raise ValueError('INVALID_TARGET_BASIS')
        if self.quantity != 'remaining' and not isinstance(self.quantity, dict) and (
                type(self.quantity) is not int or self.quantity < 1):
            raise ValueError('INVALID_TARGET_QUANTITY')
        return self


class PriceRisk(StrictModel):
    """Describe protection percentages; execution is always checked at Close."""
    sl: Positive | None = None
    tp: Positive | None = None
    trailing: Positive | None = None
    stop_price: Any = None
    targets: list[PriceTarget] | None = Field(None, min_length=1)
    trailing_after_tp1: Positive | None = None

    @model_validator(mode='after')
    def combinations(self):
        """Reject ambiguous pairs before the engine receives risk configuration."""
        if ((self.sl is not None and self.stop_price is not None)
                or (self.tp is not None and self.targets is not None)
                or (self.trailing is not None and self.trailing_after_tp1 is not None)):
            raise ValueError('INVALID_RISK')
        if self.trailing_after_tp1 is not None and not self.targets:
            raise ValueError('TRAILING_REQUIRES_TP1')
        if self.targets and any(target.quantity == 'remaining' for target in self.targets[:-1]):
            raise ValueError('REMAINING_TARGET_MUST_BE_LAST')
        return self


class PriceRunRequest(StrictModel):
    """Accept only strategy intent and the optional report-date pair."""
    symbol: Literal['VN30F1M']
    from_: str | None = Field(None, alias='from')
    to: str | None = None
    quantity: Annotated[StrictInt, Field(gt=0)] = 1
    entry: dict[str, Any]
    exit: dict[str, Any] = Field(default_factory=dict)
    risk: PriceRisk | None = None
    order: PriceOrder = Field(default_factory=PriceOrder)
    indicators: dict[str, IndicatorInput] = Field(default_factory=dict)
    warmup_bars: Annotated[StrictInt, Field(ge=0)] = 0
    daily_limits: dict[str, Any] | None = None

    @model_validator(mode='before')
    @classmethod
    def no_market_data(cls, value):
        """Report legacy and data fields explicitly rather than ignoring them."""
        legacy = {'accounting', 'initial_cash', 'execution', 'strategy', 'report', 'auto_fetch_data',
                  'trade_data', 'market_data', 'bars', 'raw', 'file', 'contract_map', 'price_limits',
                  'open', 'high', 'low', 'close', 'volume', 'auctions'}
        if isinstance(value, dict) and legacy & value.keys():
            raise ValueError('LEGACY_OR_DATA_FIELD_NOT_ALLOWED: ' + ','.join(sorted(legacy & value.keys())))
        if isinstance(value, dict) and 'symbol' in value and value['symbol'] != 'VN30F1M':
            raise ValueError('SYMBOL_UNSUPPORTED')
        return value

    @model_validator(mode='after')
    def rules(self):
        """Check dates and all expressions using the same compilation as execution."""
        if (self.from_ is None) != (self.to is None):
            raise ValueError('INVALID_REPORT_RANGE')
        if self.from_ is not None:
            try:
                start, end = date.fromisoformat(self.from_), date.fromisoformat(self.to)
                if (start.isoformat() != self.from_ or end.isoformat() != self.to or start > end
                        or end > datetime.now(ZoneInfo('Asia/Ho_Chi_Minh')).date()):
                    raise ValueError()
            except ValueError:
                raise ValueError('INVALID_REPORT_RANGE') from None
        self.compiled()
        return self

    def compiled(self):
        """Return normalized conditions and explicit defaults, never invented sizing."""
        if (not self.entry.keys() & {'long', 'short'} or self.entry.keys() - {'long', 'short', 'signal_windows'}
                or self.exit.keys() - {'long', 'short', 'flat_by', 'allow_overnight'}):
            raise ValueError('INVALID_ACTIONS')
        if self.exit.get('allow_overnight', False) is not False:
            raise ValueError('OVERNIGHT_NOT_ALLOWED')
        if self.exit.get('flat_by') is not None:
            if not isinstance(self.exit['flat_by'], str):
                raise ValueError('INVALID_TIME')
            check_time(self.exit['flat_by'])
        windows = self.entry.get('signal_windows', [])
        if not isinstance(windows, list):
            raise ValueError('INVALID_SIGNAL_WINDOWS')
        previous = None
        for window in windows:
            if not isinstance(window, list) or len(window) != 2:
                raise ValueError('INVALID_SIGNAL_WINDOWS')
            for stamp in window:
                if not isinstance(stamp, str):
                    raise ValueError('INVALID_SIGNAL_WINDOWS')
                check_time(stamp)
            if window[0] > window[1] or (previous is not None and window[0] <= previous):
                raise ValueError('INVALID_SIGNAL_WINDOWS')
            previous = window[1]
        if windows and self.exit.get('flat_by') and windows[-1][1] >= self.exit['flat_by']:
            raise ValueError('ENTRY_WINDOW_AFTER_FLAT_BY')
        indicators = {name: spec.model_dump(mode='json', exclude_none=True) for name, spec in self.indicators.items()}
        if any(not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*', name) or name in {*ALIASES, 'price', 'market',
                'trade_data', 'market_data', 'position', 'account', 'day', 'clock'} for name in indicators):
            raise ValueError('INVALID_INDICATOR_NAME')
        actions = {'entry': {}, 'exit': {}}
        for group, supplied in (('entry', self.entry), ('exit', self.exit)):
            for side in ('long', 'short'):
                if side not in supplied:
                    continue
                raw = supplied[side]
                action = raw if isinstance(raw, dict) and 'condition' in raw else {'condition': raw}
                if action.keys() - ({'condition', 'order', 'quantity'} if group == 'exit' else {'condition', 'order'}):
                    raise ValueError('INVALID_ACTION')
                condition = expand_condition(action['condition'], indicators)
                order = PriceOrder.model_validate(action.get('order', self.order.model_dump())).model_dump(exclude_none=True)
                if 'limit_price' in order:
                    order['limit_price'] = expand_condition(order['limit_price'], indicators)
                if order['type'] == 'LO':
                    order.update(max_execution_bars=3, time_in_force='DAY')
                quantity = action.get('quantity', 'remaining')
                if group == 'exit' and quantity != 'remaining' and (type(quantity) is not int or quantity < 1):
                    raise ValueError('INVALID_QUANTITY')
                actions[group][side.upper()] = {'condition': condition, 'order': order, 'quantity': quantity}
        refs = references(indicators) | (STATE_REFS - {'account.equity', 'account.required_margin', 'day.start_equity'})
        for group, rows in actions.items():
            available = refs - {name for name in refs if name.startswith('position.')} if group == 'entry' else refs
            for action in rows.values():
                validate_expression(action['condition'], available, expected='bool')
                if 'limit_price' in action['order']:
                    validate_expression(action['order']['limit_price'], available, expected='number')
        for side in actions['entry']:
            if side not in actions['exit'] and (self.risk is None or not self.risk.model_dump(exclude_none=True)):
                raise ValueError('EXIT_REQUIRED')
        daily_limits = self.daily_limits
        if daily_limits is not None:
            if set(daily_limits) != {'stop_new_entry'}:
                raise ValueError('INVALID_DAILY_LIMITS')
            daily_limits = {'stop_new_entry': expand_condition(daily_limits['stop_new_entry'], indicators)}
            refs |= references(indicators)
            validate_expression(daily_limits['stop_new_entry'], refs - {r for r in refs if r.startswith('position.')}, expected='bool')
        risk = self.risk.model_dump(mode='json', exclude_none=True) if self.risk else {}
        entry_refs = refs - {name for name in refs if name.startswith('position.')}
        if 'stop_price' in risk:
            risk['stop_price'] = expand_condition(risk['stop_price'], indicators)
        target_quantity = 0
        previous_pct = None
        for target in risk.get('targets', []):
            if 'price' in target:
                target['price'] = expand_condition(target['price'], indicators)
            else:
                pct = decimal(target['pct'])
                if previous_pct is not None and pct < previous_pct:
                    raise ValueError('TARGETS_OUT_OF_ORDER')
                previous_pct = pct
            quantity = target['quantity']
            if isinstance(quantity, dict):
                validate_expression(quantity, {'position.initial_quantity'}, expected='number')
                from ..domain.expressions import evaluate_expression
                quantity = evaluate_expression(quantity, {'position.initial_quantity': self.quantity})
                if quantity != int(quantity) or quantity < 1:
                    raise ValueError('INVALID_TARGET_QUANTITY')
            if quantity != 'remaining':
                target_quantity += int(quantity)
        if target_quantity > self.quantity:
            raise ValueError('INVALID_TARGET_QUANTITY')
        refs |= references(indicators)
        entry_refs |= references(indicators)
        for node in [risk['stop_price']] if 'stop_price' in risk else []:
            validate_expression(node, entry_refs, expected='number')
        for target in risk.get('targets', []):
            if 'price' in target:
                validate_expression(target['price'], entry_refs, expected='number')
        default_order = self.order.model_dump(exclude_none=True)
        if 'limit_price' in default_order:
            default_order['limit_price'] = expand_condition(default_order['limit_price'], indicators)
            refs |= references(indicators)
            validate_expression(default_order['limit_price'], refs, expected='number')
            default_order.update(max_execution_bars=3, time_in_force='DAY')
        spec = {**actions, 'indicators': indicators, 'quantity': self.quantity,
                'warmup_bars': self.warmup_bars, 'signal_windows': windows,
                'flat_by': self.exit.get('flat_by'), 'daily_limits': daily_limits,
                'risk': risk, 'order': default_order,
                'allow_overnight': False, 'session_end_action': 'close_at_close',
                'default_profile_version': 'price-only-v2'}
        spec['required_history'] = required_history(spec)
        return spec
