import {backtestData, relatedRows} from './backtest-data.mjs?v=20261027-price-cd-v1';
import {clearCharts, renderCharts} from './backtest-chart.mjs?v=20261027-price-cd-v1';
import {mountInputForm} from './backtest-input.mjs?v=20261027-price-cd-v1';

/** Find a page element by its selector. */
const $ = selector => document.querySelector(selector);
const percent = new Intl.NumberFormat('vi-VN', {style: 'percent', maximumFractionDigits: 2});
const runTime = new Intl.DateTimeFormat('vi-VN', {timeZone: 'Asia/Ho_Chi_Minh',
    year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23'});
let sequence = 0;
let activeRunId;
let posting = false;
let historySequence = 0, historyRequest, historyQuery, nextHistoryCursor;
const number = new Intl.NumberFormat('vi-VN', {maximumFractionDigits: 6});
/** Render supplied result rows as a text-only table. */
const table = (selector, rows, columns) => {
    const container = $(selector); container.replaceChildren();
    if (!rows.length) {container.textContent = 'Không có dữ liệu.'; return;}
    const element = document.createElement('table');
    const header = element.createTHead().insertRow();
    for (const column of columns) {const cell = document.createElement('th'); cell.textContent = column; header.append(cell);}
    const body = element.createTBody();
    for (const row of rows) {
        const tr = body.insertRow();
        for (const column of columns) {
            const value = row[column], cell = tr.insertCell();
            if (column === 'reason' && value === 'END_OF_DAY') {
                const label = document.createElement('span'); label.textContent = value; cell.append(label);
            } else cell.textContent = value && typeof value === 'object' ? JSON.stringify(value) : value ?? '';
        }
    }
    container.append(element);
};
/** Fetch JSON and surface HTTP error details. */
const getJSON = async (url, options) => {
    const response = await fetch(url, options), body = await response.json();
    if (!response.ok) throw Error(typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail || 'Lỗi API'));
    return body;
};
const inputForm = mountInputForm($('#run-form'));
/** Display only backend-reported source and coverage, keeping requested dates separate. */
const coverage = metadata => {
    const available = metadata.available_range, requested = metadata.report_range;
    return [metadata.auto_fetch?.provider, available ? `Dữ liệu thực có: ${available.start} – ${available.end}` : '', requested ? `Kỳ báo cáo: ${requested.start} – ${requested.end}` : '', ...(metadata.warnings ?? [])].filter(Boolean).join(' · ');
};
$('#navigation-toggle').onclick = /* Toggle the mobile navigation and its accessible expanded state. */ event => {
    const expanded = event.currentTarget.getAttribute('aria-expanded') !== 'true';
    event.currentTarget.setAttribute('aria-expanded', String(expanded));
    $('#page-navigation').setAttribute('data-expanded', String(expanded));
};
$('#navigation-links').onclick = /* Collapse mobile navigation after a navigation link is selected. */ event => {
    if (!event.target.closest('a')) return;
    $('#navigation-toggle').setAttribute('aria-expanded', 'false');
    $('#page-navigation').setAttribute('data-expanded', 'false');
};
/** Clear the displayed run and invalidate earlier result requests. */
function reset() {
    sequence += 1; clearCharts(); $('#result').hidden = true;
    $('#navigation-results').hidden = true;
    $('#data-coverage').textContent = '';
    $('#state').textContent = 'Đang tải…'; $('#state').className = 'muted'; $('#retry-run').hidden = true;
    return sequence;
}
/** Display a saved run and fetch its matching chart data. */
async function show(run, current) {
    if (current !== sequence) return;
    $('#result').hidden = false;
    $('#navigation-results').hidden = false;
    const priceOnly = run.schema_version === 3;
    const contract = run.metadata.accounting_profile === 'contract_v1';
    $('#pnl-chart-title').textContent = priceOnly ? 'Lãi/lỗ tích lũy (điểm × lượng)' : `Vốn (${run.metadata.money_unit ?? 'đơn vị gốc'})`;
    $('#pnl-table-title').textContent = priceOnly ? 'Lãi/lỗ theo nến (điểm × lượng)' : 'Vốn theo nến — lịch sử cũ';
    $('#data-coverage').textContent = coverage(run.metadata);
    const sessions = run.metadata.matching_model === 'hnx_sessions_v1';
    $('#run-title').textContent = `${run.metadata.symbol || run.metadata.config?.symbol || 'Backtest'} · ${run.metadata.run_id}`;
    $('#summary').replaceChildren();
    for (const [key, value] of Object.entries(run.summary)) {
        const card = document.createElement('div');
        card.textContent = `${key}: ${value === null ? 'Chưa xác định' : ['total_return', 'win_rate'].includes(key) ? percent.format(value) : key === 'pnl_unit' ? 'điểm × lượng' : value}`;
        $('#summary').append(card);
    }
    /** Render result tables for the selected fill or the full run. */
    const renderTables = fillId => {
        const rows = relatedRows(run, fillId);
        if (priceOnly) {
            table('#fills', rows.fills, ['fill_time', 'fill_phase', 'direction', 'side', 'price', 'quantity', 'order_id', 'position_id']);
            table('#trades', rows.trades, ['position_id', 'entry_price', 'exit_price', 'quantity', 'realized_pnl', 'reason']);
            table('#position', rows.position, ['direction', 'entry_price', 'initial_quantity', 'remaining_quantity', 'stop_price', 'target_price', 'targets', 'trailing_price', 'trailing_extreme']);
            table('#audit', rows.signals, ['decision_time', 'direction', 'action', 'reason', 'signal_id']);
            table('#orders', rows.orders, ['created_at', 'type', 'limit_price', 'side', 'quantity', 'status', 'reason', 'end_time', 'execution_bars']);
            table('#equity', rows.equity, ['time', 'realized_pnl', 'unrealized_pnl', 'total_pnl']);
        } else {
        table('#fills', rows.fills, ['fill_time', ...(sessions ? ['order_type', 'phase', 'time_precision'] : []), ...(contract ? ['direction', 'contract_code'] : []), 'side', 'fill_price', 'quantity', 'fee', ...(contract ? ['broker_fee', 'exchange_fee', 'clearing_fee', 'pit'] : [])]);
        table('#trades', rows.trades, [...(contract ? ['direction', 'contract_code'] : []), 'entry_date', 'exit_date', 'entry_price', 'exit_price', 'quantity', 'fees', 'net_pnl', 'close_reason']);
        table('#position', rows.position, [...(contract ? ['direction', 'contract_code'] : []), 'quantity', 'entry_price', ...(contract ? ['remaining_entry_cost'] : ['market_value']), 'unrealized_pnl']);
        table('#audit', rows.signals, ['signal_time', 'side', 'reason', ...(contract ? [] : ['pivot'])]);
        const fixed = run.metadata.continuous_match_quantity != null;
        table('#orders', rows.orders, ['created_time', ...(sessions ? ['order_type', ...(fixed ? ['effective_order_type', 'converted_limit_price'] : []),
            'limit_price', ...(fixed ? ['requested_quantity', 'reference_price'] : []), 'quantity', 'filled_quantity', 'expired_quantity',
            ...(fixed ? ['canceled_quantity', 'rejected_quantity'] : []), 'remaining_quantity', 'completed_time'] : []), 'side', 'status', contract ? 'reason' : 'rejection_reason']);
        table('#equity', rows.equity, ['trading_date', 'cash', 'quantity', ...(contract ? ['required_margin', 'available_cash'] : ['market_value']), 'equity', 'unrealized_pnl']);
        }
        $('#table-filter').hidden = !rows.selected;
        $('#table-filter').textContent = rows.selected ? `Đang lọc theo ${rows.selected.side} lúc ${rows.selected.fill_time}. Bấm vùng trống trên chart để bỏ lọc.` : '';
    };
    renderTables();
    clearCharts();
    $('#chart-status').textContent = 'Đang tải chart…';
    try {
        const payload = await getJSON(`/api/backtests/${run.metadata.run_id}/chart`);
        if (current !== sequence) return;
        renderCharts(backtestData(run, payload), {...payload.metadata, ...run.metadata.config}, renderTables);
        $('#state').textContent = `Đã tải kết quả và biểu đồ.${priceOnly && !run.fills.length ? ' Không có giao dịch trong kỳ.' : ''}${priceOnly && run.open_position ? ' Còn vị thế mở tại cuối dữ liệu thực có.' : ''}${run.evaluation_status ? ` Đánh giá quy tắc: ${run.evaluation_status.status}; ${run.evaluation_status.unevaluable_bars} nến thiếu dữ liệu để đánh giá.` : ''}`;
    } catch (error) {
        if (current !== sequence) return;
        $('#chart-status').textContent = `Không tải được chart: ${error.message}`;
        $('#state').textContent = 'Đã tải kết quả và trade history; chart chưa tải được.';
        $('#state').className = 'error';
        $('#retry-run').hidden = false;
    }
}
/** Show a request error only if it belongs to the active result request. */
function errorState(error, current) {
    if (current !== sequence) return;
    clearCharts(); $('#result').hidden = true;
    $('#navigation-results').hidden = true;
    $('#data-coverage').textContent = '';
    $('#state').className = 'error'; $('#state').textContent = error.message;
    $('#retry-run').hidden = !activeRunId;
}
/** Load a saved run while ignoring stale responses. */
async function load(id) {
    if (posting) return;
    const current = reset(); activeRunId = id;
    try {await show(await getJSON(`/api/backtests/${id}`), current);} catch (error) {errorState(error, current);}
}
/** Load a filtered history page and cancel the previous history request. */
async function history(after) {
    const current = ++historySequence;
    historyRequest?.abort(); historyRequest = new AbortController();
    const query = new URLSearchParams(historyQuery);
    query.set('limit', '20');
    if (after) query.set('after', after);
    $('#history').replaceChildren(); $('#history').setAttribute('aria-busy', 'true');
    $('#history-status').className = 'muted'; $('#history-status').textContent = 'Đang tìm lịch sử…';
    $('#history-next').hidden = true;
    try {
        const page = await getJSON(`/api/backtests/history?${query}`, {signal: historyRequest.signal});
        if (current !== historySequence) return;
        const rows = page.items.map(/* Keep old money units and new point results in distinct columns. */ item => {
            const priceOnly = item.schema_version === 3 || item.pnl_unit === 'point_quantity';
            return {'Chi tiết': '', 'Mã': item.symbol || 'Backtest',
                'Ngày bắt đầu': item.start_date || '?', 'Ngày kết thúc': item.end_date || '?',
                'Đơn vị': priceOnly ? 'Điểm × lượng' : item.money_unit ?? 'Đơn vị gốc',
                'Lãi/lỗ tổng': priceOnly ? number.format(item.total_pnl) : '—',
                'Lãi/lỗ đã chốt': priceOnly ? number.format(item.realized_pnl) : '—',
                'Giảm từ đỉnh': priceOnly ? number.format(item.max_drawdown) : '—',
                'Vị thế đã đóng': priceOnly ? item.closed_positions : '—',
                'Sinh lời bản cũ': !priceOnly && item.total_return != null ? percent.format(item.total_return) : '—',
                'Vốn cuối bản cũ': !priceOnly && item.final_equity != null ? number.format(item.final_equity) : '—',
                'Thời điểm chạy': item.run_at ? runTime.format(new Date(item.run_at)) : '?'};
        });
        if (rows.length) table('#history', rows, ['Chi tiết', 'Mã', 'Ngày bắt đầu', 'Ngày kết thúc', 'Đơn vị', 'Lãi/lỗ tổng', 'Lãi/lỗ đã chốt', 'Giảm từ đỉnh', 'Vị thế đã đóng', 'Sinh lời bản cũ', 'Vốn cuối bản cũ', 'Thời điểm chạy']);
        $('#history').querySelectorAll('tbody tr').forEach(/* Bind accessible mouse and keyboard actions to a history row. */ (row, index) => {
            const id = page.items[index].run_id;
            /** Open the saved run without bubbling the row interaction. */
            const open = event => {event.stopPropagation(); return load(id);};
            const button = document.createElement('button'); button.type = 'button'; button.textContent = 'Xem';
            button.setAttribute('aria-label', `Xem kết quả ${rows[index]['Mã']}, từ ${rows[index]['Ngày bắt đầu']} đến ${rows[index]['Ngày kết thúc']}, ${id.slice(0, 8)}`);
            button.addEventListener('click', open);
            row.title = id; row.addEventListener('click', open);
            row.cells[0].append(button);
        });
        nextHistoryCursor = page.next_cursor;
        $('#history-next').hidden = !nextHistoryCursor;
        $('#history-status').textContent = page.items.length ? `Đang hiển thị ${page.items.length} kết quả.` : 'Không có kết quả phù hợp.';
    } catch (error) {
        if (current !== historySequence || error.name === 'AbortError') return;
        $('#history-status').className = 'error'; $('#history-status').textContent = `Không tải được lịch sử: ${error.message}`;
    } finally {
        if (current === historySequence) $('#history').setAttribute('aria-busy', 'false');
    }
}
$('#history-form').onsubmit = /* Validate history filters and request their first page. */ event => {
    event.preventDefault();
    const fields = [...event.target.querySelectorAll('input, select')];
    for (const input of fields) input.setCustomValidity('');
    for (const low of fields.filter(input => input.name.startsWith('min_'))) {
        const high = fields.find(input => input.name === low.name.replace('min_', 'max_'));
        if (high && low.value && high.value && Number(low.value) > Number(high.value)) high.setCustomValidity('Giá trị đến phải lớn hơn hoặc bằng giá trị từ.');
    }
    if (!event.target.reportValidity()) return;
    historyQuery = new URLSearchParams(fields.filter(/* Keep only populated history filter inputs. */ input => input.value !== '').map(/* Pair a history filter name with its entered value. */ input => [input.name, input.value]));
    history();
};
$('#history-form').oninput = /* Clear custom history filter validation messages. */ () => {
    for (const input of $('#history-form').querySelectorAll('input')) input.setCustomValidity('');
};
$('#history-next').onclick = /* Request the next history page using its saved cursor. */ () => history(nextHistoryCursor);
$('#retry-run').onclick = /* Retry loading the currently selected run. */ () => load(activeRunId);
for (const id of ['fills', 'trades', 'position', 'audit', 'orders', 'equity']) {
    $('#toggle-' + id).onclick = /* Toggle only this result table and keep its accessible state in sync. */ event => {
        const expanded = $('#' + id).hidden;
        $('#' + id).hidden = !expanded;
        event.currentTarget.textContent = expanded ? 'Rút gọn' : 'Mở rộng';
        event.currentTarget.setAttribute('aria-expanded', String(expanded));
    };
}
$('#run-form').onsubmit = /* Submit a backtest request while preventing duplicate submissions. */ async event => {
    event.preventDefault(); if (posting) return;
    posting = true; const submit = event.target.querySelector('[type=submit]'); submit.disabled = true;
    const current = reset(); activeRunId = undefined;
    try {
        const payload = inputForm.read();
        const run = await getJSON('/api/backtests', {method: 'POST', headers: {'content-type': 'application/json'}, body: JSON.stringify(payload)});
        activeRunId = run.metadata.run_id; await show(run, current);
        historySequence += 1; historyRequest?.abort();
        $('#history').replaceChildren(); $('#history').setAttribute('aria-busy', 'false'); $('#history-next').hidden = true;
        $('#history-status').className = 'muted'; $('#history-status').textContent = 'Đã lưu lần chạy mới. Bấm Tìm lịch sử để cập nhật danh sách.';
    } catch (error) {errorState(error, current);} finally {posting = false; submit.disabled = false;}
};
$('#validate-payload').onclick = /* Validate the visible strategy without replacing it with source candles. */ async event => {
    const button = event?.currentTarget ?? $('#validate-payload'); button.disabled = true;
    try {
        const body = await getJSON('/api/backtests/validate', {method: 'POST', headers: {'content-type': 'application/json'}, body: JSON.stringify(inputForm.read())});
        $('#state').className = 'muted';
        $('#state').textContent = body.valid ? 'Cấu hình hợp lệ. Từng nến vẫn cần đủ dữ liệu; chưa tạo lần chạy.' : 'Cấu hình chưa hợp lệ.';
        $('#data-coverage').textContent = coverage(body.data_metadata ?? {});
    } catch (error) {$('#state').className = 'error'; $('#state').textContent = error.message;}
    finally {button.disabled = false;}
};
let catalogue, catalogueRequest, parameterGroup = 'parameters', selectedParameter;
/** Format catalogue values for readers without changing their underlying contract. */
function parameterValue(value) {
    const labels = {integer: 'Số nguyên', decimal: 'Số thập phân', string: 'Văn bản', object: 'Cấu hình',
        array: 'Danh sách', expression: 'Biểu thức', price: 'Giá', IMMEDIATE: 'Khớp tại giá đóng cửa', LO: 'Lệnh giới hạn',
        close: 'Giá đóng cửa', high: 'Giá cao nhất', low: 'Giá thấp nhất', volume: 'Khối lượng'};
    if (Array.isArray(value)) return value.length ? value.map(parameterValue).join(', ') : 'Không giới hạn bổ sung';
    if (value && typeof value === 'object') return value.type === 'IMMEDIATE' ? labels.IMMEDIATE
        : Object.keys(value).length ? JSON.stringify(value) : 'Không khai báo thêm';
    return Object.hasOwn(labels, value) ? labels[value] : String(value);
}
/** Display one selected item using text nodes, including a correctly nested JSON example. */
function renderParameterDetail(entry) {
    const container = $('#parameter-detail'); container.replaceChildren();
    if (!entry) {container.textContent = 'Không có tham số phù hợp.'; return;}
    const heading = document.createElement('h3'); heading.textContent = entry.name ?? entry.id;
    const identifier = document.createElement('code'); identifier.textContent = entry.id;
    const description = document.createElement('p'); description.textContent = entry.description ?? '';
    container.append(heading, identifier, description);
    const values = document.createElement('dl');
    for (const [field, label] of [['type', 'Giá trị nhận'], ['unit', 'Đơn vị'], ['default', 'Khi bỏ trống'],
        ['minimum', 'Tối thiểu'], ['exclusive_minimum', 'Phải lớn hơn'], ['maximum', 'Tối đa'],
        ['allowed', 'Giá trị hợp lệ'], ['source', 'Nguồn'], ['required_data', 'Dữ liệu cần'],
        ['minimum_samples', 'Lịch sử tối thiểu'], ['parameters', 'Tham số chỉ báo'], ['outputs', 'Đầu ra']]) {
        let value = entry[field];
        if (value === undefined || (value === null && field !== 'default')
                || (field !== 'default' && value && typeof value === 'object' && !Object.keys(value).length)
                || (field === 'minimum_samples' && value === 0)) continue;
        if (field === 'default') {
            if (catalogue.request_schema?.required?.includes(entry.id)) value = 'Bắt buộc';
            else if (value === null) value = entry.id.startsWith('risk.') || entry.id === 'daily_limits.stop_new_entry'
                ? 'Không bật' : 'Không chỉ định';
        }
        if (field === 'source') value = catalogue.sources?.find(source => source.id === value)?.symbol ?? value;
        if (field === 'minimum_samples') value = `${value} nến`;
        const term = document.createElement('dt'), content = document.createElement('dd');
        term.textContent = label; content.textContent = parameterValue(value); values.append(term, content);
    }
    container.append(values);
    if (entry.example !== undefined && entry.example !== null) {
        const title = document.createElement('h4'); title.textContent = 'Ví dụ JSON';
        const pre = document.createElement('pre'), code = document.createElement('code');
        const example = parameterGroup === 'parameters'
            ? entry.id.split('.').reduceRight((value, key) => ({[key]: value}), entry.example) : entry.example;
        code.textContent = JSON.stringify(example, null, 2); pre.append(code); container.append(title, pre);
    }
}
/** Search the selected group and retain selection whenever the matching item still exists. */
function renderParameters() {
    const container = $('#parameter-list'); container.replaceChildren();
    if (!catalogue) return;
    const query = $('#parameter-search').value.trim().toLocaleLowerCase('vi');
    const entries = (catalogue[parameterGroup] ?? []).filter(item => JSON.stringify(item).toLocaleLowerCase('vi').includes(query));
    if (!entries.some(entry => entry.id === selectedParameter)) selectedParameter = entries[0]?.id;
    for (const entry of entries) {
        const button = document.createElement('button'); button.type = 'button';
        button.setAttribute('aria-pressed', String(entry.id === selectedParameter));
        button.setAttribute('aria-controls', 'parameter-detail');
        const name = document.createElement('span'), identifier = document.createElement('code');
        name.textContent = entry.name ?? entry.id; identifier.textContent = entry.id; button.append(name, identifier);
        button.onclick = /* Update detail without replacing the focused selection button. */ () => {
            selectedParameter = entry.id;
            for (const item of container.children) item.setAttribute('aria-pressed', String(item === button));
            renderParameterDetail(entry);
        };
        container.append(button);
    }
    renderParameterDetail(entries.find(entry => entry.id === selectedParameter));
    $('#parameter-status').className = 'muted';
    $('#parameter-status').textContent = entries.length ? `Có ${entries.length} mục phù hợp.` : 'Không có tham số phù hợp.';
}
$('#parameter-search').oninput = renderParameters;
for (const group of ['parameters', 'aliases', 'operators']) {
    $('#parameter-group-' + group).onclick = /* Switch catalogue groups without refetching or editing strategy JSON. */ () => {
        parameterGroup = group;
        for (const key of ['parameters', 'aliases', 'operators']) $('#parameter-group-' + key).setAttribute('aria-pressed', String(key === group));
        renderParameters();
    };
}
/** Open the native modal with lazy loading, request sharing and retry on a later open. */
async function openParameters(event) {
    event?.preventDefault();
    const panel = $('#parameter-panel');
    if (!panel.open) panel.showModal();
    $('#parameter-search').focus();
    if (catalogue) {renderParameters(); return;}
    $('#parameter-status').className = 'muted';
    $('#parameter-status').textContent = 'Đang tải danh mục tham số…';
    try {catalogueRequest ??= getJSON('/api/strategy-parameters'); catalogue = await catalogueRequest; renderParameters();}
    catch (error) {catalogueRequest = undefined; $('#parameter-status').className = 'error'; $('#parameter-status').textContent = `Không tải được danh mục: ${error.message}`;}
}
$('#open-parameters').onclick = openParameters;
$('#open-parameters-nav').onclick = openParameters;
$('#close-parameters').onclick = /* Let the native dialog restore focus to its opening control. */ () => $('#parameter-panel').close();
