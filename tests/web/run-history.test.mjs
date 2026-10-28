import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';
import assert from 'node:assert/strict';
import test from 'node:test';

const source = readFileSync(new URL('../../src/backtesting_api/web/backtest-app.mjs', import.meta.url), 'utf8')
    .replace(/^import .*;\r?\n/gm, '');
const tick = () => new Promise(resolve => setImmediate(resolve));
function app(respond, relatedRows = () => ({fills: [], trades: [], position: [], signals: [], orders: [], equity: []})) {
    const elements = new Map(), requests = [];
    const element = () => ({hidden: true, value: '{}', style: {}, children: [], listeners: {},
        showModal() {this.open = true;}, close() {this.open = false;}, focus() {this.focused = true;},
        replaceChildren() {this.children = [];}, append(...children) {this.children.push(...children);},
        attributes: {}, setAttribute(name, value) {this.attributes[name] = value;},
        getAttribute(name) {return this.attributes[name];},
        addEventListener(type, callback) {this.listeners[type] = callback;},
        querySelector() {return {};},
        querySelectorAll(selector) {return selector === 'tbody tr' ? this.children.flatMap(child => child.body?.rows || []) : [];},
        createTHead() {return {insertRow: element};},
        createTBody() {
            this.body = {rows: [], insertRow() {
                const row = element(); row.cells = [];
                row.insertCell = () => {const cell = element(); row.cells.push(cell); return cell;};
                this.rows.push(row); return row;
            }};
            return this.body;
        }});
    const $ = key => {
        if (!elements.has(key)) elements.set(key, element());
        return elements.get(key);
    };
    const fields = ['min_total_return_pct', 'max_total_return_pct', 'min_equity', 'max_equity']
        .map(name => ({name, value: '', setCustomValidity(message) {this.error = message;}}));
    $('#history-form').querySelectorAll = () => fields;
    $('#history-form').reportValidity = () => fields.every(field => !field.error);
    $('#parameter-search').value = '';
    const context = {Intl, URLSearchParams, AbortController,
        document: {querySelector: $, createElement: element},
        fetch: async (url, options) => {
            requests.push({url, options});
            return {ok: true, json: () => respond(url, options)};
        }, mountInputForm: () => ({read: () => ({})}), clearCharts() {}, renderCharts() {}, backtestData: () => ({}),
        relatedRows,
    };
    runInNewContext(source, context);
    const search = () => $('#history-form').onsubmit({preventDefault() {}, target: $('#history-form')});
    return {$, fields, requests, search};
}
const item = (id = 'run-one') => ({run_id: id, symbol: 'VN30F1M', start_date: '2026-03-15',
    end_date: '2026-09-15', money_unit: 'VND', total_return: '0.1', final_equity: '110000000', run_at: '2026-10-08T17:30:00Z'});

test('each result table collapses independently without fetching or discarding its data', () => {
    const ui = app(() => ({}));
    const ids = ['fills', 'trades', 'position', 'audit', 'orders', 'equity'];
    for (const id of ids) {ui.$('#' + id).hidden = false; ui.$('#' + id).append({textContent: id});}
    for (const id of ids) {
        const button = ui.$('#toggle-' + id), table = ui.$('#' + id);
        button.onclick({currentTarget: button});
        assert.equal(table.hidden, true);
        assert.equal(button.getAttribute('aria-expanded'), 'false');
        assert.equal(button.textContent, 'Mở rộng');
        for (const other of ids.filter(other => other !== id)) assert.equal(ui.$('#' + other).hidden, false);
        button.onclick({currentTarget: button});
        assert.equal(table.hidden, false);
        assert.equal(button.getAttribute('aria-expanded'), 'true');
        assert.equal(button.textContent, 'Rút gọn');
        assert.equal(table.children[0].textContent, id);
    }
    assert.equal(ui.requests.length, 0);
});

test('day-end reason is a translatable label while trade numbers remain raw', async () => {
    const ui = app(url => url.endsWith('/chart') ? {metadata: {}} : {
        schema_version: 3, metadata: {run_id: 'daily-close'}, summary: {}},
        () => ({fills: [], trades: [{exit_price: '100.47', reason: 'END_OF_DAY'}], position: [], signals: [], orders: [], equity: []}));
    await ui.$('#run-form').onsubmit({preventDefault() {}, target: ui.$('#run-form')});
    const row = ui.$('#trades').querySelectorAll('tbody tr')[0];
    assert.equal(row.cells[2].textContent, '100.47');
    assert.equal(row.cells[5].children[0].textContent, 'END_OF_DAY');
});

test('history stays unloaded until search, pages contain summaries and only selection loads detail', async () => {
    const run = {metadata: {run_id: 'run-two', symbol: 'VN30F1M'}, summary: {}};
    let fail = false;
    const ui = app(url => {if (fail) throw Error('Không tải được run'); return url.includes('/history?')
        ? {items: [{...item(url.includes('after=') ? 'run-two' : 'run-one'), money_unit: url.includes('after=') ? 'price_unit' : 'VND'}], next_cursor: url.includes('after=') ? null : 'run-one'}
        : url.endsWith('/chart') ? {metadata: {}} : run;});
    assert.equal(ui.requests.length, 0);
    ui.fields[0].value = '1.1';
    ui.search(); await tick();
    const query = new URL(ui.requests[0].url, 'http://localhost').searchParams;
    assert.equal(query.get('min_total_return_pct'), '1.1');
    assert.equal(query.get('limit'), '20');
    assert.equal(query.has('min_equity'), false);
    assert.equal(ui.requests.length, 1);
    const first = ui.$('#history').querySelectorAll('tbody tr')[0];
    assert.equal(first.cells[1].textContent, 'VN30F1M');
    assert.match(first.cells[2].textContent, /2026-03-15/);
    assert.equal(first.cells[3].textContent, '2026-09-15');
    assert.equal(first.cells[10].textContent, '110.000.000');
    assert.match(first.cells[11].textContent, /00:30:00/);
    assert.match(first.cells[11].textContent, /09\/10\/2026/);
    await ui.$('#history-next').onclick();
    assert.match(ui.requests[1].url, /after=run-one/);
    const rows = ui.$('#history').querySelectorAll('tbody tr');
    assert.equal(rows.length, 1);
    assert.equal(rows[0].cells[10].textContent, '110.000.000');
    assert.equal(ui.$('#history-next').hidden, true);
    await rows[0].cells[0].children[0].listeners.click({stopPropagation() {}});
    assert.deepEqual(ui.requests.slice(2).map(request => request.url), ['/api/backtests/run-two', '/api/backtests/run-two/chart']);
    assert.equal(ui.$('#result').hidden, false);
    assert.equal(ui.$('#navigation-results').hidden, false);
    await rows[0].listeners.click({stopPropagation() {}});
    assert.deepEqual(ui.requests.slice(4).map(request => request.url), ['/api/backtests/run-two', '/api/backtests/run-two/chart']);
    fail = true;
    const loading = rows[0].listeners.click({stopPropagation() {}});
    assert.equal(ui.$('#navigation-results').hidden, true);
    await loading;
    assert.equal(ui.$('#navigation-results').hidden, true);
});

test('compact navigation opens and closes after choosing a page anchor', () => {
    const ui = app(() => ({})), toggle = ui.$('#navigation-toggle');
    toggle.onclick({currentTarget: toggle});
    assert.equal(toggle.getAttribute('aria-expanded'), 'true');
    assert.equal(ui.$('#page-navigation').getAttribute('data-expanded'), 'true');
    ui.$('#navigation-links').onclick({target: {closest: () => null}});
    assert.equal(toggle.getAttribute('aria-expanded'), 'true');
    ui.$('#navigation-links').onclick({target: {closest: () => ({})}});
    assert.equal(toggle.getAttribute('aria-expanded'), 'false');
    assert.equal(ui.$('#page-navigation').getAttribute('data-expanded'), 'false');
});

test('new search ignores a late page and validates ranges; running does not reload history', async () => {
    const pending = [];
    const ui = app(url => url.includes('/history?') ? new Promise(resolve => pending.push(resolve))
        : url.endsWith('/chart') ? {metadata: {}} : {metadata: {run_id: 'new-run'}, summary: {}});
    ui.fields[0].value = '20'; ui.fields[1].value = '10';
    ui.search(); assert.equal(ui.requests.length, 0);
    ui.fields[0].value = '0'; ui.$('#history-form').oninput();
    ui.search(); await tick();
    ui.fields[0].value = '1'; ui.search(); await tick();
    pending[1]({items: [item('new-page')], next_cursor: null}); await tick();
    pending[0]({items: [item('old-page')], next_cursor: null}); await tick();
    assert.equal(ui.$('#history').querySelectorAll('tbody tr')[0].title, 'new-page');
    await ui.$('#run-form').onsubmit({preventDefault() {}, target: ui.$('#run-form')});
    assert.equal(ui.requests.filter(request => request.url.includes('/history?')).length, 2);
    assert.equal(ui.$('#history').children.length, 0);
    assert.match(ui.$('#history-status').textContent, /Bấm Tìm lịch sử/);
});


test('mixed history separates point P&L from legacy money and percentage fields', async () => {
    const ui = app(() => ({items: [item(), {...item('points'), schema_version: 3, pnl_unit: 'point_quantity', total_pnl: '12.5', realized_pnl: '6', max_drawdown: '3', closed_positions: 2, final_equity: null, total_return: null}], next_cursor: null}));
    ui.search(); await tick();
    const rows = ui.$('#history').querySelectorAll('tbody tr');
    assert.equal(rows[0].cells[4].textContent, 'VND');
    assert.equal(rows[0].cells[5].textContent, '—');
    assert.equal(rows[0].cells[10].textContent, '110.000.000');
    assert.equal(rows[1].cells[4].textContent, 'Điểm × lượng');
    assert.equal(rows[1].cells[5].textContent, '12,5');
    assert.equal(rows[1].cells[10].textContent, '—');
});


test('parameter browser loads on demand, preserves safe text and wraps field examples correctly', async () => {
    const ui = app(() => ({parameters: [{id: 'risk.sl', name: 'Cắt lỗ', unit: '%',
        description: '<script>not executable</script>', type: 'decimal', default: null,
        required_data: [], minimum_samples: 0, exclusive_minimum: 0, example: 6},
        {id: 'symbol', name: 'Mã giao dịch', default: 'VN30F1M', example: 'VN30F1M'}],
        request_schema: {required: ['symbol']}, aliases: [], operators: []}));
    assert.equal(ui.requests.length, 0);
    await ui.$('#open-parameters').onclick();
    assert.equal(ui.$('#parameter-panel').open, true);
    assert.equal(ui.$('#parameter-search').focused, true);
    assert.deepEqual(ui.requests.map(item => item.url), ['/api/strategy-parameters']);
    const item = ui.$('#parameter-list').children[0], detail = ui.$('#parameter-detail');
    assert.equal(item.children[1].textContent, 'risk.sl');
    assert.equal(item.getAttribute('aria-pressed'), 'true');
    assert.equal(detail.children[2].textContent, '<script>not executable</script>');
    const metadata = detail.children[3].children.map(node => node.textContent);
    assert.ok(metadata.includes('Không bật'));
    assert.ok(metadata.includes('Phải lớn hơn'));
    assert.ok(!metadata.includes('Lịch sử tối thiểu'));
    assert.ok(!metadata.includes('Dữ liệu cần'));
    assert.equal(detail.children[5].children[0].textContent, '{\n  "risk": {\n    "sl": 6\n  }\n}');
    ui.$('#parameter-list').children[1].onclick();
    assert.ok(detail.children[3].children.some(node => node.textContent === 'Bắt buộc'));
    ui.$('#parameter-search').value = 'không tồn tại'; ui.$('#parameter-search').oninput();
    assert.equal(ui.$('#parameter-list').children.length, 0);
    assert.equal(ui.$('#parameter-detail').textContent, 'Không có tham số phù hợp.');
    assert.match(ui.$('#parameter-status').textContent, /Không có/);
    ui.$('#close-parameters').onclick();
    assert.equal(ui.$('#parameter-panel').open, false);
    await ui.$('#open-parameters-nav').onclick({preventDefault() {}});
    assert.equal(ui.requests.length, 1);
});

test('parameter group selection is local and item changes retain the focused list button', async () => {
    const operator = {id: 'above', name: 'Lớn hơn', example: {left: 'price', op: 'above', right: 0}};
    const ui = app(() => ({parameters: [{id: 'quantity', name: 'Số lượng', type: 'integer', default: 1, example: 3}],
        aliases: [{id: 'price', name: 'Giá đóng cửa', source: 'trade_data', minimum_samples: 1},
                  {id: 'sma20', name: 'SMA20', source: 'trade_data', minimum_samples: 20}],
        sources: [{id: 'trade_data', symbol: 'VN30F1M'}], operators: [operator]}));
    await ui.$('#open-parameters').onclick();
    ui.$('#parameter-group-aliases').onclick();
    const buttons = ui.$('#parameter-list').children.slice();
    buttons[1].onclick();
    assert.equal(ui.$('#parameter-list').children[1], buttons[1]);
    assert.equal(buttons[0].getAttribute('aria-pressed'), 'false');
    assert.equal(buttons[1].getAttribute('aria-pressed'), 'true');
    assert.equal(ui.$('#parameter-detail').children[1].textContent, 'sma20');
    assert.ok(ui.$('#parameter-detail').children[3].children.some(node => node.textContent === 'VN30F1M'));
    assert.ok(ui.$('#parameter-detail').children[3].children.some(node => node.textContent === '20 nến'));
    ui.$('#parameter-group-operators').onclick();
    const detail = ui.$('#parameter-detail');
    assert.equal(detail.children[1].textContent, 'above');
    assert.equal(detail.children[5].children[0].textContent, JSON.stringify(operator.example, null, 2));
    assert.equal(ui.$('#parameter-group-operators').getAttribute('aria-pressed'), 'true');
    assert.equal(ui.requests.length, 1);
});

test('parameter browser shares pending requests and retries after a provider failure', async () => {
    let complete;
    const ui = app(() => new Promise(resolve => {complete = resolve;}));
    const first = ui.$('#open-parameters').onclick(), second = ui.$('#open-parameters').onclick();
    await tick();
    assert.equal(ui.requests.length, 1);
    complete({parameters: [], aliases: [], operators: []});
    await Promise.all([first, second]);
    let unavailable = true;
    const retry = app(() => {if (unavailable) throw Error('controlled outage'); return {parameters: []};});
    await retry.$('#open-parameters').onclick();
    assert.match(retry.$('#parameter-status').textContent, /controlled outage/);
    unavailable = false;
    await retry.$('#open-parameters').onclick();
    assert.equal(retry.requests.length, 2);
    assert.equal(retry.$('#parameter-status').className, 'muted');
});
