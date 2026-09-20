import {backtestData} from './backtest-data.mjs';
import {clearCharts, renderCharts} from './backtest-chart.mjs';

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
    $('#run-title').textContent = `Run ${run.metadata.run_id} — ${run.metadata.label}`;
    $('#summary').replaceChildren();
    for (const [key, value] of Object.entries(run.summary)) {
        const card = document.createElement('div');
        card.textContent = `${key}: ${key === 'total_return' ? percent.format(value) : value}`;
        $('#summary').append(card);
    }
    table('#fills', run.fills, ['fill_time', 'side', 'fill_price', 'quantity', 'fee']);
    table('#trades', run.trades, ['entry_date', 'exit_date', 'entry_price', 'exit_price', 'quantity', 'fees', 'net_pnl', 'close_reason']);
    table('#position', run.open_position ? [run.open_position] : [], ['quantity', 'entry_price', 'market_value', 'unrealized_pnl']);
    table('#audit', run.signals, ['signal_time', 'side', 'reason', 'pivot']);
    table('#orders', run.orders, ['created_time', 'side', 'status', 'rejection_reason']);
    table('#equity', run.equity_history, ['trading_date', 'cash', 'quantity', 'market_value', 'equity', 'unrealized_pnl']);
    clearCharts();
    $('#chart-status').textContent = 'Đang tải chart…';
    try {
        const payload = await getJSON(`/api/backtests/${run.metadata.run_id}/chart`);
        if (current !== sequence) return;
        renderCharts(backtestData(run, payload), payload.metadata);
        $('#state').textContent = 'Đã tải kết quả, trade history và chart.';
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
$('#run-form').onsubmit = async event => {
    event.preventDefault(); if (posting) return;
    posting = true; const submit = event.target.querySelector('[type=submit]'); submit.disabled = true;
    const current = reset(); activeRunId = undefined;
    try {
        const payload = {...Object.fromEntries(new FormData(event.target)), symbol: 'HPG', strategy_id: 'canslim_breakout_v0'};
        const run = await getJSON('/api/backtests', {method: 'POST', headers: {'content-type': 'application/json'}, body: JSON.stringify(payload)});
        activeRunId = run.metadata.run_id; await show(run, current); await history();
    } catch (error) {errorState(error, current);} finally {posting = false; submit.disabled = false;}
};
history(true);
