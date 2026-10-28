/** A generic example from the approved contract, without inferred trading rules. */
export const DEFAULT_STRATEGY = {symbol: 'VN30F1M', entry: {long: {left: 'price', op: 'above', right: 'sma20'}}, risk: {sl: 6, tp: 12}};
const CONFIG_KEYS = new Set(['symbol', 'from', 'to', 'quantity', 'entry', 'exit', 'risk', 'order', 'indicators', 'warmup_bars', 'daily_limits']);
/** Clone configuration without retaining mutable editor references. */
const clone = value => JSON.parse(JSON.stringify(value));
/** Require only configuration fields; source references inside expressions remain valid. */
export function strategyConfig(value) {
    if (value === null || typeof value !== 'object' || Array.isArray(value)) throw Error('Cấu hình phải là một đối tượng JSON.');
    const unknown = Object.keys(value).filter(key => !CONFIG_KEYS.has(key));
    if (unknown.length) throw Error(`Trường không được hỗ trợ: ${unknown.join(', ')}. Chỉ nhập cấu hình chiến lược.`);
    if (value.symbol !== 'VN30F1M' || !value.entry || typeof value.entry !== 'object' || Array.isArray(value.entry)) throw Error('Cần mã VN30F1M và điều kiện entry.');
    return clone(value);
}
/** Bind config-only controls and JSON with exact unchanged decimal values. */
export function mountInputForm(form) {
    /** Find one control within this editor. */
    const $ = selector => form.querySelector(selector);
    let state = {}, bindings = [], serialized = '';
    const json = $('#strategy-json');
    /** Display an editor status without replacing the last valid configuration. */
    const notice = (message, error = false) => {$('#input-status').textContent = message; $('#input-status').className = `${error ? 'error' : 'muted'} input-wide`;};
    /** Read a nested value without interpreting expressions. */
    const get = (value, path) => path.split('.').reduce((item, key) => item?.[key], value);
    /** Set or remove one editable leaf while retaining advanced fields. */
    const put = (value, path, next) => {
        const keys = path.split('.'); let target = value;
        for (const key of keys.slice(0, -1)) target = target[key] ??= {};
        if (next === undefined) delete target[keys.at(-1)]; else target[keys.at(-1)] = next;
    };
    /** Synchronize the JSON representation after a deliberate form edit. */
    const sync = () => {
        try {if (json.value !== serialized) throw Error('Hãy áp dụng JSON đang chỉnh trước khi sửa form.'); state = readFields(); serialized = JSON.stringify(state, null, 2); json.value = serialized; notice('Đã đồng bộ cấu hình chiến lược.');}
        catch (error) {notice(error.message, true);}
    };
    /** Create a labelled native control using the page's existing input styles. */
    function field(container, path, label, kind = 'text', options) {
        const wrapper = document.createElement('label'); wrapper.textContent = label;
        const input = document.createElement(options ? 'select' : kind === 'json' ? 'textarea' : 'input');
        if (options) for (const [value, text] of options) {const option = document.createElement('option'); option.value = value; option.textContent = text; input.append(option);}
        else if (kind !== 'json') {input.type = kind === 'decimal' ? 'text' : kind; if (kind === 'decimal') input.inputMode = 'decimal';}
        if (kind === 'json') {input.rows = 3; input.spellcheck = false;}
        const original = get(state, path), fallback = path === 'order.type' ? 'IMMEDIATE' : path === 'quantity' ? '1' : '';
        const display = original === undefined ? fallback : kind === 'json' ? JSON.stringify(original, null, 2) : String(original);
        input.value = display; input.name = path;
        input.onchange = sync;
        wrapper.append(input); container.append(wrapper);
        bindings.push({path, input, kind, original, display, wrapper});
        return bindings.at(-1);
    }
    /** Render simple fields while preserving advanced conditions and action orders in state. */
    function render() {
        bindings = [];
        for (const id of ['#general-fields', '#order-fields', '#risk-fields']) $(id).replaceChildren();
        field($('#general-fields'), 'symbol', 'Mã giao dịch', 'text', [['VN30F1M', 'VN30F1M']]);
        field($('#general-fields'), 'from', 'Từ ngày (tùy chọn)', 'date');
        field($('#general-fields'), 'to', 'Đến ngày (tùy chọn)', 'date');
        field($('#general-fields'), 'quantity', 'Số lượng (mặc định 1)', 'number');
        const quantity = bindings.at(-1).input; quantity.min = '1'; quantity.step = '1';
        const order = field($('#order-fields'), 'order.type', 'Cách khớp', 'text', [['IMMEDIATE', 'Khớp ngay tại Close'], ['LO', 'Lệnh giới hạn (LO)']]);
        const limit = field($('#order-fields'), 'order.limit_price', 'Giá hoặc biểu thức giá giới hạn', 'json');
        /** Explain only the selected matching policy and expose the relevant field. */
        const updateOrder = () => {
            limit.wrapper.hidden = order.input.value !== 'LO';
            $('#order-help').textContent = order.input.value === 'LO' ? 'LO chỉ xét từ nến sau, tối đa 3 nến thực có và chỉ trong ngày đặt; limit giữ nguyên khi chờ.' : 'Khớp ngay tại Close ra tín hiệu, theo giả định mô phỏng độ trễ bằng 0 và khớp đủ lượng.';
        };
        order.input.onchange = () => {updateOrder(); sync();}; updateOrder();
        for (const [path, label] of [['sl', 'Cắt lỗ (%)'], ['tp', 'Chốt lời (%)'], ['trailing', 'Trailing (%)']]) {
            const binding = field($('#risk-fields'), 'risk.' + path, label, 'decimal');
            binding.input.disabled = (path === 'sl' && state.risk?.stop_price !== undefined) || (path === 'tp' && state.risk?.targets !== undefined) || (path === 'trailing' && state.risk?.trailing_after_tp1 !== undefined);
        }
    }
    /** Read edited controls, retaining original types and unchanged decimal strings. */
    function readFields() {
        const value = clone(state), orderType = bindings.find(binding => binding.path === 'order.type').input.value;
        for (const binding of bindings) {
            const {path, input, original, display, kind} = binding;
            if (input.disabled || (path === 'order.limit_price' && orderType !== 'LO')) continue;
            const text = input.value.trim();
            if (text === display) continue;
            let next;
            if (text) {
                if (kind === 'json') {try {next = JSON.parse(text);} catch {throw Error('Giá giới hạn phải là số hoặc biểu thức JSON hợp lệ.');}}
                else if (path === 'quantity') {next = Number(text); if (!Number.isSafeInteger(next) || next < 1) throw Error('Số lượng phải là số nguyên dương.');}
                else if (kind === 'decimal') {if (!Number.isFinite(Number(text)) || Number(text) <= 0) throw Error('Phần trăm bảo vệ phải là số dương hữu hạn.'); next = text;}
                else next = text;
            }
            put(value, path, next);
        }
        if (orderType === 'IMMEDIATE') {
            delete value.order;
        } else {
            value.order ??= {type: 'LO'}; value.order.type = 'LO';
            const limit = bindings.find(binding => binding.path === 'order.limit_price').input.value.trim();
            if (!limit) throw Error('LO cần giá hoặc biểu thức giá giới hạn.');
            try {value.order.limit_price = JSON.parse(limit);} catch {throw Error('Giá giới hạn phải là số hoặc biểu thức JSON hợp lệ.');}
        }
        if (value.risk && !Object.keys(value.risk).length) delete value.risk;
        if (value.quantity === undefined && bindings.find(binding => binding.path === 'quantity').input.value.trim() === '') delete value.quantity;
        if (Boolean(value.from) !== Boolean(value.to)) throw Error('Cần nhập cả hai ngày hoặc bỏ cả hai.');
        if (value.from && (value.from > value.to || !/^\d{4}-\d{2}-\d{2}$/.test(value.from) || !/^\d{4}-\d{2}-\d{2}$/.test(value.to))) throw Error('Kỳ báo cáo không hợp lệ.');
        return strategyConfig(value);
    }
    /** Replace configuration only after parsing and field-scope validation succeed. */
    function setPayload(payload) {
        const next = strategyConfig(payload); state = next; render();
        serialized = JSON.stringify(next, null, 2); json.value = serialized;
        notice('Dữ liệu 5 phút luôn được máy chủ lấy tự động. Có thể chỉnh form hoặc JSON chiến lược.');
    }
    /** Submit the visible JSON draft or the current form, never hidden market arrays. */
    function read() {
        if (json.value !== serialized) {
            let next; try {next = JSON.parse(json.value);} catch {throw Error('JSON chiến lược chưa hợp lệ; cấu hình đang dùng vẫn được giữ.');}
            setPayload(next);
        }
        state = readFields();
        serialized = JSON.stringify(state, null, 2); json.value = serialized;
        notice('Đã đồng bộ cấu hình chiến lược.');
        return clone(state);
    }
    json.onchange = () => {try {setPayload(JSON.parse(json.value));} catch (error) {notice(error.message, true);}};
    $('#apply-strategy').onclick = () => {try {setPayload(JSON.parse(json.value));} catch (error) {notice(error.message, true);}};
    $('#load-example').onclick = () => setPayload(DEFAULT_STRATEGY);
    setPayload(DEFAULT_STRATEGY);
    return {read, setPayload};
}
