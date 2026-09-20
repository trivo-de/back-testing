import test from 'node:test';
import assert from 'node:assert/strict';

test('theme toggle persists and storage changes synchronize the page', async () => {
    const windowTarget = new EventTarget();
    const button = new EventTarget();
    button.dataset = {};
    button.setAttribute = (name, value) => { button[name] = value; };
    globalThis.window = windowTarget;
    globalThis.document = {documentElement: {dataset: {}}, querySelectorAll: () => [button]};
    globalThis.matchMedia = () => ({matches: true});
    globalThis.localStorage = {value: null, getItem() { return this.value; }, setItem(key, value) { this.value = value; }};

    await import(`../../src/backtest_hpg/web/theme.mjs?test=${Date.now()}`);
    assert.equal(document.documentElement.dataset.theme, 'dark');
    assert.equal(button.textContent, '☾');
    button.dispatchEvent(new Event('click'));
    assert.equal(document.documentElement.dataset.theme, 'light');
    assert.equal(button.textContent, '☀');
    assert.equal(localStorage.value, 'light');

    const event = new Event('storage');
    Object.assign(event, {key: 'backtest-theme', newValue: 'dark'});
    window.dispatchEvent(event);
    assert.equal(document.documentElement.dataset.theme, 'dark');

    await import(`../../src/backtest_hpg/web/theme.mjs?duplicate=${Date.now()}`);
    button.dispatchEvent(new Event('click'));
    assert.equal(document.documentElement.dataset.theme, 'dark');
});
