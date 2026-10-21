"""Read and validate order configuration from strategy payload."""


LEGACY_ORDER_TYPES = {'next_open': 'SIMULATED', 'limit': 'LO', 'ato': 'ATO', 'atc': 'ATC'}


# Resolve each action's direction and order using explicit and legacy settings.
def action_orders(group, *, entry=False, legacy_policy=None, pending=None):
    if group is None:
        return {}
    policy = legacy_policy if entry else group.get('fill_policy')
    legacy = None
    if policy is not None:
        legacy = {'type': LEGACY_ORDER_TYPES[policy]}
        if group.get('limit_price') is not None:
            legacy['limit_price'] = group['limit_price']
        if (policy == 'limit') != ('limit_price' in legacy):
            raise ValueError(('ENTRY' if entry else 'CLOSE') + '_LIMIT_PRICE_REQUIRED_ONLY_FOR_LO')
    elif group.get('limit_price') is not None:
        raise ValueError('LEGACY_LIMIT_PRICE_REQUIRES_FILL_POLICY')
    actions = group.get('actions') or {}
    resolved = {}
    for name in group['any']:
        action = actions.get(name, {})
        order = action.get('order') or group.get('order') or legacy
        if order is None:
            raise ValueError('MISSING_ACTION_ORDER: ' + name)
        if legacy is not None and any(order.get(key) != legacy.get(key) for key in ('type', 'limit_price')):
            raise ValueError('CONFLICTING_LEGACY_ORDER: ' + name)
        order = dict(order)
        if pending is not None:
            if order.get('pending') is not None and order['pending'] != pending:
                raise ValueError('CONFLICTING_LEGACY_PENDING: ' + name)
            order['pending'] = pending
        resolved[name] = {'side': action.get('side', name) if entry else 'CLOSE', 'order': order}
    return resolved


# Resolve entry and bar-close orders from the strategy payload.
def strategy_orders(payload):
    strategy = payload['strategy']
    pending = strategy['entry'].get('pending')
    return (
        action_orders(strategy['entry'], entry=True,
                      legacy_policy=payload['execution'].get('entry_fill_policy'), pending=pending),
        action_orders(strategy['exit'].get('bar_close'), pending=pending),
    )


# Report effective orders together with their configuration source paths.
def order_configuration(payload):
    entry, close = strategy_orders(payload)
    strategy = payload['strategy']
    groups = (('entry', strategy['entry'], entry),
              ('exit.bar_close', strategy['exit'].get('bar_close'), close))
    configuration = {'matching_model': payload['execution'].get('matching_model') or 'next_open'}
    for path, group, actions in groups:
        configuration[path] = {}
        for name, action in actions.items():
            base = 'strategy.' + path
            if (group.get('actions') or {}).get(name, {}).get('order'):
                source = f'{base}.actions.{name}.order'
            elif group.get('order'):
                source = base + '.order'
            else:
                source = 'execution.entry_fill_policy' if path == 'entry' else base + '.fill_policy'
            configuration[path][name] = {**action, 'source': source}
            if strategy['entry'].get('pending') is not None:
                configuration[path][name]['pending_source'] = 'strategy.entry.pending'
    return configuration
