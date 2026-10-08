import assert from 'node:assert/strict';
import {existsSync, readFileSync} from 'node:fs';
import test from 'node:test';
import {assemblePayload, dataSource, mountInputForm, sourceInfo, splitPayload} from '../../src/backtesting_api/web/backtest-input.mjs';

class Element {
    constructor(tag = 'div') {this.tagName = tag.toUpperCase(); this.children = []; this.value = ''; this.textContent = ''; this.validationMessage = '';}
    append(...items) {for (const item of items) {item.parentElement = this; this.children.push(item);}}
    replaceChildren() {this.children = [];}
    setAttribute() {}
    setCustomValidity(value) {this.validationMessage = value;}
    remove() {this.parentElement.children = this.parentElement.children.filter(item => item !== this);}
}
function editor(getJSON = () => {throw Error('Không được tự tải dữ liệu.');}) {
    const elements = new Map(), form = new Element('form');
    form.querySelector = selector => {
        if (selector.includes(':invalid')) return null;
        if (!elements.has(selector)) {const element = new Element(); elements.set(selector, element); form.append(element);}
        return elements.get(selector);
    };
    form.querySelectorAll = () => [];
    const walk = element => [element, ...element.children.flatMap(walk)];
    form.reportValidity = () => walk(form).every(element => !element.validationMessage && (!element.required || element.value));
    const previous = globalThis.document;
    globalThis.document = {createElement: tag => new Element(tag)};
    try {
        const input = mountInputForm(form, getJSON);
        return {form, input, walk: () => walk(form), field: label => walk(form).find(element => element.tagName === 'LABEL' && element.textContent === label).children[0]};
    } finally {globalThis.document = previous;}
}
const files = ['payload-hpg-canslim-v0-daily.json', 'payload-vn30f1m-canslim-v0.json', 'payload.json', 'payload_raw.json'];
const payload = name => JSON.parse(readFileSync(new URL(`../../data/payload_examples/${name}`, import.meta.url), 'utf8'));
const sample = () => JSON.parse(readFileSync(new URL('../../src/backtesting_api/web/canslim-v1-example.json', import.meta.url), 'utf8'));
const raw = key => {
    const path = new URL(key === 'trade_data'
        ? '../../data/trade/vn30f1m-5m-20260316-20260915.json'
        : '../../data/market/VNINDEX_5&from=1772323200&to=1789516800.json', import.meta.url);
    if (existsSync(path)) return JSON.parse(readFileSync(path, 'utf8'));
    const bars = sample()[key].bars;
    return {s: 'ok', ...Object.fromEntries(['time', 'open', 'high', 'low', 'close', 'volume'].map((field, index) =>
        [['t', 'o', 'h', 'l', 'c', 'v'][index], bars.map(bar => bar[field])]))};
};

test('all supplied payloads fill the form and round-trip exactly without candles in textareas', () => {
    const originalDocument = globalThis.document;
    // setPayload creates controls after the editor has mounted.
    globalThis.document = {createElement: tag => new Element(tag)};
    try {
        const values = [sample(), ...files.filter(name => existsSync(new URL(`../../data/payload_examples/${name}`, import.meta.url))).map(payload)];
        for (const value of values) {
            const ui = editor();
            ui.input.setPayload(value);
            assert.deepEqual(ui.input.read(), value);
            const textareas = ui.walk().filter(element => element.tagName === 'TEXTAREA');
            assert.ok(textareas.every(element => element.value.length <= 65536));
            assert.ok(textareas.every(element => !element.value.includes('"bars"') && !element.value.includes('"t":')));
            assert.ok(ui.walk().length < 500, 'DOM size must not scale with candle count');
        }
    } finally {globalThis.document = originalDocument;}
});

test('editing a parameter changes only that field, keeps decimal text and validates report dates', () => {
    const previous = globalThis.document; globalThis.document = {createElement: tag => new Element(tag)};
    try {
        const ui = editor(), value = sample();
        value.report = {start_date: '2026-03-18', end_date: '2026-09-15'};
        ui.input.setPayload(value);
        ui.field('Vốn ban đầu').value = '100000000.123456789';
        const edited = ui.input.read();
        assert.equal(edited.initial_cash, '100000000.123456789');
        assert.deepEqual({...edited, initial_cash: value.initial_cash}, value);
        assert.equal(edited.trade_data.bars, value.trade_data.bars);
        assert.throws(() => ui.input.setPayload({...value, strategy: {...value.strategy, indicators: {broken: null}}}), /Mỗi chỉ báo/);
        assert.deepEqual(ui.input.read(), edited, 'bad import must preserve current edits');
        ui.field('Ngày kết thúc báo cáo').value = '';
        assert.throws(() => ui.input.read(), /cả ngày bắt đầu/);
    } finally {globalThis.document = previous;}
});

test('both preset formats use existing API data shapes and config-only import retains no displayed price array', () => {
    for (const key of ['trade_data', 'market_data']) {
        const value = raw(key);
        assert.deepEqual(dataSource(value, key), value);
        const split = splitPayload({[key]: {resolution: '5', ...value}});
        assert.deepEqual(split.config[key], {resolution: '5'});
        assert.equal(split.data[key].t, value.t);
        assert.deepEqual(assemblePayload(split.config, split.data)[key], {resolution: '5', ...value});
        assert.match(sourceInfo(value), /nến/);
        assert.match(sourceInfo({...value, timezone: 'invalid-timezone'}), /\?/);
        assert.equal(dataSource({[key]: {bars: value}}, key).bars, value);
    }
    assert.throws(() => dataSource({strategy: {}}, 'trade_data'), /Không tìm thấy/);
    assert.throws(() => splitPayload([]), /object JSON/);
});

test('loading both presets then the sample preserves real raw candles without mixing demo bars', async () => {
    const previous = globalThis.document; globalThis.document = {createElement: tag => new Element(tag)};
    try {
        const ui = editor(url => url.startsWith('/ui-data/') ? raw(url.split('/').at(-1))
            : sample());
        for (const key of ['trade_data', 'market_data']) {
            const button = ui.form.querySelector(`#${key}-preset`);
            await button.onclick({currentTarget: button});
        }
        const button = ui.form.querySelector('#load-example');
        await button.onclick({currentTarget: button});
        const result = ui.input.read();
        assert.equal(result.trade_data.t.length, raw('trade_data').t.length);
        assert.equal(result.market_data.t.length, raw('market_data').t.length);
        assert.equal(Object.hasOwn(result.trade_data, 'bars'), false);
        assert.equal(Object.hasOwn(result.market_data, 'bars'), false);
        assert.deepEqual(result.trade_data.t, raw('trade_data').t);
        assert.ok(ui.form.querySelector('#trade_data-summary').textContent.startsWith(raw('trade_data').t.length.toLocaleString('vi-VN')));
        const before = ui.input.read();
        ui.field('Điều kiện vào lệnh (entry)').value = '{';
        const clear = ui.form.querySelector('#trade_data-clear');
        await clear.onclick({currentTarget: clear});
        assert.match(ui.form.querySelector('#input-status').textContent, /JSON không hợp lệ/);
        ui.field('Điều kiện vào lệnh (entry)').value = JSON.stringify(before.strategy.entry);
        ui.field('Điều kiện vào lệnh (entry)').oninput();
        assert.deepEqual(ui.input.read(), before);
    } finally {globalThis.document = previous;}
});
