import assert from 'node:assert/strict';
import test from 'node:test';
import {DEFAULT_STRATEGY, mountInputForm, strategyConfig} from '../../src/backtesting_api/web/backtest-input.mjs';

/** Supply only the native control operations exercised by the editor. */
class Element {
    constructor(tag = 'div') {this.tagName = tag.toUpperCase(); this.children = []; this.value = ''; this.textContent = ''; this.disabled = false;}
    append(...items) {for (const item of items) {item.parentElement = this; this.children.push(item);}}
    replaceChildren() {this.children = [];}
}
/** Mount the actual editor against a small native-control test surface. */
function editor(t) {
    const elements = new Map(), form = new Element('form');
    form.querySelector = selector => {
        if (!elements.has(selector)) {const element = new Element(); elements.set(selector, element); form.append(element);}
        return elements.get(selector);
    };
    const previous = globalThis.document;
    globalThis.document = {createElement: tag => new Element(tag)};
    t.after(() => {globalThis.document = previous;});
    const input = mountInputForm(form);
    const walk = element => [element, ...element.children.flatMap(walk)];
    return {input, element: selector => form.querySelector(selector), field: name => walk(form).find(element => element.name === name)};
}

test('default strategy contains configuration only and preserves omitted defaults', t => {
    const ui = editor(t);
    assert.deepEqual(ui.input.read(), DEFAULT_STRATEGY);
    assert.equal(ui.field('quantity').value, '1');
    assert.equal(ui.field('order.type').value, 'IMMEDIATE');
    assert.equal(ui.field('order.limit_price').parentElement.hidden, true);
    assert.match(ui.element('#order-help').textContent, /Close/);
    for (const key of ['accounting', 'initial_cash', 'trade_data', 'market_data', 'auto_fetch_data']) assert.equal(key in ui.input.read(), false);
});

test('legacy payloads and source arrays are rejected instead of silently converted', () => {
    for (const key of ['accounting', 'initial_cash', 'trade_data', 'market_data', 'bars', 'raw', 'file', 'auto_fetch_data', 'strategy']) {
        assert.throws(() => strategyConfig({...DEFAULT_STRATEGY, [key]: {}}), /không được hỗ trợ/);
    }
    assert.throws(() => strategyConfig([]));
});

test('form edits preserve exact decimal strings and untouched advanced configuration', t => {
    const ui = editor(t), value = {...DEFAULT_STRATEGY, risk: {sl: '6.000000000000000001', tp: '12.50'},
        quantity: 3, indicators: {custom: {type: 'EMA', period: 7, source: 'market_data.close'}},
        exit: {long: {condition: {gte: [{ref: 'position.held_bars'}, 18]}, order: {type: 'LO', limit_price: {ref: 'price'}}}}};
    ui.input.setPayload(value); assert.deepEqual(ui.input.read(), value);
    ui.field('risk.tp').value = '13.000000000000000001'; ui.field('risk.tp').onchange();
    assert.equal(ui.input.read().risk.tp, '13.000000000000000001');
    assert.equal(ui.input.read().risk.sl, value.risk.sl);
    assert.deepEqual(ui.input.read().exit, value.exit);
    assert.equal(JSON.parse(ui.element('#strategy-json').value).risk.tp, '13.000000000000000001');
});

test('LO shows its limit, pins the chosen type and never silently changes it to immediate', t => {
    const ui = editor(t);
    ui.field('order.type').value = 'LO'; ui.field('order.type').onchange();
    assert.throws(() => ui.input.read(), /LO cần/);
    ui.field('order.limit_price').value = '{"ref":"trade_data.close"}'; ui.field('order.limit_price').onchange();
    assert.deepEqual(ui.input.read().order, {type: 'LO', limit_price: {ref: 'trade_data.close'}});
    assert.match(ui.element('#order-help').textContent, /3 nến.*trong ngày/);
    ui.field('order.type').value = 'IMMEDIATE'; ui.field('order.type').onchange();
    assert.equal('order' in ui.input.read(), false);
});

test('date pair and positive integer quantity are checked before sending', t => {
    const ui = editor(t);
    ui.field('from').value = '2026-04-01';
    assert.throws(() => ui.input.read(), /cả hai ngày/);
    ui.field('to').value = '2026-04-01';
    assert.equal(ui.input.read().from, '2026-04-01');
    ui.field('to').value = '2026-03-31'; assert.throws(() => ui.input.read(), /không hợp lệ/);
    ui.field('to').value = '2026-04-01'; ui.field('quantity').value = '1.5'; assert.throws(() => ui.input.read(), /nguyên dương/);
});

test('JSON edits update form before validation and malformed drafts do not replace the valid state', t => {
    const ui = editor(t), value = {...DEFAULT_STRATEGY, quantity: 5, risk: {trailing: '6.2'}};
    ui.element('#strategy-json').value = JSON.stringify(value);
    assert.deepEqual(ui.input.read(), value);
    assert.equal(ui.field('quantity').value, '5');
    ui.element('#strategy-json').value = '{';
    assert.throws(() => ui.input.read(), /JSON chiến lược chưa hợp lệ/);
    assert.equal(ui.field('quantity').value, '5');
    ui.input.setPayload(value); assert.deepEqual(ui.input.read(), value);
});

test('TP tiers and trailing after TP1 remain explicit JSON instead of conflicting simple controls', t => {
    const ui = editor(t), value = {...DEFAULT_STRATEGY, quantity: 3, risk: {sl: 6, targets: [
        {quantity: 1, pct: 6}, {quantity: 'remaining', pct: 12}], trailing_after_tp1: '6'}};
    ui.input.setPayload(value);
    assert.equal(ui.field('risk.tp').disabled, true);
    assert.equal(ui.field('risk.trailing').disabled, true);
    assert.deepEqual(ui.input.read(), value);
});

test('submitting form edits synchronizes the visible JSON even before a change event', t => {
    const ui = editor(t);
    ui.field('order.type').value = 'LO';
    ui.field('order.limit_price').value = '100';
    const value = ui.input.read();
    assert.deepEqual(value.order, {type: 'LO', limit_price: 100});
    assert.deepEqual(JSON.parse(ui.element('#strategy-json').value), value);
    assert.doesNotMatch(ui.element('#input-status').textContent, /LO cần/);
});
