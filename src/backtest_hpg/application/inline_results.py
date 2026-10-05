"""Map contract results without legacy pivot fields or timestamp-based joins."""
from dataclasses import fields, is_dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID, uuid5
from ..config import BACKTEST
from ..domain.contract_accounting import ContractPortfolio
from ..domain.execution import ContractFill, ContractTrade
from ..domain.portfolio import Portfolio


def exact_json(value):
    """Serialize financial values without applying the legacy display precision."""
    if isinstance(value, Decimal): return format(value, 'f')
    if isinstance(value, date): return value.isoformat()
    if isinstance(value, UUID): return str(value)
    if is_dataclass(value): return {f.name: exact_json(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, dict): return {k: exact_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)): return [exact_json(v) for v in value]
    return value


def contract_result_to_dict(run_id, data, result, *, input_hash, policy_hash, accounting):
    """Convert a contract typeresult to a dictionary."""
    if not isinstance(result.portfolio, ContractPortfolio):
        raise ValueError('CONTRACT_RESULT_REQUIRED')
    if len(result.signals) != len(result.orders): raise ValueError('EVENT_COUNT_MISMATCH')
    signals, orders, fills, trades = [], [], [], []
    fill_index = trade_index = position_index = 0
    position = entry = None
    contracts = {bar.trading_date.date(): bar.contract_code for bar in data.bars}
    for sequence, (signal, order) in enumerate(zip(result.signals, result.orders), 1):
        if (signal.signal_date, signal.side) != (order.signal_date, order.side):
            raise ValueError('SIGNAL_ORDER_MISMATCH')
        signal_id, order_id = uuid5(run_id, f'signal:{sequence}'), uuid5(run_id, f'order:{sequence}')
        signals.append({'signal_id': signal_id, 'sequence_no': sequence, 'signal_time': signal.signal_date,
                        'side': signal.side, 'reason': signal.reason})
        if signal.details: signals[-1]['strategy_details'] = dict(signal.details)
        orders.append({'order_id': order_id, 'signal_id': signal_id, 'created_time': order.signal_date,
                       'side': order.side, 'status': order.status.lower(), 'reason': order.reason})
        if signal.side == 'CLOSE' and position is not None:
            orders[-1]['position_id'] = position['position_id']
        if order.status != 'FILLED': continue
        if fill_index >= len(result.fills): raise ValueError('MISSING_FILL')
        fill = result.fills[fill_index]
        fill_index += 1
        if not isinstance(fill, ContractFill) or (fill.signal_date, fill.side) != (signal.signal_date, signal.side):
            raise ValueError('ORDER_FILL_MISMATCH')
        fill_id = uuid5(run_id, f'fill:{fill_index}')
        contract = contracts.get(fill.fill_date.date())
        if fill.side in ('LONG', 'SHORT'):
            if position is not None: raise ValueError('OVERLAPPING_POSITIONS')
            position_index += 1
            position = {'position_id': uuid5(run_id, f'position:{position_index}'), 'direction': fill.direction,
                        'contract_code': contract, 'entry_fill_id': fill_id, 'entry_time': fill.fill_date,
                        'entry_price': fill.price, 'initial_quantity': fill.quantity, 'quantity': fill.quantity}
            entry = fill
        elif position is None or contract != position['contract_code']:
            raise ValueError('EXIT_POSITION_OR_CONTRACT_MISMATCH')
        orders[-1]['position_id'] = position['position_id']
        fills.append({'fill_id': fill_id, 'order_id': order_id, 'position_id': position['position_id'],
                      'contract_code': contract, 'direction': fill.direction, 'side': fill.side,
                      'signal_time': fill.signal_date, 'fill_time': fill.fill_date, 'fill_price': fill.price,
                      'bar_time': fill.bar_time or fill.fill_date,
                      'quantity': fill.quantity, 'fee': fill.fee, **fill.costs.__dict__})
        if fill.side == 'CLOSE':
            if trade_index >= len(result.trades): raise ValueError('MISSING_EXIT_LEG')
            trade = result.trades[trade_index]
            trade_index += 1
            if (not isinstance(trade, ContractTrade) or trade.quantity != fill.quantity
                    or trade.exit_date != fill.fill_date or trade.entry_date != entry.fill_date
                    or trade.direction != position['direction']):
                raise ValueError('EXIT_LEG_MISMATCH')
            trades.append({'trade_id': uuid5(run_id, f'trade:{trade_index}'),
                           'position_id': position['position_id'], 'entry_fill_id': position['entry_fill_id'],
                           'exit_fill_id': fill_id, 'contract_code': contract, 'close_reason': signal.reason,
                           **trade.__dict__})
            position['quantity'] -= fill.quantity
            if position['quantity'] < 0: raise ValueError('NEGATIVE_OPEN_QUANTITY')
            if position['quantity'] == 0: position = None
    if fill_index != len(result.fills) or trade_index != len(result.trades):
        raise ValueError('UNMATCHED_RESULT_EVENTS')
    ledger = result.portfolio.position
    if (ledger is None) != (position is None) or (ledger and ledger.quantity != position['quantity']):
        raise ValueError('POSITION_LEDGER_MISMATCH')
    if position:
        position.update(remaining_entry_cost=ledger.remaining_entry_cost,
                        unrealized_pnl=result.equity_history[-1].snapshot.unrealized_pnl)
        if result.position_details: position['strategy_details'] = dict(result.position_details)
    history = [{'trading_date': point.trading_date, **point.snapshot.__dict__,
                'margin_breach': point.snapshot.equity < point.snapshot.required_margin}
               for point in result.equity_history]
    response = {'schema_version': 2,
                'metadata': {**data.metadata, 'run_id': run_id, 'engine_version': BACKTEST.engine_version,
                             'accounting_profile': 'contract_v1', 'input_hash': input_hash, 'policy_hash': policy_hash,
                             'accounting': accounting, 'initial_cash': result.summary.initial_cash,
                             'money_unit': 'VND', 'quantity_unit': 'contracts',
                             'fill_time_convention': 'Open for market/gap fills; bar Close for intrabar touches'},
                'signals': signals, 'orders': orders, 'fills': fills, 'trades': trades,
                'open_position': position, 'equity_history': history,
                'summary': {**result.summary.__dict__, 'total_fees': result.portfolio.fees}}
    if result.evaluations:
        response['evaluations'] = result.evaluations
        missing = sum(row['status'] == 'UNEVALUABLE' for row in result.evaluations)
        response['evaluation_status'] = {'status': 'UNEVALUABLE' if missing == len(result.evaluations)
                                          else 'PARTIALLY_EVALUABLE' if missing else 'EVALUABLE',
                                          'unevaluable_bars': missing, 'evaluated_bars': len(result.evaluations) - missing}
    return exact_json(response)


def normalized_result_to_dict(run_id, data, result, *, input_hash, policy_hash, accounting):
    """Convert a normalized type result to a dictionary."""
    if not isinstance(result.portfolio, Portfolio):
        raise ValueError('NORMALIZED_RESULT_REQUIRED')
    if len(result.signals) != len(result.orders):
        raise ValueError('EVENT_COUNT_MISMATCH')
    signals, orders, fills, trades = [], [], [], []
    fill_index = trade_index = position_index = 0
    position = entry = None
    for sequence, (signal, order) in enumerate(zip(result.signals, result.orders), 1):
        if (signal.signal_date, signal.side) != (order.signal_date, order.side):
            raise ValueError('SIGNAL_ORDER_MISMATCH')
        signal_id, order_id = uuid5(run_id, f'signal:{sequence}'), uuid5(run_id, f'order:{sequence}')
        details = dict(signal.details)
        signals.append({'signal_id': signal_id, 'sequence_no': sequence, 'signal_time': signal.signal_date,
                        'side': signal.side, 'reason': signal.reason, 'pivot': details.get('pivot')})
        if details: signals[-1]['strategy_details'] = details
        orders.append({'order_id': order_id, 'signal_id': signal_id, 'created_time': order.signal_date,
                       'side': order.side, 'status': 'unfilled' if order.status == 'PENDING' else order.status.lower(),
                       'rejection_reason': order.reason})
        if order.status != 'FILLED':
            continue
        if fill_index >= len(result.fills):
            raise ValueError('MISSING_FILL')
        fill = result.fills[fill_index]
        fill_index += 1
        if (fill.signal_date, fill.side) != (signal.signal_date, signal.side):
            raise ValueError('ORDER_FILL_MISMATCH')
        fill_id = uuid5(run_id, f'fill:{fill_index}')
        if fill.side == 'BUY':
            if position is not None:
                raise ValueError('OVERLAPPING_POSITIONS')
            position_index += 1
            position = {'position_id': uuid5(run_id, f'position:{position_index}'), 'entry_fill_id': fill_id,
                        'entry_time': fill.fill_date, 'entry_price': fill.price, 'quantity': fill.quantity}
            entry = fill
        elif fill.side != 'SELL' or position is None:
            raise ValueError('EXIT_POSITION_MISMATCH')
        orders[-1]['position_id'] = position['position_id']
        fills.append({'fill_id': fill_id, 'order_id': order_id, 'position_id': position['position_id'],
                      'signal_time': fill.signal_date, 'fill_time': fill.fill_date, 'bar_time': fill.fill_date,
                      'side': fill.side, 'fill_price': fill.price, 'quantity': fill.quantity, 'fee': fill.fee})
        if fill.side == 'SELL':
            if trade_index >= len(result.trades):
                raise ValueError('MISSING_TRADE')
            trade = result.trades[trade_index]
            trade_index += 1
            if trade.entry_date != entry.fill_date or trade.exit_date != fill.fill_date or trade.quantity != fill.quantity:
                raise ValueError('TRADE_FILL_MISMATCH')
            trades.append({'trade_id': uuid5(run_id, f'trade:{trade_index}'), 'position_id': position['position_id'],
                           'entry_fill_id': position['entry_fill_id'], 'exit_fill_id': fill_id,
                           'close_reason': signal.reason, **trade.__dict__})
            position = None
    if fill_index != len(result.fills) or trade_index != len(result.trades):
        raise ValueError('UNMATCHED_RESULT_EVENTS')
    ledger = result.portfolio.position
    if (ledger is None) != (position is None):
        raise ValueError('POSITION_LEDGER_MISMATCH')
    if position:
        snapshot = result.equity_history[-1].snapshot
        position.update(market_value=snapshot.market_value, unrealized_pnl=snapshot.unrealized_pnl,
                        entry_pivot=dict(result.position_details).get('pivot'))
    response = {
        'schema_version': 2,
        'metadata': {**data.metadata, 'run_id': run_id, 'engine_version': BACKTEST.engine_version,
                     'accounting_profile': 'normalized_v0', 'input_hash': input_hash,
                     'policy_hash': policy_hash, 'accounting': accounting,
                     'initial_cash': result.summary.initial_cash, 'money_unit': 'price_unit',
                     'quantity_unit': 'normalized_units', 'fill_time_convention': 'next Open'},
        'signals': signals, 'orders': orders, 'fills': fills, 'trades': trades,
        'open_position': position,
        'equity_history': [{'trading_date': point.trading_date, **point.snapshot.__dict__}
                           for point in result.equity_history],
        'summary': {**result.summary.__dict__, 'total_fees': result.portfolio.fees},
    }
    if result.evaluations:
        response['evaluations'] = result.evaluations
        missing = sum(row['status'] == 'UNEVALUABLE' for row in result.evaluations)
        response['evaluation_status'] = {'status': 'UNEVALUABLE' if missing == len(result.evaluations)
                                          else 'PARTIALLY_EVALUABLE' if missing else 'EVALUABLE',
                                         'unevaluable_bars': missing,
                                         'evaluated_bars': len(result.evaluations) - missing}
    return exact_json(response)


def inline_result_to_dict(run_id, data, result, *, input_hash, policy_hash, accounting):
    "Reusing the appropriate result-to-dict function based on the accounting model."
    if accounting['model'] == 'contract':
        return contract_result_to_dict(run_id, data, result, input_hash=input_hash,
                                       policy_hash=policy_hash, accounting=accounting)
    return normalized_result_to_dict(run_id, data, result, input_hash=input_hash,
                                     policy_hash=policy_hash, accounting=accounting)
