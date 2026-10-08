import {backtestData, relatedRows} from './backtest-data.mjs?v=20260929';
import {clearCharts, renderCharts} from './backtest-chart.mjs?v=20260930';
import {mountInputForm} from './backtest-input.mjs?v=20261008';

const $ = selector => document.querySelector(selector);
const percent = new Intl.NumberFormat('vi-VN', {style: 'percent', maximumFractionDigits: 2});
let sequence = 0;
let activeRunId;
let posting = false;
let historySequence = 0, historyRequest, historyQuery, nextHistoryCursor;
const number = new Intl.NumberFormat('vi-VN', {maximumFractionDigits: 6});
const table = (selector, rows, columns) => {
    const container = $(selector); container.replaceChildren();
    if (!rows.length) {container.textContent = 'Không có dữ liệu.'; return;}
    const element = document.createElement('table');
    const header = element.createTHead().insertRow();
    for (const column of columns) {const cell = document.createElement('th'); cell.textContent = column; header.append(cell);}
    const body = element.createTBody();
    for (const row of rows) {
        const tr = body.insertRow();
        for (const column of columns) tr.insertCell().textContent = row[column] ?? '';
    }
    container.append(element);
};
const getJSON = async (url, options) => {
    const response = await fetch(url, options), body = await response.json();
    if (!response.ok) throw Error(typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail || 'Lỗi API'));
    return body;
};
const inputForm = mountInputForm($('#run-form'), getJSON);
$('#navigation-toggle').onclick = event => {
    const expanded = event.currentTarget.getAttribute('aria-expanded') !== 'true';
    event.currentTarget.setAttribute('aria-expanded', String(expanded));
    $('#page-navigation').setAttribute('data-expanded', String(expanded));
};
$('#navigation-links').onclick = event => {
    if (!event.target.closest('a')) return;
    $('#navigation-toggle').setAttribute('aria-expanded', 'false');
    $('#page-navigation').setAttribute('data-expanded', 'false');
};
function reset() {
    sequence += 1; clearCharts(); $('#result').hidden = true;
    $('#navigation-results').hidden = true;
    $('#state').textContent = 'Đang tải…'; $('#state').className = 'muted'; $('#retry-run').hidden = true;
    return sequence;
}
async function show(run, current) {
    if (current !== sequence) return;
    $('#result').hidden = false;
    $('#navigation-results').hidden = false;
    const contract = run.metadata.accounting_profile === 'contract_v1';
    $('#run-title').textContent = `${run.metadata.symbol || run.metadata.config?.symbol || 'Backtest'} · ${run.metadata.run_id}`;
    $('#summary').replaceChildren();
    for (const [key, value] of Object.entries(run.summary)) {
        const card = document.createElement('div');
        card.textContent = `${key}: ${key === 'total_return' ? percent.format(value) : value}`;
        $('#summary').append(card);
    }
    const renderTables = fillId => {
        const rows = relatedRows(run, fillId);
        table('#fills', rows.fills, ['fill_time', ...(contract ? ['direction', 'contract_code'] : []), 'side', 'fill_price', 'quantity', 'fee', ...(contract ? ['broker_fee', 'exchange_fee', 'clearing_fee', 'pit'] : [])]);
        table('#trades', rows.trades, [...(contract ? ['direction', 'contract_code'] : []), 'entry_date', 'exit_date', 'entry_price', 'exit_price', 'quantity', 'fees', 'net_pnl', 'close_reason']);
        table('#position', rows.position, [...(contract ? ['direction', 'contract_code'] : []), 'quantity', 'entry_price', ...(contract ? ['remaining_entry_cost'] : ['market_value']), 'unrealized_pnl']);
        table('#audit', rows.signals, ['signal_time', 'side', 'reason', ...(contract ? [] : ['pivot'])]);
        table('#orders', rows.orders, ['created_time', 'side', 'status', contract ? 'reason' : 'rejection_reason']);
        table('#equity', rows.equity, ['trading_date', 'cash', 'quantity', ...(contract ? ['required_margin', 'available_cash'] : ['market_value']), 'equity', 'unrealized_pnl']);
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
        $('#state').textContent = `Đã tải kết quả và biểu đồ.${run.evaluation_status ? ` Đánh giá quy tắc: ${run.evaluation_status.status}; ${run.evaluation_status.unevaluable_bars} nến thiếu dữ liệu để đánh giá.` : ''}`;
    } catch (error) {
        if (current !== sequence) return;
        $('#chart-status').textContent = `Không tải được chart: ${error.message}`;
        $('#state').textContent = 'Đã tải kết quả và trade history; chart chưa tải được.';
        $('#state').className = 'error';
        $('#retry-run').hidden = false;
    }
}
function errorState(error, current) {
    if (current !== sequence) return;
    clearCharts(); $('#result').hidden = true;
    $('#navigation-results').hidden = true;
    $('#state').className = 'error'; $('#state').textContent = error.message;
    $('#retry-run').hidden = !activeRunId;
}
async function load(id) {
    if (posting) return;
    const current = reset(); activeRunId = id;
    try {await show(await getJSON(`/api/backtests/${id}`), current);} catch (error) {errorState(error, current);}
}
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
        const rows = page.items.map(item => ({'Chi tiết': '', 'Mã': item.symbol || 'Backtest',
            'Ngày bắt đầu': item.start_date || '?', 'Ngày kết thúc': item.end_date || '?',
            'Sinh lời': percent.format(item.total_return), 'Vốn cuối kỳ': number.format(item.final_equity)}));
        if (rows.length) table('#history', rows, ['Chi tiết', 'Mã', 'Ngày bắt đầu', 'Ngày kết thúc', 'Sinh lời', 'Vốn cuối kỳ']);
        $('#history').querySelectorAll('tbody tr').forEach((row, index) => {
            const id = page.items[index].run_id;
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
$('#history-form').onsubmit = event => {
    event.preventDefault();
    const fields = [...event.target.querySelectorAll('input')];
    for (const input of fields) input.setCustomValidity('');
    for (const [low, high] of [[fields[0], fields[1]], [fields[2], fields[3]]]) {
        if (low.value && high.value && Number(low.value) > Number(high.value)) high.setCustomValidity('Giá trị đến phải lớn hơn hoặc bằng giá trị từ.');
    }
    if (!event.target.reportValidity()) return;
    historyQuery = new URLSearchParams(fields.filter(input => input.value !== '').map(input => [input.name, input.value]));
    history();
};
$('#history-form').oninput = () => {
    for (const input of $('#history-form').querySelectorAll('input')) input.setCustomValidity('');
};
$('#history-next').onclick = () => history(nextHistoryCursor);
$('#retry-run').onclick = () => load(activeRunId);
$('#toggle-equity').onclick = event => {
    const expanded = $('#equity').hidden;
    $('#equity').hidden = !expanded;
    event.currentTarget.textContent = expanded ? 'Thu gọn' : 'Mở rộng';
    event.currentTarget.setAttribute('aria-expanded', String(expanded));
};
$('#run-form').onsubmit = async event => {
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
$('#validate-payload').onclick = async () => {
    try {
        const body = await getJSON('/api/backtests/validate', {method: 'POST', headers: {'content-type': 'application/json'}, body: JSON.stringify(inputForm.read())});
        $('#state').className = 'muted';
        $('#state').textContent = `${body.status}. ${body.runnable ? 'Có thể chạy; từng nến vẫn cần đủ dữ liệu chỉ báo.' : 'Chưa có bộ thực thi.'}`;
    } catch (error) {$('#state').className = 'error'; $('#state').textContent = error.message;}
};
