import {backtestData, relatedRows} from './backtest-data.mjs?v=20260929';
import {clearCharts, renderCharts} from './backtest-chart.mjs?v=20260930';

const $ = selector => document.querySelector(selector);
const percent = new Intl.NumberFormat('vi-VN', {style: 'percent', maximumFractionDigits: 2});
let sequence = 0;
let activeRunId;
let posting = false;
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
function reset() {
    sequence += 1; clearCharts(); $('#result').hidden = true;
    $('#state').textContent = 'Đang tải…'; $('#state').className = 'muted'; $('#retry-run').hidden = true;
    return sequence;
}
async function show(run, current) {
    if (current !== sequence) return;
    $('#result').hidden = false;
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
    $('#state').className = 'error'; $('#state').textContent = error.message;
    $('#retry-run').hidden = !activeRunId;
}
async function load(id) {
    if (posting) return;
    const current = reset(); activeRunId = id;
    try {await show(await getJSON(`/api/backtests/${id}`), current);} catch (error) {errorState(error, current);}
}
async function history(openLatest = false) {
    try {
        const runs = await getJSON('/api/backtests');
        $('#history').replaceChildren();
        for (const run of runs) {
            const button = document.createElement('button'); button.type = 'button';
            button.textContent = `${run.metadata.run_id} · Equity ${run.summary.final_equity}`;
            button.addEventListener('click', () => load(run.metadata.run_id)); $('#history').append(button);
        }
        if (!runs.length) $('#history').textContent = 'Chưa có run.';
        if (openLatest && sequence === 0 && runs.length) await load(runs[0].metadata.run_id);
    } catch (error) {$('#history').textContent = `Không tải được history: ${error.message}`;}
}
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
        const payload = JSON.parse($('#payload-json').value);
        const run = await getJSON('/api/backtests', {method: 'POST', headers: {'content-type': 'application/json'}, body: JSON.stringify(payload)});
        activeRunId = run.metadata.run_id; await show(run, current); await history();
    } catch (error) {errorState(error, current);} finally {posting = false; submit.disabled = false;}
};
$('#payload-file').onchange = async event => {
    const file = event.target.files[0];
    if (file) $('#payload-json').value = await file.text();
};
$('#load-example').onclick = async () => {
    try {$('#payload-json').value = JSON.stringify(await getJSON('/static/canslim-v1-example.json'), null, 2);}
    catch (error) {$('#state').textContent = error.message;}
};
$('#validate-payload').onclick = async () => {
    try {
        const body = await getJSON('/api/backtests/validate', {method: 'POST', headers: {'content-type': 'application/json'}, body: JSON.stringify(JSON.parse($('#payload-json').value))});
        $('#state').className = 'muted';
        $('#state').textContent = `${body.status}. ${body.runnable ? 'Có thể chạy; từng nến vẫn cần đủ dữ liệu chỉ báo.' : 'Chưa có bộ thực thi.'}`;
    } catch (error) {$('#state').className = 'error'; $('#state').textContent = error.message;}
};
history(true);
