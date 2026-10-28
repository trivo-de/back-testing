"""Expand the approved short condition vocabulary into typed expressions."""
from decimal import Decimal
from .portfolio import decimal
from .expressions import MAX_EXPRESSION_DEPTH, MAX_EXPRESSION_NODES


ALIASES = {
    'sma20': {'type': 'SMA', 'period': 20},
    'ema5': {'type': 'EMA', 'period': 5},
    'bb20_2': {'type': 'BB', 'period': 20, 'stddev_multiplier': '2'},
    'macd12_26_9': {'type': 'MACD', 'fast_period': 12, 'slow_period': 26, 'signal_period': 9},
    'mfi14': {'type': 'MFI', 'period': 14},
}


def references(indicators):
    """List available source columns and explicitly configured indicator outputs."""
    refs = {f'{s}.{c}' for s in ('trade_data', 'market_data')
            for c in ('open', 'high', 'low', 'close', 'volume')}
    for name, spec in indicators.items():
        outputs = {'BB': ('middle', 'upper', 'lower'),
                   'MACD': ('line', 'signal', 'histogram')}.get(spec['type'])
        refs.update(f'{name}.{part}' for part in outputs) if outputs else refs.add(name)
    return refs


def expand_condition(node, indicators):
    """Resolve aliases on demand, bounding work before expanding the input tree."""
    budget = [MAX_EXPRESSION_NODES]

    def reference(name):
        """Resolve only the fixed alias catalogue, never infer arbitrary periods."""
        if not isinstance(name, str):
            raise ValueError('UNKNOWN_REF')
        source = 'market_data' if name.startswith('market.') else 'trade_data'
        alias = name.removeprefix('market.')
        if alias == 'price':
            return f'{source}.close'
        base, _, output = alias.partition('.')
        if base in ALIASES:
            spec = ALIASES[base]
            key = ('market_' if source == 'market_data' else 'trade_') + base
            definition = {**spec, 'source': source if spec['type'] == 'MFI' else source + '.close'}
            if key in indicators and indicators[key] != definition:
                raise ValueError('INDICATOR_ALIAS_CONFLICT')
            indicators[key] = definition
            return key + ('.' + output if output else '')
        return name

    def visit(item, depth=0):
        """Translate short comparisons and inclusive numeric ranges recursively."""
        budget[0] -= 1
        if budget[0] < 0:
            raise ValueError('EXPRESSION_TOO_LARGE')
        if depth > MAX_EXPRESSION_DEPTH:
            raise ValueError('EXPRESSION_TOO_DEEP')
        if isinstance(item, str):
            return item if ':' in item else {'ref': reference(item)}
        if not isinstance(item, dict):
            return item
        if 'left' in item or 'op' in item or 'right' in item:
            if set(item) != {'left', 'op', 'right'}:
                raise ValueError('INVALID_EXPRESSION')
            if not isinstance(item['op'], str):
                raise ValueError('UNSUPPORTED_OPERATOR')
            op = {'above': 'gt', 'below': 'lt'}.get(item['op'], item['op'])
            if op not in ('gt', 'lt', 'gte', 'lte', 'cross_up', 'cross_down'):
                raise ValueError('UNSUPPORTED_OPERATOR')
            return {op: [visit(item['left'], depth + 1), visit(item['right'], depth + 1)]}
        if 'ref' in item:
            if set(item) - {'ref', 'shift', 'min', 'max'}:
                raise ValueError('UNKNOWN_REF')
            ref = {'ref': reference(item['ref'])}
            if 'shift' in item:
                ref['shift'] = item['shift']
            bounds = [key for key in ('min', 'max') if key in item]
            if bounds:
                if any(type(item[key]) not in (int, float, Decimal) for key in bounds):
                    raise ValueError('INVALID_RANGE')
                for key in bounds:
                    decimal(item[key])
                if len(bounds) == 2 and item['min'] > item['max']:
                    raise ValueError('INVALID_RANGE')
                return {'all': [{('gte' if key == 'min' else 'lte'): [ref, item[key]]} for key in bounds]}
            return ref
        if len(item) != 1:
            raise ValueError('INVALID_EXPRESSION')
        op, args = next(iter(item.items()))
        if not isinstance(args, list):
            raise ValueError('INVALID_EXPRESSION')
        return {op: [visit(arg, depth + 1) for arg in args]}

    return visit(node)


def required_history(strategy):
    """Include indicator seeds, source shifts and previous crossing samples."""
    periods = {}
    for name, spec in strategy.get('indicators', {}).items():
        periods[name] = (spec['slow_period'] + spec['signal_period'] - 1 if spec['type'] == 'MACD'
                         else spec['period'] + (spec['type'] == 'MFI'))
    required = max(strategy.get('warmup_bars') or 0, max(periods.values(), default=0))

    def collect(value, offset=0):
        """Accumulate lookback along each expression path without summing siblings."""
        nonlocal required
        if isinstance(value, dict):
            if 'ref' in value:
                name = value['ref'].split('.')[0]
                if name in periods or (name in ('trade_data', 'market_data') and (value.get('shift', 0) or offset)):
                    required = max(required, periods.get(name, 1) + value.get('shift', 0) + offset)
            for key, child in value.items():
                collect(child, offset + (key in ('cross_up', 'cross_down')))
        elif isinstance(value, list):
            for child in value:
                collect(child, offset)

    collect(strategy)
    return required
