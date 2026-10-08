// Nến ở trong dữ liệu, không được dựng thành ô nhập hoặc JSON trên trang.
const PRICE_KEYS = ['bars', 'raw', 's', 't', 'o', 'h', 'l', 'c', 'v'];
const RULE_LIMIT = 65536;
const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
const clone = value => JSON.parse(JSON.stringify(value));

export function splitPayload(payload) {
    if (!object(payload)) throw Error('Payload phải là một object JSON.');
    const config = {...payload}, data = {};
    for (const key of ['trade_data', 'market_data']) {
        const source = payload[key];
        if (source == null) continue;
        if (!object(source)) throw Error(`${key} phải là một object JSON.`);
        data[key] = Object.fromEntries(PRICE_KEYS.filter(name => Object.hasOwn(source, name)).map(name => [name, source[name]]));
        config[key] = Object.fromEntries(Object.entries(source).filter(([name]) => !PRICE_KEYS.includes(name)));
    }
    return {config: clone(config), data};
}

export function assemblePayload(config, data) {
    const payload = clone(config);
    for (const key of ['trade_data', 'market_data']) {
        if (payload[key] != null || data[key]) payload[key] = {...payload[key], ...data[key]};
    }
    return payload;
}

export function dataSource(value, key) {
    if (Array.isArray(value)) return {bars: value};
    if (!object(value)) throw Error('File dữ liệu phải chứa object OHLCV hoặc danh sách nến.');
    const source = Object.hasOwn(value, key) ? value[key] : value;
    if (!object(source) || !PRICE_KEYS.some(name => Object.hasOwn(source, name) && name !== 's')) {
        throw Error(`Không tìm thấy dữ liệu ${key} trong file JSON.`);
    }
    return source;
}

export function sourceInfo(source) {
    const rows = Array.isArray(source?.bars) ? source.bars : null;
    const raw = source?.raw ?? (object(source?.bars) ? source.bars : source);
    const times = rows ? null : raw?.t;
    const count = rows?.length ?? (Array.isArray(times) ? times.length : 0);
    const scale = source?.timestamp_unit === 'ms' ? 1000 : 1;
    const date = stamp => {
        const value = new Date(Number(stamp) / scale * 1000);
        if (!Number.isFinite(value.getTime())) return '?';
        try {
            return new Intl.DateTimeFormat('vi-VN', {
                timeZone: source?.timezone || 'Asia/Ho_Chi_Minh', dateStyle: 'short', timeStyle: 'short',
            }).format(value);
        } catch {return '?';} // Thông tin nguồn sai vẫn được API kiểm tra, không tự sửa.
    };
    return count ? `${count.toLocaleString('vi-VN')} nến · ${date(rows ? rows[0]?.time : times[0])} → ${date(rows ? rows.at(-1)?.time : times.at(-1))}` : 'Chưa nạp dữ liệu.';
}

const general = [
    ['initial_cash', 'Vốn ban đầu', 'decimal', true],
    ['report.start_date', 'Ngày bắt đầu báo cáo', 'date'],
    ['report.end_date', 'Ngày kết thúc báo cáo', 'date'],
    ['strategy.warmup_bars', 'Số nến khởi tạo chỉ báo', 'integer'],
    ['execution.entry_fill_policy', 'Thời điểm khớp lệnh', ['next_open'], true],
    ['execution.slippage_rate', 'Tỷ lệ trượt giá', 'decimal', true],
];
const accountingFields = {
    normalized: [['fee_rate', 'Tỷ lệ phí', 'decimal', true]],
    contract: [['contract_multiplier', 'Hệ số nhân hợp đồng', 'decimal', true, '100000'],
        ['margin_rate', 'Tỷ lệ ký quỹ', 'decimal', true], ['pit_rate', 'Tỷ lệ thuế', 'decimal', true],
        ['exchange_fee_per_contract', 'Phí sở / hợp đồng', 'decimal', true],
        ['clearing_fee_per_contract', 'Phí bù trừ / hợp đồng', 'decimal', true],
        ['broker_fee_per_contract', 'Phí môi giới / hợp đồng', 'decimal', true]],
};
const sizingFields = {
    fixed_fractional: [['risk_fraction', 'Tỷ lệ vốn chịu rủi ro', 'decimal', true], ['stop_loss_fraction', 'Tỷ lệ dừng lỗ', 'decimal', true]],
    risk_and_margin: [['risk_fraction', 'Tỷ lệ vốn chịu rủi ro', 'decimal', true], ['stop_points', 'Khoảng dừng lỗ', 'decimal', true],
        ['margin_buffer', 'Hệ số dự phòng ký quỹ', 'decimal', true], ['max_contracts', 'Số hợp đồng tối đa', 'integer', true],
        ['pyramiding', 'Thêm vị thế cùng hướng', ['false'], true]],
};
const indicatorTypes = ['SMA', 'EMA', 'BB', 'MACD', 'MFI', 'HIGHEST', 'LOWEST'];
const choiceLabels = {
    '5': '5 phút', D: '1 ngày', s: 'Giây', ms: 'Mili giây',
    normalized: 'Mô phỏng theo giá (normalized)', contract: 'Hợp đồng phái sinh (contract)',
    fixed_fractional: 'Theo tỷ lệ vốn và dừng lỗ', risk_and_margin: 'Theo rủi ro và ký quỹ',
    next_open: 'Giá mở cửa nến kế tiếp', false: 'Không', true: 'Có',
};
const get = (value, path) => path.split('.').reduce((parent, key) => parent?.[key], value);
function put(value, path, item) {
    const keys = path.split('.'), last = keys.pop();
    let target = value;
    for (const key of keys) target = target[key] ??= {};
    if (item === undefined) delete target[last]; else target[last] = item;
}

export function mountInputForm(form, getJSON) {
    const $ = selector => form.querySelector(selector);
    let state = {config: {}, data: {}}, bindings = [], ruleBindings = [], indicatorRows = [];
    let operation = 0, pending = false;
    const notice = (text, error = false) => {$('#input-status').textContent = text; $('#input-status').className = `${error ? 'error' : 'muted'} input-wide`;};
    const node = (tag, text) => {const element = document.createElement(tag); if (text !== undefined) element.textContent = text; return element;};
    function control(container, label, value, kind = 'text', required = false, fallback = '') {
        const wrapper = node('label', label);
        const input = node(Array.isArray(kind) ? 'select' : 'input');
        input.required = required;
        if (Array.isArray(kind)) {
            for (const choice of ['', ...new Set([...kind, ...(value == null ? [] : [String(value)])])]) {
                const option = node('option', choiceLabels[choice] || choice || 'Chọn…'); option.value = choice; input.append(option);
            }
        } else {
            input.type = kind === 'date' ? 'date' : 'text';
            if (kind === 'integer' || kind === 'decimal') input.inputMode = 'decimal';
        }
        input.value = value == null ? fallback : String(value);
        input.oninput = () => input.setCustomValidity('');
        wrapper.append(input); container.append(wrapper);
        return {input, value, initial: input.value, kind, label};
    }
    function field(container, path, label, kind, required, fallback) {
        const binding = control(container, label, get(state.config, path), kind, required, fallback);
        bindings.push({...binding, path}); return binding.input;
    }
    function readControl(binding) {
        const {input, value, initial, kind, label} = binding;
        if (input.value === initial) return value;
        const text = input.value.trim();
        if (!text) return undefined;
        if (kind === 'integer' && (!/^\d+$/.test(text) || !Number.isSafeInteger(Number(text)) || Number(text) <= 0)) {
            input.setCustomValidity(`${label} phải là số nguyên dương.`); throw Error(input.validationMessage);
        }
        if (kind === 'decimal' && !Number.isFinite(Number(text))) {
            input.setCustomValidity(`${label} phải là số hữu hạn.`); throw Error(input.validationMessage);
        }
        if (kind === 'integer') return Number(text);
        if (Array.isArray(kind) && ['true', 'false'].includes(text)) return text === 'true';
        return text;
    }
    function rules(container, path, label, required = false, fallback = '') {
        const value = get(state.config, path);
        const text = value == null ? fallback : JSON.stringify(value, null, 2);
        if (text.length > RULE_LIMIT) throw Error(`${label} vượt 65.536 ký tự; vùng điều kiện không nhận dữ liệu nến.`);
        const wrapper = node('label', label), input = node('textarea');
        input.rows = 8; input.spellcheck = false; input.required = required; input.value = text;
        input.oninput = () => input.setCustomValidity(''); wrapper.append(input); container.append(wrapper);
        ruleBindings.push({path, input, label});
    }
    function group(selector, path, choices, specs) {
        const container = $(selector);
        const model = field(container, path, selector === '#accounting-fields' ? 'Mô hình tính tiền' : 'Cách tính khối lượng', choices, true);
        const body = node('div'); body.className = 'input-grid'; container.append(body);
        function parameters() {
            body.replaceChildren(); bindings = bindings.filter(binding => !binding.path.startsWith(path.slice(0, path.lastIndexOf('.') + 1)) || binding.path === path);
            for (const [key, label, kind, required, fallback] of specs[model.value] || []) {
                field(body, path.slice(0, path.lastIndexOf('.') + 1) + key, label, kind, required, fallback);
            }
        }
        parameters();
        model.onchange = () => {
            put(state.config, path.slice(0, path.lastIndexOf('.')), {[path.split('.').at(-1)]: model.value});
            parameters();
        };
    }
    function indicator(name = '', spec = {}) {
        const row = node('fieldset'), legend = node('legend', 'Chỉ báo'); row.append(legend);
        const fields = node('div'); fields.className = 'input-grid'; row.append(fields);
        const title = control(fields, 'Tên chỉ báo', name, 'text', true);
        const type = control(fields, 'Loại chỉ báo', spec.type, indicatorTypes, true);
        const params = node('div'); params.className = 'input-grid'; row.append(params);
        const entry = {row, title, type, params: []};
        function parameters() {
            params.replaceChildren(); entry.params = [];
            const columns = ['SMA', 'HIGHEST', 'LOWEST'].includes(type.input.value) ? ['open', 'high', 'low', 'close', 'volume'] : ['open', 'high', 'low', 'close'];
            const sources = type.input.value === 'MFI' ? ['trade_data', 'market_data'] : ['trade_data', 'market_data'].flatMap(source => columns.map(column => `${source}.${column}`));
            entry.params.push({key: 'source', ...control(params, 'Nguồn chỉ báo', spec.source, sources, true)});
            const keys = type.input.value === 'MACD' ? ['fast_period', 'slow_period', 'signal_period'] : ['period'];
            const labels = {period: 'Chu kỳ', fast_period: 'Chu kỳ nhanh', slow_period: 'Chu kỳ chậm', signal_period: 'Chu kỳ tín hiệu'};
            for (const key of keys) entry.params.push({key, ...control(params, labels[key], spec[key], 'integer', true)});
            if (type.input.value === 'BB') entry.params.push({key: 'stddev_multiplier', ...control(params, 'Hệ số độ lệch chuẩn', spec.stddev_multiplier, 'decimal', true)});
            if (type.input.value === 'MACD') entry.params.push({key: 'histogram', ...control(params, 'Dạng histogram', spec.histogram, ['line'], true)});
        }
        parameters(); type.input.onchange = () => {spec = {}; parameters();};
        const remove = node('button', 'Xóa chỉ báo'); remove.type = 'button';
        remove.onclick = () => {row.remove(); indicatorRows = indicatorRows.filter(item => item !== entry);};
        row.append(remove); $('#indicator-fields').append(row); indicatorRows.push(entry);
    }
    function render() {
        bindings = []; ruleBindings = []; indicatorRows = [];
        for (const selector of ['#general-fields', '#accounting-fields', '#sizing-fields', '#indicator-fields', '#rule-fields']) $(selector).replaceChildren();
        for (const spec of general) field($('#general-fields'), ...spec);
        group('#accounting-fields', 'accounting.model', ['normalized', 'contract'], accountingFields);
        group('#sizing-fields', 'strategy.sizing.type', ['fixed_fractional', 'risk_and_margin'], sizingFields);
        for (const [name, spec] of Object.entries(state.config.strategy?.indicators || {})) indicator(name, spec);
        rules($('#rule-fields'), 'strategy.entry', 'Điều kiện vào lệnh (entry)', true);
        rules($('#rule-fields'), 'strategy.exit', 'Điều kiện thoát lệnh (exit)', true);
        rules($('#rule-fields'), 'strategy.daily_limits', 'Giới hạn trong ngày (daily_limits)');
        for (const key of ['trade_data', 'market_data']) {
            const container = $(`#${key}-fields`); container.replaceChildren();
            for (const spec of [ ['symbol', 'Mã dữ liệu', 'text'], ['resolution', 'Khung thời gian', ['5', 'D'], false, '5'],
                ['timestamp_unit', 'Đơn vị thời gian', ['s', 'ms'], false, 's'], ['timezone', 'Múi giờ', 'text', false, 'Asia/Ho_Chi_Minh'], ['price_unit', 'Đơn vị giá', 'text'] ]) {
                field(container, `${key}.${spec[0]}`, ...spec.slice(1));
            }
            rules(container, `${key}.contract_map`, 'Bảng mã hợp đồng và đáo hạn (contract_map)');
            $(`#${key}-summary`).textContent = sourceInfo({...state.config[key], ...state.data[key]});
        }
    }
    function setPayload(payload) {
        if (PRICE_KEYS.some(key => Object.hasOwn(payload || {}, key)) && !payload.strategy) {
            throw Error('Đây là JSON dữ liệu giá. Hãy nạp vào nguồn giao dịch hoặc thị trường.');
        }
        const next = splitPayload(payload);
        for (const key of ['strategy', 'accounting', 'execution', 'report']) {
            if (next.config[key] != null && !object(next.config[key])) throw Error(`${key} phải là một object JSON.`);
        }
        for (const key of ['sizing', 'indicators']) {
            const value = next.config.strategy?.[key];
            if (value != null && !object(value)) throw Error(`strategy.${key} phải là một object JSON.`);
        }
        if (Object.values(next.config.strategy?.indicators || {}).some(value => !object(value))) {
            throw Error('Mỗi chỉ báo phải là một object JSON.');
        }
        // ponytail: ô điều kiện tối đa 65.536 ký tự; cây công thức lớn cần trình soạn riêng.
        for (const value of [next.config.strategy?.entry, next.config.strategy?.exit, next.config.strategy?.daily_limits,
            next.config.trade_data?.contract_map, next.config.market_data?.contract_map]) {
            if (value != null && JSON.stringify(value, null, 2).length > RULE_LIMIT) throw Error('Cấu hình điều kiện vượt 65.536 ký tự. Không đưa dữ liệu nến vào vùng điều kiện.');
        }
        state = next; render();
    }
    function read(check = true) {
        if (check && pending) throw Error('Vui lòng chờ dữ liệu được nạp xong.');
        if (check) {
            const invalid = form.querySelector('input:invalid, select:invalid, textarea:invalid');
            for (let parent = invalid?.parentElement; parent; parent = parent.parentElement) if (parent.tagName === 'DETAILS') parent.open = true;
            if (!form.reportValidity()) throw Error('Vui lòng điền các trường bắt buộc và kiểm tra giá trị đã nhập.');
        }
        const config = clone(state.config);
        for (const binding of bindings) {
            const value = readControl(binding);
            if (value !== undefined || get(config, binding.path) !== undefined) put(config, binding.path, value);
        }
        const names = new Set();
        const indicators = indicatorRows.map(entry => {
            const name = entry.title.input.value.trim();
            if (!/^[A-Za-z][A-Za-z0-9_]*$/.test(name) || names.has(name)) throw Error('Tên chỉ báo phải hợp lệ và không được trùng.');
            names.add(name);
            return [name, Object.fromEntries([['type', readControl(entry.type)], ...entry.params.map(param => [param.key, readControl(param)])])];
        });
        if (indicators.length || config.strategy?.indicators) put(config, 'strategy.indicators', Object.fromEntries(indicators));
        for (const {path, input, label} of ruleBindings) {
            if (input.value.length > RULE_LIMIT) throw Error(`${label} vượt 65.536 ký tự.`);
            if (!input.value.trim()) {if (get(config, path) !== undefined) put(config, path, undefined); continue;}
            let value;
            try {value = JSON.parse(input.value);} catch {input.setCustomValidity(`${label}: JSON không hợp lệ.`); throw Error(input.validationMessage);}
            put(config, path, value);
        }
        if (config.report && !Object.keys(config.report).length) delete config.report;
        if (config.report && (!config.report.start_date || !config.report.end_date)) throw Error('Kỳ báo cáo cần cả ngày bắt đầu và ngày kết thúc.');
        for (const key of ['trade_data', 'market_data']) if (config[key] && !Object.keys(config[key]).length && !state.data[key]) delete config[key];
        return assemblePayload(config, state.data);
    }
    async function perform(button, action) {
        if (pending) return;
        const current = ++operation; pending = true;
        const controls = [...form.querySelectorAll('input[type=file], #load-example, [id$="-preset"], [id$="-clear"]')];
        for (const control of controls) control.disabled = true;
        form.setAttribute('aria-busy', 'true'); notice('Đang đọc JSON…');
        try {await action(current);} catch (error) {if (current === operation) notice(error.message, true);} finally {
            pending = false; form.setAttribute('aria-busy', 'false');
            for (const control of controls) control.disabled = false;
            if (button.tagName === 'INPUT' && button.type === 'file') button.value = '';
        }
    }
    $('#payload-file').onchange = event => {
        const file = event.target.files[0]; if (!file) return;
        perform(event.target, async current => {
            const payload = JSON.parse(await file.text());
            if (current !== operation) return; setPayload(payload); notice(`Đã điền cấu hình và dữ liệu từ ${file.name}.`);
        });
    };
    $('#load-example').onclick = event => perform(event.currentTarget, async current => {
        const sample = await getJSON('/static/canslim-v1-example.json');
        if (current !== operation) return;
        const existing = assemblePayload(state.config, state.data);
        const sampleConfig = splitPayload(sample).config;
        for (const key of ['trade_data', 'market_data']) if (state.data[key]) sample[key] = {...sampleConfig[key], ...existing[key]};
        setPayload(sample); notice('Đã điền mẫu CANSLIM v1. Dữ liệu đã nạp được giữ lại; mẫu chỉ có 2 nến nếu chưa nạp dữ liệu.');
    });
    for (const key of ['trade_data', 'market_data']) {
        const replaceSource = (value, label) => {
            const current = read(false), incoming = dataSource(value, key);
            const metadata = Object.fromEntries(Object.entries(current[key] || {}).filter(([name]) => !PRICE_KEYS.includes(name)));
            current[key] = {...metadata, ...incoming}; setPayload(current); notice(`Đã nạp ${label}.`);
        };
        $(`#${key}-file`).onchange = event => {
            const file = event.target.files[0]; if (!file) return;
            perform(event.target, async current => {const value = JSON.parse(await file.text()); if (current === operation) replaceSource(value, file.name);});
        };
        $(`#${key}-preset`).onclick = event => perform(event.currentTarget, async current => {
            const value = await getJSON(`/ui-data/${key}`); if (current === operation) replaceSource({...value, symbol: key === 'trade_data' ? 'VN30F1M' : 'VNINDEX', resolution: '5'}, key === 'trade_data' ? 'VN30F1M có sẵn' : 'VNINDEX có sẵn');
        });
        $(`#${key}-clear`).onclick = event => perform(event.currentTarget, async () => {
            const current = read(false); delete current[key]; setPayload(current); notice('Đã bỏ nguồn dữ liệu đã chọn.');
        });
    }
    $('#add-indicator').onclick = () => indicator();
    render();
    return {read, setPayload};
}
