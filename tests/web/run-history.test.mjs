import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';
import assert from 'node:assert/strict';
import test from 'node:test';

const source = readFileSync(new URL('../../src/backtesting_api/web/backtest-app.mjs', import.meta.url), 'utf8')
    .replace(/^import .*;\r?\n/gm, '');
const tick = () => new Promise(resolve => setImmediate(resolve));
function app(respond) {
    const elements = new Map(), requests = [];
    const element = () => ({hidden: true, value: '{}', style: {}, children: [], listeners: {},
        replaceChildren() {this.children = [];}, append(child) {this.children.push(child);},
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
    const context = {Intl, URLSearchParams, AbortController,
        document: {querySelector: $, createElement: element},
        fetch: async (url, options) => {
            requests.push({url, options});
            return {ok: true, json: () => respond(url, options)};
        }, mountInputForm: () => ({read: () => ({})}), clearCharts() {}, renderCharts() {}, backtestData: () => ({}),
        relatedRows: () => ({fills: [], trades: [], position: [], signals: [], orders: [], equity: []}),
    };
    runInNewContext(source, context);
    const search = () => $('#history-form').onsubmit({preventDefault() {}, target: $('#history-form')});
    return {$, fields, requests, search};
}
const item = (id = 'run-one') => ({run_id: id, symbol: 'VN30F1M', start_date: '2026-03-15',
    end_date: '2026-09-15', money_unit: 'VND', total_return: '0.1', final_equity: '110000000'});

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
    assert.equal(first.cells[5].textContent, '110.000.000');
    await ui.$('#history-next').onclick();
    assert.match(ui.requests[1].url, /after=run-one/);
    const rows = ui.$('#history').querySelectorAll('tbody tr');
    assert.equal(rows.length, 1);
    assert.equal(rows[0].cells[5].textContent, '110.000.000');
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
