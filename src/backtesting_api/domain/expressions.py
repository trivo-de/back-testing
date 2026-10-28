"""Operations for building backtest strategies."""
from datetime import time
from decimal import Decimal, DecimalException, ROUND_FLOOR
import operator
from .portfolio import decimal

NUMERIC = {'add': operator.add, 'sub': operator.sub, 'mul': operator.mul,
           'div': operator.truediv, 'min': min, 'max': max}
COMPARE = {'gt': operator.gt, 'gte': operator.ge, 'lt': operator.lt, 'lte': operator.le}
CROSS = {'cross_up', 'cross_down'}
MAX_EXPRESSION_DEPTH = 32
MAX_EXPRESSION_NODES = 4096
STATE_REFS = {'position.entry_price', 'position.initial_quantity', 'position.held_bars',
              'account.equity', 'account.required_margin', 'day.net_pnl',
              'day.start_equity', 'day.entry_fill_count', 'clock.local_time'}


class MissingValue(ValueError):
    """Raised when a value is missing for a reference in an expression."""
    # Retain the missing reference name in the evaluation error.
    def __init__(self, name):
        super().__init__(f'Missing value for reference: {name}')
        self.name = name


# Validate expression structure, types, reference shifts, and recursion limits.
def validate_expression(node, references, conditions=None, expected=None, *, depth=0, trail=(), _budget=None):
    _budget = [MAX_EXPRESSION_NODES] if _budget is None else _budget
    _budget[0] -= 1
    if _budget[0] < 0:
        raise ValueError('EXPRESSION_TOO_LARGE')
    if depth > MAX_EXPRESSION_DEPTH:
        raise ValueError('EXPRESSION_TOO_DEEP')
    conditions = conditions or {}
    if isinstance(node, str):
        if node in conditions:
            if node in trail:
                raise ValueError('CYCLIC_CONDITION: ' + node)
            kind = validate_expression(conditions[node], references, conditions, 'bool',
                                       depth=depth + 1, trail=trail + (node,), _budget=_budget)
        else:
            try:
                parsed = time.fromisoformat(node)
                if parsed.strftime('%H:%M') != node:
                    raise ValueError()
            except ValueError:
                raise ValueError('UNKNOWN_CONDITION_OR_TIME: ' + node) from None
            kind = 'time'
    elif type(node) in (int, float, Decimal):
        decimal(node)
        kind = 'number'
    elif isinstance(node, dict) and 'ref' in node:
        if set(node) - {'ref', 'shift'} or not isinstance(node['ref'], str) or node['ref'] not in references:
            raise ValueError('UNKNOWN_REF')
        shift = node.get('shift', 0)
        state_ref = node['ref'] in STATE_REFS or node['ref'].startswith('position.entry_')
        if type(shift) is not int or shift < 0 or ('shift' in node and state_ref):
            raise ValueError('INVALID_SHIFT')
        kind = 'time' if node['ref'] == 'clock.local_time' else 'number'
    elif isinstance(node, dict) and len(node) == 1:
        op, args = next(iter(node.items()))
        if op not in {*NUMERIC, *COMPARE, *CROSS, 'floor', 'all', 'any'} or not isinstance(args, list):
            raise ValueError('UNSUPPORTED_OPERATOR')
        count = 1 if op == 'floor' else 2
        if not args or (op not in ('all', 'any') and len(args) != count):
            raise ValueError('INVALID_OPERAND_COUNT')
        kinds = [validate_expression(arg, references, conditions, depth=depth + 1, trail=trail, _budget=_budget) for arg in args]
        if op in ('all', 'any'):
            if any(k != 'bool' for k in kinds):
                raise ValueError('BOOLEAN_REQUIRED')
            kind = 'bool'
        elif op in COMPARE or op in CROSS:
            if kinds[0] != kinds[1] or kinds[0] not in ('number', 'time'):
                raise ValueError('COMPARISON_TYPE_MISMATCH')
            kind = 'bool'
            if op in CROSS:
                # State has no source series and cannot supply an earlier sample.
                def has_state(value):
                    """Reject state references inside either crossing operand."""
                    if isinstance(value, dict):
                        return (value.get('ref') in STATE_REFS or
                                str(value.get('ref', '')).startswith('position.') or
                                any(has_state(child) for child in value.values()))
                    return isinstance(value, list) and any(has_state(child) for child in value)
                if kinds != ['number', 'number'] or has_state(args):
                    raise ValueError('CROSS_REQUIRES_SERIES')
        else:
            if any(k != 'number' for k in kinds):
                raise ValueError('NUMBER_REQUIRED')
            if op == 'div' and type(args[1]) in (int, float, Decimal) and decimal(args[1]) == 0:
                raise ValueError('DIVISION_BY_ZERO')
            kind = 'number'
    else:
        raise ValueError('INVALID_EXPRESSION')
    if expected is not None and kind != expected:
        raise ValueError('EXPRESSION_TYPE_MISMATCH')
    return kind


def evaluate_expression(node, values, conditions=None):
    """Read only available values/series; shift looks back within the referenced series."""
    conditions = conditions or {}
    validate_expression(node, set(values), conditions)

    # Evaluate one expression node using the supplied available values.
    def evaluate(item, offset=0):
        if isinstance(item, str):
            return evaluate(conditions[item], offset) if item in conditions else time.fromisoformat(item)
        if type(item) in (int, float, Decimal):
            return decimal(item)
        if 'ref' in item:
            name = item['ref']
            value = values[name]
            if isinstance(value, (list, tuple)):
                shift = item.get('shift', 0) + offset
                if len(value) <= shift:
                    raise MissingValue(name)
                value = value[-1-shift]
            elif item.get('shift', 0) or offset:
                raise MissingValue(name)
            if value is None:
                raise MissingValue(name)
            if name == 'clock.local_time':
                return time.fromisoformat(value) if isinstance(value, str) else value
            if isinstance(value, bool):
                raise ValueError('NUMBER_REQUIRED')
            return decimal(value)
        op, args = next(iter(item.items()))
        if op in CROSS:
            previous = [evaluate(arg, offset + 1) for arg in args]
            current = [evaluate(arg, offset) for arg in args]
            if op == 'cross_up':
                return previous[0] <= previous[1] and current[0] > current[1]
            return previous[0] >= previous[1] and current[0] < current[1]
        # Evaluate operands recursively
        operands = [evaluate(arg, offset) for arg in args]
        if op == 'all': return all(operands)
        if op == 'any': return any(operands)
        if op == 'floor': return operands[0].to_integral_value(rounding=ROUND_FLOOR)
        if op in COMPARE: return COMPARE[op](*operands)
        if op == 'div' and operands[1] == 0:
            raise ValueError('DIVISION_BY_ZERO')
        return decimal(NUMERIC[op](*operands))

    try:
        return evaluate(node)
    except DecimalException as error:
        raise ValueError('INVALID_ARITHMETIC') from error
