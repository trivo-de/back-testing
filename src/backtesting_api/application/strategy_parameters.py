"""Publish the implemented strategy vocabulary from its owning definitions."""
from copy import deepcopy
from ..domain.expressions import COMPARE, NUMERIC, CROSS, MAX_EXPRESSION_DEPTH, MAX_EXPRESSION_NODES
from ..domain.strategy_terms import ALIASES, required_history


def strategy_parameters():
    """Describe current request fields, aliases and operators without a second validator."""
    from ..api.price_schemas import PriceRunRequest
    schema = PriceRunRequest.model_json_schema(by_alias=True)
    simple = {'symbol': 'VN30F1M', 'entry': {'long': {'left': 'price', 'op': 'above', 'right': 'sma20'}},
              'risk': {'sl': 6, 'tp': 12}}
    default_config = PriceRunRequest.model_validate(simple).compiled()
    lo_config = PriceRunRequest.model_validate({**simple, 'order': {'type': 'LO', 'limit_price': 100}}).compiled()['order']
    definitions = [
        ('symbol', 'Mã giao dịch', 'Hiện hỗ trợ VN30F1M.', 'string', 'mã', 'request', 'VN30F1M'),
        ('from', 'Ngày bắt đầu', 'Cùng có hoặc cùng bỏ với ngày kết thúc.', 'string', 'ngày ISO', 'request', None),
        ('to', 'Ngày kết thúc', 'Gồm ngày cuối; không nhận ngày tương lai.', 'string', 'ngày ISO', 'request', None),
        ('quantity', 'Số lượng mở', 'Số nguyên dương; không suy từ vốn.', 'integer', 'đơn vị', 'entry', 1),
        ('entry', 'Điều kiện mở', 'Ít nhất một hướng long hoặc short; all/any không rỗng.', 'object', None, 'entry', None),
        ('exit', 'Điều kiện đóng', 'Đóng đúng hướng đang giữ; mặc định đóng lượng còn lại.', 'object', None, 'exit', None),
        ('order', 'Cách khớp', 'Khớp ngay tại Close hoặc LO từ nến sau; LO tối đa 3 nến trong ngày.', 'object', None, 'order', {'type': 'IMMEDIATE'}),
        ('risk.sl', 'Dừng lỗ', 'Phần trăm từ giá mở thực tế; chỉ xét và thoát tại Close.', 'decimal', '%', 'risk', None),
        ('risk.tp', 'Chốt lời', 'Phần trăm từ giá mở thực tế; 6 nghĩa là 6%.', 'decimal', '%', 'risk', None),
        ('risk.trailing', 'Dừng lỗ kéo theo', 'Theo Close thuận lợi nhất; mức mới hiệu lực từ nến sau.', 'decimal', '%', 'risk', None),
        ('risk.stop_price', 'Giá dừng lỗ tuyệt đối', 'Loại trừ sl; tính và ghim khi quyết định mở.', 'expression', 'điểm giá', 'risk', None),
        ('risk.targets', 'Các mức chốt lời', 'Mỗi mức có pct hoặc price và quantity; remaining chỉ ở cuối.', 'array', None, 'risk', None),
        ('risk.trailing_after_tp1', 'Kéo theo sau TP1', 'Chỉ bắt đầu sau phần TP1; loại trừ trailing từ entry.', 'decimal', '%', 'risk', None),
        ('indicators', 'Chỉ báo tùy chỉnh', 'Khai báo loại, nguồn và chu kỳ; không đè alias có sẵn.', 'object', None, 'expression', {}),
        ('warmup_bars', 'Lịch sử tối thiểu bổ sung', 'Không làm giảm lịch sử chỉ báo, shift hoặc giao cắt.', 'integer', 'nến', 'data', 0),
        ('entry.signal_windows', 'Khung giờ mở', 'Các cặp HH:MM tăng dần, không chồng; giờ Việt Nam.', 'array', 'HH:MM', 'entry', []),
        ('daily_limits.stop_new_entry', 'Điều kiện dừng mở trong ngày', 'day.net_pnl chỉ gồm phần đã chốt theo điểm × lượng.', 'expression', 'boolean', 'entry', None),
        ('exit.flat_by', 'Hạn chót đóng vị thế', 'Còn vị thế tại mốc thì báo lỗi; không tự tạo lần khớp.', 'string', 'HH:MM', 'exit', None),
    ]
    examples = {
        'symbol': 'VN30F1M', 'from': '2026-04-01', 'to': '2026-09-15', 'quantity': 3,
        'entry': simple['entry'], 'exit': {'long': {'left': 'price', 'op': 'below', 'right': 'sma20'}},
        'risk.stop_price': {'sub': [{'ref': 'trade_data.close'}, 6]},
        'risk.targets': [{'pct': 6, 'quantity': 1}, {'pct': 12, 'quantity': 'remaining'}],
        'indicators': {'peak20': {'type': 'HIGHEST', 'source': 'trade_data.high', 'period': 20}},
        'warmup_bars': 150, 'entry.signal_windows': [['09:05', '11:20'], ['13:05', '14:00']],
        'daily_limits.stop_new_entry': {'gte': [{'ref': 'day.entry_fill_count'}, 3]},
        'exit.flat_by': '14:30',
    }
    parameters = []
    for identifier, name, description, kind, unit, scope, default in definitions:
        item = {'id': identifier, 'name': name, 'description': description, 'type': kind,
                'unit': unit, 'scope': scope, 'default': default, 'required_data': [],
                'minimum_samples': 0, 'example': deepcopy(examples.get(identifier))}
        if identifier in schema['properties']:
            item['schema'] = schema['properties'][identifier]
        if identifier in ('quantity', 'warmup_bars'):
            item['minimum'] = 1 if identifier == 'quantity' else 0
        if identifier in ('risk.sl', 'risk.tp', 'risk.trailing', 'risk.trailing_after_tp1'):
            item.update(exclusive_minimum=0, example=6)
        if identifier == 'order':
            item.update(allowed=['IMMEDIATE', 'LO'], example={'type': 'LO', 'limit_price': {'ref': 'trade_data.close'}})
        parameters.append(item)
    aliases = []
    for prefix, source in (('', 'trade_data'), ('market.', 'market_data')):
        aliases.append({'id': prefix + 'price', 'name': 'Giá đóng cửa', 'source': source,
                        'type': 'price', 'parameters': {}, 'outputs': [], 'minimum_samples': 1,
                        'required_data': ['close'], 'example': {'left': prefix + 'price', 'op': 'above', 'right': 0}})
        for name, config in ALIASES.items():
            spec = {**config, 'source': source if config['type'] == 'MFI' else source + '.close'}
            outputs = {'BB': ['middle', 'upper', 'lower'], 'MACD': ['line', 'signal', 'histogram']}.get(config['type'], [])
            identifier = prefix + name
            reference = identifier + ('.' + outputs[0] if outputs else '')
            aliases.append({'id': identifier, 'name': config['type'] + ' ' + name,
                            'source': source, 'type': config['type'], 'parameters': deepcopy(config),
                            'outputs': outputs, 'minimum_samples': required_history({'indicators': {'value': spec}}),
                            'required_data': ['high', 'low', 'close', 'volume'] if config['type'] == 'MFI' else ['close'],
                            'example': {'left': reference, 'op': 'above', 'right': 0}})
    labels = {'above': 'Lớn hơn', 'below': 'Nhỏ hơn', 'gt': 'Lớn hơn', 'lt': 'Nhỏ hơn',
              'gte': 'Lớn hơn hoặc bằng', 'lte': 'Nhỏ hơn hoặc bằng', 'cross_up': 'Cắt lên',
              'cross_down': 'Cắt xuống', 'all': 'Tất cả điều kiện', 'any': 'Ít nhất một điều kiện',
              'add': 'Cộng', 'sub': 'Trừ', 'mul': 'Nhân', 'div': 'Chia', 'min': 'Giá trị nhỏ hơn',
              'max': 'Giá trị lớn hơn', 'floor': 'Làm tròn xuống', 'range': 'Khoảng gồm hai cận',
              'ref': 'Tham chiếu và dịch quá khứ'}
    operators = []
    for name in sorted({*COMPARE, *NUMERIC, *CROSS, 'above', 'below', 'all', 'any', 'floor', 'range', 'ref'}):
        example = ({'left': 'price', 'op': name, 'right': 'sma20'} if name in (*CROSS, 'above', 'below') else
                   {'ref': 'price', 'min': 100, 'max': 200} if name == 'range' else
                   {'ref': 'trade_data.close', 'shift': 1} if name == 'ref' else
                   {name: [{'gt': [2, 1]}]} if name in ('all', 'any') else
                   {'floor': [1.5]} if name == 'floor' else {name: [2, 1]})
        operators.append({'id': name, 'name': labels[name], 'description': labels[name],
                          'operands': 1 if name == 'floor' else 'nonempty' if name in ('all', 'any') else 2,
                          'example': example})
    return {'schema_version': 1, 'default_profile_version': default_config['default_profile_version'],
            'defaults': {'quantity': default_config['quantity'], 'order': default_config['order'],
                         'allow_overnight': default_config['allow_overnight'],
                         'session_end_action': default_config['session_end_action'], 'data_window_months': 6},
            'parameters': parameters, 'aliases': aliases, 'operators': operators, 'request_schema': schema,
            'sources': [{'id': 'trade_data', 'symbol': 'VN30F1M', 'resolution': '5'},
                        {'id': 'market_data', 'symbol': 'VNINDEX', 'resolution': '5'}],
            'limits': {'expression_depth': MAX_EXPRESSION_DEPTH, 'expression_nodes': MAX_EXPRESSION_NODES,
                       'lo_execution_bars': lo_config['max_execution_bars'], 'lo_time_in_force': lo_config['time_in_force']},
            'examples': [{'id': 'minimal-long', 'name': 'LONG không kỳ báo cáo', 'payload': simple}]}
