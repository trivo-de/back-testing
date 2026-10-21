// Keep candles in source data rather than rendering them as form fields or page JSON.
const PRICE_KEYS = ['bars', 'raw', 's', 't', 'o', 'h', 'l', 'c', 'v', 'auctions', 'contract_dates'];
const RULE_LIMIT = 65536;
/** Recognize non-null JSON objects while excluding arrays. */
const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
/** Clone JSON-compatible input without retaining mutable references. */
const clone = value => JSON.parse(JSON.stringify(value));

/** Separate source price data from editable request configuration. */
export function splitPayload(payload) {
    if (!object(payload)) throw Error('Payload phải là một object JSON.');
    const config = {...payload}, data = {};
    for (const key of ['trade_data', 'market_data']) {
        const source = payload[key];
        if (source == null) continue;
        if (!object(source)) throw Error(`${key} phải là một object JSON.`);
        data[key] = Object.fromEntries(PRICE_KEYS.filter(/* Keep price fields present in the source document. */ name => Object.hasOwn(source, name)).map(/* Pair a price field name with its supplied value. */ name => [name, source[name]]));
        config[key] = Object.fromEntries(Object.entries(source).filter(/* Keep non-price source metadata in the editable configuration. */ ([name]) => !PRICE_KEYS.includes(name)));
    }
    return {config: clone(config), data};
}

/** Combine edited configuration with the retained source data. */
export function assemblePayload(config, data) {
    const payload = clone(config);
    for (const key of ['trade_data', 'market_data']) {
        if (payload[key] != null || data[key]) payload[key] = {...payload[key], ...data[key]};
    }
    return payload;
}

/** Extract a supported source object or candle list from imported JSON. */
export function dataSource(value, key) {
    if (Array.isArray(value)) return {bars: value};
    if (!object(value)) throw Error('File dữ liệu phải chứa object OHLCV hoặc danh sách nến.');
    const source = Object.hasOwn(value, key) ? value[key] : value;
    if (!object(source) || !PRICE_KEYS.some(/* Require at least one source price field other than status. */ name => Object.hasOwn(source, name) && name !== 's')) {
        throw Error(`Không tìm thấy dữ liệu ${key} trong file JSON.`);
    }
    return source;
}

/** Summarize supplied source coverage without modifying the source data. */
export function sourceInfo(source) {
    const rows = Array.isArray(source?.bars) ? source.bars : null;
    const raw = source?.raw ?? (object(source?.bars) ? source.bars : source);
    const times = rows ? null : raw?.t;
    const count = rows?.length ?? (Array.isArray(times) ? times.length : 0);
    const scale = source?.timestamp_unit === 'ms' ? 1000 : 1;
    /** Format a source timestamp in its declared timezone for display. */
    const date = stamp => {
        const value = new Date(Number(stamp) / scale * 1000);
        if (!Number.isFinite(value.getTime())) return '?';
        try {
            return new Intl.DateTimeFormat('vi-VN', {
                timeZone: source?.timezone || 'Asia/Ho_Chi_Minh', dateStyle: 'short', timeStyle: 'short',
            }).format(value);
        } catch {return '?';} // Leave invalid source metadata unchanged for API validation.
    };
    const auctionInfo = source?.auctions?.length ? ` · ${source.auctions.length} bản ghi ATC` : '';
    return count ? `${count.toLocaleString('vi-VN')} nến · ${date(rows ? rows[0]?.time : times[0])} → ${date(rows ? rows.at(-1)?.time : times.at(-1))}${auctionInfo}` : 'Chưa nạp dữ liệu.';
}

const general = [
    ['initial_cash', 'Vốn ban đầu', 'decimal', true],
    ['report.start_date', 'Ngày bắt đầu báo cáo', 'date'],
    ['report.end_date', 'Ngày kết thúc báo cáo', 'date'],
    ['strategy.warmup_bars', 'Số nến khởi tạo chỉ báo', 'integer'],
    ['execution.matching_model', 'Mô hình khớp lệnh', ['next_open', 'hnx_sessions_v1'], false, 'next_open'],
    ['execution.auction_match_quantity', 'Giới hạn khớp mỗi đợt đấu giá', 'nonnegative_integer'],
    ['execution.continuous_match_quantity', 'Lượng đối ứng cố định mỗi nến', 'nonnegative_integer'],
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
        ['pyramiding', 'Thêm vị thế cùng hướng', ['false', 'true'], true]],
};
const indicatorTypes = ['SMA', 'EMA', 'BB', 'MACD', 'MFI', 'HIGHEST', 'LOWEST'];
const choiceLabels = {
    '5': '5 phút', D: '1 ngày', s: 'Giây', ms: 'Mili giây',
    normalized: 'Mô phỏng theo giá (normalized)', contract: 'Hợp đồng phái sinh (contract)',
    fixed_fractional: 'Theo tỷ lệ vốn và dừng lỗ', risk_and_margin: 'Theo rủi ro và ký quỹ',
    next_open: 'Giá mở cửa nến kế tiếp', false: 'Không', true: 'Có', ato: 'ATO lúc 09:00',
    limit: 'Lệnh giới hạn (LO)', hnx_sessions_v1: 'Theo phiên HNX: ATO, LO và ATC',
    SIMULATED: 'Theo mô phỏng đã chọn', LO: 'Lệnh giới hạn (LO)', ATO: 'ATO lúc 09:00', ATC: 'ATC lúc 14:45',
    MTL: 'Thị trường chuyển dư sang LO (MTL)', MOK: 'Thị trường khớp toàn bộ hoặc hủy (MOK)', MAK: 'Thị trường khớp và hủy dư (MAK)',
};
/** Read a nested configuration value using a dotted path. */
const get = (value, path) => path.split('.').reduce(/* Read the next path component if its parent exists. */ (parent, key) => parent?.[key], value);
/** Set or remove a nested configuration field using a dotted path. */
function put(value, path, item) {
    const keys = path.split('.'), last = keys.pop();
    let target = value;
    for (const key of keys) target = target[key] ??= {};
    if (item === undefined) delete target[last]; else target[last] = item;
}

/** Resolve explicit and legacy order settings for one strategy action. */
function effectiveOrder(config, group, name, entry) {
    const legacy = entry ? config.execution?.entry_fill_policy : group.fill_policy;
    const order = clone(group.actions?.[name]?.order ?? group.order ?? {
        type: ({next_open: 'SIMULATED', limit: 'LO', ato: 'ATO', atc: 'ATC'})[legacy] ?? 'SIMULATED',
        ...(group.limit_price ? {limit_price: group.limit_price} : {}),
    });
    if (config.strategy?.entry?.pending) order.pending = clone(config.strategy.entry.pending);
    return order;
}

/** Bind configuration controls, JSON rule editors, and source loaders to the form. */
export function mountInputForm(form, getJSON) {
    /** Find a control within the mounted form. */
    const $ = selector => form.querySelector(selector);
    const autoFetch = $('#auto-fetch-data');
    /** Identify fields that belong to manually supplied market sources. */
    const manualSource = path => path.startsWith('trade_data.') || path.startsWith('market_data.');
    /** Enable or disable manual sources according to automatic fetching mode. */
    function syncDataMode() {
        $('#input-trade').disabled = autoFetch.checked;
        $('#input-market').disabled = autoFetch.checked;
    }
    autoFetch.onchange = syncDataMode;
    let state = {config: {}, data: {}}, bindings = [], ruleBindings = [], indicatorRows = [], orderRefreshers = [];
    let operation = 0, pending = false;
    /** Display an input status or validation error. */
    const notice = (text, error = false) => {$('#input-status').textContent = text; $('#input-status').className = `${error ? 'error' : 'muted'} input-wide`;};
    /** Create a DOM element with optional text content. */
    const node = (tag, text) => {const element = document.createElement(tag); if (text !== undefined) element.textContent = text; return element;};
    /** Create a labeled input control and retain its original value. */
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
            if (kind === 'integer' || kind === 'nonnegative_integer' || kind === 'decimal') input.inputMode = 'decimal';
        }
        input.value = value == null ? fallback : String(value);
        input.oninput = /* Clear a control's custom error when its value is edited. */ () => input.setCustomValidity('');
        wrapper.append(input); container.append(wrapper);
        return {input, value, initial: input.value, kind, label};
    }
    /** Bind a labeled control to a configuration path. */
    function field(container, path, label, kind, required, fallback) {
        const binding = control(container, label, get(state.config, path), kind, required, fallback);
        bindings.push({...binding, path}); return binding.input;
    }
    /** Read a control while preserving unchanged values and validating edited values. */
    function readControl(binding) {
        const {input, value, initial, kind, label} = binding;
        if (input.value === initial) return value;
        const text = input.value.trim();
        if (!text) return undefined;
        if (kind === 'integer' && (!/^\d+$/.test(text) || !Number.isSafeInteger(Number(text)) || Number(text) <= 0)) {
            input.setCustomValidity(`${label} phải là số nguyên dương.`); throw Error(input.validationMessage);
        }
        if (kind === 'nonnegative_integer' && (!/^\d+$/.test(text) || !Number.isSafeInteger(Number(text)))) {
            input.setCustomValidity(`${label} phải là số nguyên không âm.`); throw Error(input.validationMessage);
        }
        if (kind === 'decimal' && !Number.isFinite(Number(text))) {
            input.setCustomValidity(`${label} phải là số hữu hạn.`); throw Error(input.validationMessage);
        }
        if (kind === 'integer' || kind === 'nonnegative_integer') return Number(text);
        if (Array.isArray(kind) && ['true', 'false'].includes(text)) return text === 'true';
        return text;
    }
    /** Create a bounded JSON editor for a rule or metadata field. */
    function rules(container, path, label, required = false, fallback = '') {
        const value = get(state.config, path);
        const text = value == null ? fallback : JSON.stringify(value, null, 2);
        if (text.length > RULE_LIMIT) throw Error(`${label} vượt 65.536 ký tự; vùng điều kiện không nhận dữ liệu nến.`);
        const wrapper = node('label', label), input = node('textarea');
        input.rows = 8; input.spellcheck = false; input.required = required; input.value = text;
        input.oninput = /* Clear the JSON editor's custom error after an edit. */ () => input.setCustomValidity(''); wrapper.append(input); container.append(wrapper);
        ruleBindings.push({path, input, label});
        return input;
    }
    /** Create order controls alongside an entry or exit JSON editor. */
    function orderEditor(container, input, entry) {
        const body = node('div'); body.className = 'input-grid'; container.append(body);
        let drafts = [];
        /** Refresh order controls from the current rule and execution configuration. */
        function refresh(force = false) {
            if (!force && drafts.some(/* Detect unresolved validation errors in draft order controls. */ input => input.validationMessage)) return;
            drafts = [];
            body.replaceChildren();
            let root;
            try {root = JSON.parse(input.value);} catch {return;}
            const group = entry ? root : root?.bar_close;
            if (!object(group)) return;
            const source = clone(state.config);
            try {source.strategy.entry = JSON.parse(ruleBindings.find(/* Find the entry JSON editor used to resolve effective orders. */ binding => binding.path === 'strategy.entry').input.value);} catch {}
            /** Resolve effective order settings for the named action. */
            const effective = name => effectiveOrder(source, group, name, entry);
            const names = group.any ?? [];
            /** Apply an order edit and synchronize its JSON and visible controls. */
            function update(name, patch, refreshControls = true) {
                // Migrate only when edited; untouched historical JSON round-trips exactly.
                const config = read(false);
                const groups = [[config.strategy.entry, true], [config.strategy.exit?.bar_close, false]];
                for (const [value, isEntry] of groups) {
                    if (!value) continue;
                    value.actions = Object.fromEntries(value.any.map(/* Create explicit actions while retaining each action's existing overrides. */ key => [key, {
                        ...value.actions?.[key], ...(isEntry ? {side: value.actions?.[key]?.side ?? key} : {}),
                        order: effectiveOrder(config, value, key, isEntry),
                    }]));
                }
                patch((entry ? config.strategy.entry : config.strategy.exit.bar_close).actions[name].order);
                for (const [value] of groups) if (value) {
                    delete value.limit_price; delete value.pending; delete value.fill_policy;
                }
                delete state.config.execution.entry_fill_policy;
                for (const binding of ruleBindings.filter(/* Select the entry and exit JSON editors for synchronization. */ binding => ['strategy.entry', 'strategy.exit'].includes(binding.path))) {
                    binding.input.value = JSON.stringify(get(config, binding.path), null, 2);
                    binding.input.setCustomValidity('');
                }
                if (refreshControls) orderRefreshers.forEach(/* Refresh a dependent order editor after configuration changes. */ refresh => refresh());
            }
            for (const name of names) {
                const box = node('fieldset'); box.append(node('legend', `${entry ? 'Entry' : 'Exit'}: ${name}`));
                const order = effective(name);
                const model = bindings.find(/* Find the selected matching-model control. */ binding => binding.path === 'execution.matching_model')?.input.value || 'next_open';
                const choices = model === 'hnx_sessions_v1' ? ['SIMULATED', 'LO', entry ? 'ATO' : 'ATC', 'MTL', 'MOK', 'MAK'] : ['SIMULATED'];
                const type = control(box, 'Loại lệnh', order.type, choices, true);
                const price = control(box, 'Biểu thức giá giới hạn', order.limit_price == null ? '' : JSON.stringify(order.limit_price));
                const age = control(box, 'Số nến chờ khớp tối đa', order.pending?.max_execution_bars, 'integer');
                drafts.push(price.input, age.input);
                /** Apply an order control edit and report any validation error. */
                const change = action => {try {action(); notice('Đã cập nhật lệnh trong JSON chiến lược.');} catch (error) {notice(error.message, true);}};
                type.input.onchange = /* Apply the selected order type through the guarded editor update. */ () => change(/* Update the action associated with the order type control. */ () => update(name, /* Set the action's selected order type. */ value => {value.type = type.input.value;}));
                price.input.oninput = price.input.onchange = /* Apply an edited limit-price expression through guarded validation. */ () => change(/* Parse and validate the limit-price control before updating the action. */ () => {
                    price.input.setCustomValidity('');
                    let value;
                    try {value = price.input.value.trim() ? JSON.parse(price.input.value) : undefined;}
                    catch {price.input.setCustomValidity('Biểu thức giá giới hạn: JSON không hợp lệ.'); throw Error(price.input.validationMessage);}
                    update(name, /* Set or remove the action's explicit limit-price expression. */ order => {if (value === undefined) delete order.limit_price; else order.limit_price = value;}, false);
                });
                age.input.oninput = age.input.onchange = /* Apply an edited pending lifetime through guarded validation. */ () => change(/* Read the pending lifetime and update its action configuration. */ () => {
                    age.input.setCustomValidity('');
                    const value = readControl(age);
                    update(name, /* Set or remove the action's pending lifetime and session restrictions. */ order => {
                        if (value === undefined) delete order.pending;
                        else order.pending = {cross_lunch: false, cross_cutoff: false, cross_session: false,
                            ...order.pending, max_execution_bars: value};
                    }, false);
                });
                body.append(box);
            }
            if (names.length) {
                const help = node('p', 'LO cần biểu thức giá. MTL dùng số nến chờ cho LO dư; MAK/MOK không chờ. Lệnh thị trường cần contract/HNX, lượng đối ứng cố định và bảng trần/sàn có nguồn. Đổi loại không tự xóa tham số.');
                help.className = 'input-wide muted'; body.append(help);
            }
        }
        input.oninput = /* Clear JSON validation and rebuild order controls after a rule edit. */ () => {input.setCustomValidity(''); refresh(true);};
        refresh();
        return refresh;
    }
    /** Create a model selector and its parameter controls. */
    function group(selector, path, choices, specs) {
        const container = $(selector);
        const model = field(container, path, selector === '#accounting-fields' ? 'Mô hình tính tiền' : 'Cách tính khối lượng', choices, true);
        const body = node('div'); body.className = 'input-grid'; container.append(body);
        /** Rebuild controls for the currently selected model. */
        function parameters() {
            body.replaceChildren(); bindings = bindings.filter(/* Discard obsolete parameter bindings while retaining the model selector. */ binding => !binding.path.startsWith(path.slice(0, path.lastIndexOf('.') + 1)) || binding.path === path);
            for (const [key, label, kind, required, fallback] of specs[model.value] || []) {
                field(body, path.slice(0, path.lastIndexOf('.') + 1) + key, label, kind, required, fallback);
            }
        }
        parameters();
        model.onchange = /* Replace the selected model configuration and rebuild its parameters. */ () => {
            put(state.config, path.slice(0, path.lastIndexOf('.')), {[path.split('.').at(-1)]: model.value});
            parameters();
        };
    }
    /** Create an editable indicator row with type-specific parameters. */
    function indicator(name = '', spec = {}) {
        const row = node('fieldset'), legend = node('legend', 'Chỉ báo'); row.append(legend);
        const fields = node('div'); fields.className = 'input-grid'; row.append(fields);
        const title = control(fields, 'Tên chỉ báo', name, 'text', true);
        const type = control(fields, 'Loại chỉ báo', spec.type, indicatorTypes, true);
        const params = node('div'); params.className = 'input-grid'; row.append(params);
        const entry = {row, title, type, params: []};
        /** Rebuild parameter controls for the selected indicator type. */
        function parameters() {
            params.replaceChildren(); entry.params = [];
            const columns = ['SMA', 'HIGHEST', 'LOWEST'].includes(type.input.value) ? ['open', 'high', 'low', 'close', 'volume'] : ['open', 'high', 'low', 'close'];
            const sources = type.input.value === 'MFI' ? ['trade_data', 'market_data'] : ['trade_data', 'market_data'].flatMap(/* Expand each source into its supported price-column references. */ source => columns.map(/* Join a source name and column into an indicator reference. */ column => `${source}.${column}`));
            entry.params.push({key: 'source', ...control(params, 'Nguồn chỉ báo', spec.source, sources, true)});
            const keys = type.input.value === 'MACD' ? ['fast_period', 'slow_period', 'signal_period'] : ['period'];
            const labels = {period: 'Chu kỳ', fast_period: 'Chu kỳ nhanh', slow_period: 'Chu kỳ chậm', signal_period: 'Chu kỳ tín hiệu'};
            for (const key of keys) entry.params.push({key, ...control(params, labels[key], spec[key], 'integer', true)});
            if (type.input.value === 'BB') entry.params.push({key: 'stddev_multiplier', ...control(params, 'Hệ số độ lệch chuẩn', spec.stddev_multiplier, 'decimal', true)});
            if (type.input.value === 'MACD') entry.params.push({key: 'histogram', ...control(params, 'Dạng histogram', spec.histogram, ['line'], true)});
        }
        parameters(); type.input.onchange = /* Reset indicator parameters after its type changes. */ () => {spec = {}; parameters();};
        const remove = node('button', 'Xóa chỉ báo'); remove.type = 'button';
        remove.onclick = /* Remove an indicator row and its retained bindings. */ () => {row.remove(); indicatorRows = indicatorRows.filter(/* Keep indicator bindings other than the removed row. */ item => item !== entry);};
        row.append(remove); $('#indicator-fields').append(row); indicatorRows.push(entry);
    }
    /** Render configuration, rule, indicator, and source controls from current state. */
    function render() {
        autoFetch.checked = state.config.auto_fetch_data === true;
        syncDataMode();
        bindings = []; ruleBindings = []; indicatorRows = []; orderRefreshers = [];
        for (const selector of ['#general-fields', '#accounting-fields', '#sizing-fields', '#indicator-fields', '#rule-fields']) $(selector).replaceChildren();
        for (const spec of general) field($('#general-fields'), ...spec);
        group('#accounting-fields', 'accounting.model', ['normalized', 'contract'], accountingFields);
        group('#sizing-fields', 'strategy.sizing.type', ['fixed_fractional', 'risk_and_margin'], sizingFields);
        for (const [name, spec] of Object.entries(state.config.strategy?.indicators || {})) indicator(name, spec);
        const entryGroup = node('div'), exitGroup = node('div');
        entryGroup.className = exitGroup.className = 'input-wide';
        $('#rule-fields').append(entryGroup, exitGroup);
        const entry = rules(entryGroup, 'strategy.entry', 'Điều kiện vào lệnh (entry)', true);
        const refreshEntry = orderEditor(entryGroup, entry, true);
        const exit = rules(exitGroup, 'strategy.exit', 'Điều kiện thoát lệnh (exit)', true);
        const refreshExit = orderEditor(exitGroup, exit, false);
        orderRefreshers = [refreshEntry, refreshExit];
        bindings.find(/* Find the matching-model control used by both order editors. */ binding => binding.path === 'execution.matching_model').input.onchange = /* Refresh entry and exit order controls after a matching-model change. */ () => {refreshEntry(); refreshExit();};
        rules($('#rule-fields'), 'strategy.daily_limits', 'Giới hạn trong ngày (daily_limits)');
        for (const key of ['trade_data', 'market_data']) {
            const container = $(`#${key}-fields`); container.replaceChildren();
            for (const spec of [ ['symbol', 'Mã dữ liệu', 'text'], ['resolution', 'Khung thời gian', ['5', 'D'], false, '5'],
                ['timestamp_unit', 'Đơn vị thời gian', ['s', 'ms'], false, 's'], ['timezone', 'Múi giờ', 'text', false, 'Asia/Ho_Chi_Minh'], ['price_unit', 'Đơn vị giá', 'text'] ]) {
                field(container, `${key}.${spec[0]}`, ...spec.slice(1));
            }
            rules(container, `${key}.contract_map`, 'Bảng mã hợp đồng và đáo hạn (contract_map)');
            if (key === 'trade_data') rules(container, 'trade_data.price_limits', 'Bảng giá trần/sàn theo ngày và hợp đồng (price_limits)');
            $(`#${key}-summary`).textContent = sourceInfo({...state.config[key], ...state.data[key]});
        }
    }
    /** Validate and install a payload before rebuilding the form. */
    function setPayload(payload) {
        if (PRICE_KEYS.some(/* Detect source-only imports that lack a strategy payload. */ key => Object.hasOwn(payload || {}, key)) && !payload.strategy) {
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
        if (Object.values(next.config.strategy?.indicators || {}).some(/* Reject indicator specifications that are not JSON objects. */ value => !object(value))) {
            throw Error('Mỗi chỉ báo phải là một object JSON.');
        }
        // shortcut: rule fields allow 65,536 characters; use a dedicated editor for larger trees.
        for (const value of [next.config.strategy?.entry, next.config.strategy?.exit, next.config.strategy?.daily_limits,
            next.config.trade_data?.contract_map, next.config.market_data?.contract_map]) {
            if (value != null && JSON.stringify(value, null, 2).length > RULE_LIMIT) throw Error('Cấu hình điều kiện vượt 65.536 ký tự. Không đưa dữ liệu nến vào vùng điều kiện.');
        }
        state = next; render();
    }
    /** Read and validate controls before assembling the API request payload. */
    function read(check = true) {
        if (check && pending) throw Error('Vui lòng chờ dữ liệu được nạp xong.');
        if (check) {
            const invalid = form.querySelector('input:invalid, select:invalid, textarea:invalid');
            for (let parent = invalid?.parentElement; parent; parent = parent.parentElement) if (parent.tagName === 'DETAILS') parent.open = true;
            if (!form.reportValidity()) throw Error('Vui lòng điền các trường bắt buộc và kiểm tra giá trị đã nhập.');
        }
        const config = clone(state.config);
        if (autoFetch.checked || Object.hasOwn(config, 'auto_fetch_data')) config.auto_fetch_data = autoFetch.checked;
        for (const binding of bindings) {
            if (autoFetch.checked && manualSource(binding.path)) continue;
            const value = readControl(binding);
            if (value !== undefined || get(config, binding.path) !== undefined) put(config, binding.path, value);
        }
        const names = new Set();
        const indicators = indicatorRows.map(/* Validate an indicator name and collect its current parameters. */ entry => {
            const name = entry.title.input.value.trim();
            if (!/^[A-Za-z][A-Za-z0-9_]*$/.test(name) || names.has(name)) throw Error('Tên chỉ báo phải hợp lệ và không được trùng.');
            names.add(name);
            return [name, Object.fromEntries([['type', readControl(entry.type)], ...entry.params.map(/* Pair an indicator parameter key with its validated control value. */ param => [param.key, readControl(param)])])];
        });
        if (indicators.length || config.strategy?.indicators) put(config, 'strategy.indicators', Object.fromEntries(indicators));
        for (const {path, input, label} of ruleBindings) {
            if (autoFetch.checked && manualSource(path)) continue;
            if (input.value.length > RULE_LIMIT) throw Error(`${label} vượt 65.536 ký tự.`);
            if (!input.value.trim()) {if (get(config, path) !== undefined) put(config, path, undefined); continue;}
            let value;
            try {value = JSON.parse(input.value);} catch {input.setCustomValidity(`${label}: JSON không hợp lệ.`); throw Error(input.validationMessage);}
            put(config, path, value);
        }
        if (check) {
            for (const [group, entry] of [[config.strategy?.entry, true], [config.strategy?.exit?.bar_close, false]]) {
                for (const name of group?.any ?? []) {
                    const order = effectiveOrder(config, group, name, entry);
                    if ((config.execution?.matching_model || 'next_open') === 'next_open' && order.type !== 'SIMULATED') {
                        throw Error('Loại lệnh này cần mô hình khớp theo phiên HNX.');
                    }
                    if ((order.type === 'LO') !== (order.limit_price != null)) {
                        throw Error('LO cần biểu thức giá; loại lệnh khác không nhận giá giới hạn.');
                    }
                    if (['ATO', 'ATC'].includes(order.type) && order.pending && !config.strategy.entry.pending) {
                        throw Error('ATO/ATC không nhận số nến chờ; hãy xóa tham số này.');
                    }
                    if (['MTL', 'MOK', 'MAK'].includes(order.type)) {
                        if (config.accounting?.model !== 'contract') throw Error('Lệnh thị trường chỉ dùng với mô hình contract.');
                        if (config.execution?.continuous_match_quantity == null) throw Error('Lệnh thị trường cần lượng đối ứng cố định mỗi nến.');
                        if (autoFetch.checked || !config.trade_data?.price_limits?.length) throw Error('Lệnh thị trường cần bảng giá trần/sàn được cung cấp; chưa dùng lấy dữ liệu tự động.');
                    }
                    if (['MOK', 'MAK'].includes(order.type) && order.pending &&
                        (!config.strategy.entry.pending || order.pending.max_execution_bars !== 1)) {
                        throw Error('MAK/MOK không nhận số nến chờ; hãy xóa tham số này.');
                    }
                }
            }
        }
        if (config.report && !Object.keys(config.report).length) delete config.report;
        if (config.report && (!config.report.start_date || !config.report.end_date)) throw Error('Kỳ báo cáo cần cả ngày bắt đầu và ngày kết thúc.');
        for (const key of ['trade_data', 'market_data']) if (config[key] && !Object.keys(config[key]).length && !state.data[key]) delete config[key];
        const payload = assemblePayload(config, state.data);
        if (check && autoFetch.checked) {delete payload.trade_data; delete payload.market_data;}
        return payload;
    }
    /** Run one input-loading operation while disabling conflicting controls. */
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
    $('#payload-file').onchange = /* Start importing the selected full-payload JSON file. */ event => {
        const file = event.target.files[0]; if (!file) return;
        perform(event.target, /* Parse the payload file and ignore a superseded loading operation. */ async current => {
            const payload = JSON.parse(await file.text());
            if (current !== operation) return; setPayload(payload); notice(`Đã điền cấu hình và dữ liệu từ ${file.name}.`);
        });
    };
    $('#load-example').onclick = /* Start loading the packaged strategy example. */ event => perform(event.currentTarget, /* Merge the strategy example with previously supplied source data. */ async current => {
        const sample = await getJSON('/static/canslim-v1-example.json');
        if (current !== operation) return;
        const existing = assemblePayload(state.config, state.data);
        const sampleConfig = splitPayload(sample).config;
        if (autoFetch.checked || Object.hasOwn(state.config, 'auto_fetch_data')) sample.auto_fetch_data = autoFetch.checked;
        for (const key of ['trade_data', 'market_data']) if (state.data[key]) sample[key] = {...sampleConfig[key], ...existing[key]};
        setPayload(sample); notice('Đã điền mẫu CANSLIM v1. Dữ liệu đã nạp được giữ lại; mẫu chỉ có 2 nến nếu chưa nạp dữ liệu.');
    });
    for (const key of ['trade_data', 'market_data']) {
        /** Replace one source while retaining compatible request metadata. */
        const replaceSource = (value, label) => {
            const current = read(false), incoming = dataSource(value, key);
            const metadata = Object.fromEntries(Object.entries(current[key] || {}).filter(/* Keep source metadata outside the replaced price fields. */ ([name]) => !PRICE_KEYS.includes(name)));
            delete metadata.price_limits;
            current[key] = {...metadata, ...incoming}; setPayload(current); notice(`Đã nạp ${label}.`);
        };
        $(`#${key}-file`).onchange = /* Start importing a selected market source file. */ event => {
            const file = event.target.files[0]; if (!file) return;
            perform(event.target, /* Parse the source file and apply it only for the active operation. */ async current => {const value = JSON.parse(await file.text()); if (current === operation) replaceSource(value, file.name);});
        };
        $(`#${key}-preset`).onclick = /* Start loading the approved local source snapshot. */ event => perform(event.currentTarget, /* Load the local snapshot with its explicit source symbol and resolution. */ async current => {
            const value = await getJSON(`/ui-data/${key}`); if (current === operation) replaceSource({...value, symbol: key === 'trade_data' ? 'VN30F1M' : 'VNINDEX', resolution: '5'}, key === 'trade_data' ? 'VN30F1M có sẵn' : 'VNINDEX có sẵn');
        });
        $(`#${key}-clear`).onclick = /* Start clearing the selected market source. */ event => perform(event.currentTarget, /* Remove the selected source and refresh the input form. */ async () => {
            const current = read(false); delete current[key]; setPayload(current); notice('Đã bỏ nguồn dữ liệu đã chọn.');
        });
    }
    $('#add-indicator').onclick = /* Append a new editable indicator row. */ () => indicator();
    render();
    return {read, setPayload};
}
